"""Basic evaluation runner.

For each EvalCase:
  1. Reset chat session (unique id)
  2. Run each user_turn through chat_turn()
  3. Capture: latency, reply, pdf_path, pii_warning, state_snapshot
  4. Compare against expected_status + expected_keywords
  5. Save individual + aggregated results
"""
from __future__ import annotations
import csv, json, logging, time, uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("evaluations.basic")


@dataclass
class BasicResult:
    case_id: str
    category: str
    quality: str
    user_input: str
    final_reply: str
    final_stage: str
    expected_status: str
    expected_keywords: List[str]
    matched_keywords: List[str]
    pdf_path: Optional[str]
    pii_detected: bool
    pii_warning: Optional[str]
    latency_s: float
    error: Optional[str] = None
    passed: bool = False
    turn_latencies: List[float] = field(default_factory=list)
    state_snapshot: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self): return asdict(self)


def _eval_pass(es, kws, fs, fr):
    rl = (fr or "").lower()
    matched = [k for k in kws if k.lower() in rl]
    status_ok = (not es) or (fs == es)
    kw_ok = (len(matched) >= max(1, len(kws) // 2)) if kws else True
    return (status_ok and kw_ok), matched


def _snapshot_state(state):
    """Capture state slots needed for RAGAS-style metrics (without messages)."""
    keys = ["weather_data", "places_data", "transport_data", "hotel_data",
            "budget_summary", "itinerary", "review_status", "trip_preferences"]
    snap = {}
    for k in keys:
        v = state.get(k) if isinstance(state, dict) else None
        if v: snap[k] = v
    return snap


def run_basic_eval(cases, out_dir, chat_turn_fn=None):
    if chat_turn_fn is None:
        try:
            from chat_flow import chat_turn as _ct
            chat_turn_fn = _ct
        except Exception as e:
            logger.error("could not import chat_flow.chat_turn: %s", e)
            return []
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    results: List[BasicResult] = []

    for case in cases:
        sid = f"eval-{case.case_id}-{uuid.uuid4().hex[:6]}"
        t0 = time.perf_counter()
        turn_lat = []
        last_reply = ""; last_stage = "greet"
        pdf_path = None; pii_warn = None
        err = None; final_state = {}

        try:
            chat_turn_fn(sid, "")
            for turn in case.user_turns:
                tt0 = time.perf_counter()
                try:
                    resp = chat_turn_fn(sid, turn)
                except Exception as inner:
                    err = f"{inner.__class__.__name__}: {inner}"
                    break
                tt1 = time.perf_counter()
                turn_lat.append(round(tt1 - tt0, 3))
                last_reply = getattr(resp, "reply", "") or ""
                last_stage = getattr(resp, "stage", "") or ""
                pdf_path = getattr(resp, "pdf_path", None) or pdf_path
                pii_warn = getattr(resp, "pii_warning", None) or pii_warn
                final_state = getattr(resp, "state", {}) or {}
        except Exception as e:
            err = f"{e.__class__.__name__}: {e}"
            logger.exception("case %s failed", case.case_id)

        total_lat = round(time.perf_counter() - t0, 3)
        passed, matched = _eval_pass(case.expected_status, case.expected_keywords,
                                       last_stage, last_reply)
        if err: passed = False

        r = BasicResult(
            case_id=case.case_id, category=case.category, quality=case.quality,
            user_input=" || ".join(case.user_turns),
            final_reply=last_reply, final_stage=last_stage,
            expected_status=case.expected_status,
            expected_keywords=case.expected_keywords,
            matched_keywords=matched,
            pdf_path=pdf_path, pii_detected=bool(pii_warn), pii_warning=pii_warn,
            latency_s=total_lat, error=err, passed=passed,
            turn_latencies=turn_lat,
            state_snapshot=_snapshot_state(final_state),
        )
        results.append(r)
        logger.info("case %s -> %s (stage=%s, %.2fs)",
                     case.case_id, "PASS" if passed else "FAIL", last_stage, total_lat)

    json_path = out_dir / "evaluation_results.json"
    csv_path = out_dir / "evaluation_results.csv"
    dicts = [r.to_dict() for r in results]
    json_path.write_text(json.dumps(dicts, indent=2, default=str), encoding="utf-8")
    fields = ["case_id","category","quality","passed","final_stage","expected_status",
              "latency_s","pdf_path","pii_detected","matched_keywords",
              "expected_keywords","error","final_reply"]
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for d in dicts:
            row = dict(d)
            row["matched_keywords"] = ",".join(d.get("matched_keywords") or [])
            row["expected_keywords"] = ",".join(d.get("expected_keywords") or [])
            row["final_reply"] = (d.get("final_reply") or "")[:300].replace("\n", " ")
            w.writerow(row)
    return dicts
