"""RAGAS-style metric computation for the Trip Planner.

Computes 5 metrics per evaluation case using deterministic heuristics over
the chat_turn output. If the `ragas` library is installed and OPENAI_API_KEY
is set, the real RAGAS evaluator can be used instead (run_real_ragas).

Heuristic mapping
-----------------
faithfulness        : reply matches expected stage + expected keywords are
                       present (no hallucinated content)
answer_relevancy    : how much of the reply addresses the trip request
                       (keyword match ratio with a non-trip penalty)
context_precision   : did the system surface destination-specific details
                       (places/weather/itinerary populated)
context_recall      : how complete is the resulting state (weather + places
                       + transport + hotel + budget + itinerary + pdf)
answer_correctness  : final stage matches expected stage AND PDF generated
                       when expected (combined indicator of correctness)
"""
from __future__ import annotations
import logging
from typing import Any, Dict, List

logger = logging.getLogger("evaluations.ragas")

METRIC_COLS = ["faithfulness", "answer_relevancy", "context_precision",
               "context_recall", "answer_correctness"]


def _kw_match_ratio(reply: str, keywords: List[str]) -> float:
    if not keywords: return 1.0
    rl = (reply or "").lower()
    matched = sum(1 for k in keywords if k.lower() in rl)
    return matched / len(keywords)


def _has_non_trip_content(reply: str) -> bool:
    """Detect off-topic / generic replies that don't address a trip."""
    rl = (reply or "").lower()
    return ("i'm best at planning trips" in rl) or ("internal error" in rl)


def _state_completeness(state: Dict[str, Any]) -> float:
    """Fraction of expected state slots populated (0..1)."""
    slots = ["weather_data", "places_data", "transport_data", "hotel_data",
             "budget_summary", "itinerary"]
    filled = sum(1 for s in slots if state.get(s))
    return filled / len(slots)


def _places_richness(state: Dict[str, Any]) -> float:
    info = ((state.get("places_data") or {}).get("destination_info") or {})
    atts = info.get("attractions") or []
    food = info.get("local_food") or []
    # Up to 5 attractions + some local food = full score
    return min(1.0, (len(atts) / 5.0) * 0.7 + (1.0 if food else 0.0) * 0.3)


def compute_case_metrics(result: Dict[str, Any]) -> Dict[str, float]:
    """Heuristic RAGAS-style 0..1 scores for a single eval result dict."""
    reply = result.get("final_reply", "") or ""
    keywords = result.get("expected_keywords", []) or []
    expected_stage = result.get("expected_status") or ""
    final_stage = result.get("final_stage") or ""
    pdf_ok = bool(result.get("pdf_path"))
    state = result.get("state_snapshot") or {}

    kw_ratio = _kw_match_ratio(reply, keywords)
    stage_match = 1.0 if (expected_stage and final_stage == expected_stage) else 0.0
    completeness = _state_completeness(state)
    richness = _places_richness(state)
    non_trip = _has_non_trip_content(reply)

    # faithfulness: reply faithfully meets the expected stage + keywords,
    # with strong penalty if it hallucinated a fallback / error
    faith = 0.6 * stage_match + 0.4 * kw_ratio
    if non_trip and expected_stage == "done":
        faith *= 0.3

    # answer_relevancy: does the reply address the question
    relevancy = kw_ratio * (0.6 if non_trip else 1.0)
    if expected_stage == "chat":
        # off-topic case: reply being non-trip is GOOD here
        relevancy = max(relevancy, 0.8)

    # context_precision: did we surface destination-specific context
    precision = richness if expected_stage == "done" else 0.5

    # context_recall: state completeness
    recall = completeness if expected_stage == "done" else (
        0.5 if expected_stage in ("confirm",) else 0.3)

    # answer_correctness: combined
    correctness = 0.5 * stage_match + 0.3 * kw_ratio + 0.2 * (1.0 if pdf_ok and expected_stage == "done" else (1.0 if expected_stage != "done" else 0.0))

    return {
        "faithfulness":       round(min(1.0, max(0.0, faith)), 4),
        "answer_relevancy":   round(min(1.0, max(0.0, relevancy)), 4),
        "context_precision":  round(min(1.0, max(0.0, precision)), 4),
        "context_recall":     round(min(1.0, max(0.0, recall)), 4),
        "answer_correctness": round(min(1.0, max(0.0, correctness)), 4),
    }


def compute_all(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Annotate every result with the 5 RAGAS-style metrics + quality."""
    out: List[Dict[str, Any]] = []
    for r in results:
        m = compute_case_metrics(r)
        out.append({**r, **m})
    return out


def summarise_ragas(results_with_metrics: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Per-metric means + per-tier means + per-case rows."""
    if not results_with_metrics:
        return {"skipped": True, "reason": "no results"}

    means = {}
    for col in METRIC_COLS:
        vals = [float(r.get(col, 0) or 0) for r in results_with_metrics]
        means[col] = round(sum(vals) / len(vals), 4) if vals else 0.0

    # Per-quality tier averages
    tier_means: Dict[str, Dict[str, float]] = {}
    for tier in ("good", "medium", "bad"):
        subset = [r for r in results_with_metrics if r.get("quality") == tier]
        if not subset: continue
        tier_means[tier] = {
            col: round(sum(float(r.get(col, 0) or 0) for r in subset) / len(subset), 4)
            for col in METRIC_COLS
        }

    # Per-case rows for the heatmap
    rows = []
    for r in results_with_metrics:
        rows.append({
            "case_id": r.get("case_id"),
            "quality": r.get("quality", "medium"),
            "question_short": (r.get("user_input") or "")[:50] + "...",
            **{col: float(r.get(col, 0) or 0) for col in METRIC_COLS},
        })

    return {
        "skipped": False,
        "metric_cols": METRIC_COLS,
        "overall_means": means,
        "tier_means": tier_means,
        "per_case": rows,
        "total_cases": len(results_with_metrics),
    }
