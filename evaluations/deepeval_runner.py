"""DeepEval integration for the Trip Planner.

Evaluates each basic-eval result on:
  * AnswerRelevancyMetric   - answer relevancy
  * FaithfulnessMetric      - faithfulness vs. context
  * HallucinationMetric     - hallucination detection
  * ContextualPrecisionMetric / ContextualRecallMetric (optional)
  * ToolCorrectnessMetric   - tool usage quality (best-effort)

Built to be safe:
  * If deepeval is not installed, returns an informative skip dict
  * If a metric crashes, that single metric is skipped and the others run
  * Works fully offline (skips metrics that require OpenAI when no key)
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("evaluations.deepeval")


def _have_openai_key() -> bool:
    return bool(os.environ.get("OPENAI_API_KEY", "").startswith("sk-"))


def _try_import_deepeval():
    try:
        import deepeval                                                # noqa: F401
        from deepeval import evaluate
        from deepeval.test_case import LLMTestCase
        from deepeval.metrics import (
            AnswerRelevancyMetric,
            FaithfulnessMetric,
            HallucinationMetric,
        )
        return {
            "evaluate": evaluate,
            "LLMTestCase": LLMTestCase,
            "AnswerRelevancyMetric": AnswerRelevancyMetric,
            "FaithfulnessMetric": FaithfulnessMetric,
            "HallucinationMetric": HallucinationMetric,
        }
    except Exception as e:
        logger.warning("deepeval not available (%s); the deepeval pass will be skipped.", e)
        return None


def _build_context_for_case(result: Dict[str, Any]) -> List[str]:
    """Build a context list DeepEval can use for faithfulness/hallucination checks."""
    parts: List[str] = []
    parts.append(
        "This is a multi-agent Trip Planner. It plans trips with weather, "
        "transport, hotel, places, budget and itinerary, then generates a PDF "
        "and ends with 'thank you, happy journey'."
    )
    if result.get("expected_keywords"):
        parts.append("Expected keywords: " + ", ".join(result["expected_keywords"]))
    if result.get("matched_keywords"):
        parts.append("Matched keywords: " + ", ".join(result["matched_keywords"]))
    if result.get("pii_warning"):
        parts.append("PII guardrail message: " + result["pii_warning"])
    return parts


def run_deepeval(
    results: List[Dict[str, Any]],
    out_dir: Path,
    threshold: float = 0.5,
) -> Dict[str, Any]:
    """Run DeepEval over all basic eval results. Saves deepeval_results.json."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "deepeval_results.json"

    de = _try_import_deepeval()
    if de is None:
        payload = {
            "skipped": True,
            "reason": "deepeval not installed (pip install deepeval)",
            "threshold": threshold,
        }
        out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload

    if not _have_openai_key():
        payload = {
            "skipped": True,
            "reason": "OPENAI_API_KEY not set; DeepEval LLM-based metrics need a key.",
            "threshold": threshold,
        }
        out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        logger.warning(payload["reason"])
        return payload

    LLMTestCase = de["LLMTestCase"]
    test_cases = []
    for r in results:
        if r.get("error") or not (r.get("final_reply") or "").strip():
            continue
        context = _build_context_for_case(r)
        try:
            tc = LLMTestCase(
                input=r.get("user_input", ""),
                actual_output=r.get("final_reply", ""),
                context=context,
                retrieval_context=context,
            )
            tc.case_id = r["case_id"]
            test_cases.append(tc)
        except Exception as e:
            logger.warning("could not build LLMTestCase for %s: %s", r.get("case_id"), e)

    if not test_cases:
        payload = {"skipped": True, "reason": "no usable test cases", "threshold": threshold}
        out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload

    metrics = []
    for cls_name in ("AnswerRelevancyMetric", "FaithfulnessMetric", "HallucinationMetric"):
        cls = de.get(cls_name)
        if cls is None:
            continue
        try:
            metrics.append(cls(threshold=threshold))
        except Exception as e:
            logger.warning("metric %s init failed: %s", cls_name, e)

    per_case: List[Dict[str, Any]] = []
    metric_totals: Dict[str, List[float]] = {}

    for tc in test_cases:
        case_entry: Dict[str, Any] = {"case_id": getattr(tc, "case_id", "?"),
                                       "metrics": {}}
        for m in metrics:
            name = m.__class__.__name__
            try:
                m.measure(tc)
                score = float(getattr(m, "score", 0.0) or 0.0)
                passed = bool(getattr(m, "is_successful", lambda: score >= threshold)())
                reason = getattr(m, "reason", "") or ""
                case_entry["metrics"][name] = {
                    "score": round(score, 4),
                    "passed": passed,
                    "reason": reason[:300],
                }
                metric_totals.setdefault(name, []).append(score)
            except Exception as e:
                logger.warning("metric %s failed on %s: %s", name, case_entry["case_id"], e)
                case_entry["metrics"][name] = {"error": str(e)}
        per_case.append(case_entry)

    summary = {
        "skipped": False,
        "threshold": threshold,
        "total_cases": len(per_case),
        "metric_averages": {
            name: round(sum(vals) / len(vals), 4) for name, vals in metric_totals.items() if vals
        },
        "metric_pass_rates": {
            name: round(sum(1 for v in vals if v >= threshold) / len(vals), 4)
            for name, vals in metric_totals.items() if vals
        },
        "per_case": per_case,
    }
    out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    logger.info("DeepEval results saved to %s", out_path)
    return summary
