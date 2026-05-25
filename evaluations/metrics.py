"""Pure aggregation functions over BasicResult lists.

Kept dependency-free (only stdlib) so they're trivially testable and reusable.
"""
from __future__ import annotations

import statistics
from typing import Any, Dict, Iterable, List


def compute_summary(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Return overall + per-category metrics for a list of result dicts."""
    if not results:
        return {"total": 0, "note": "no results"}

    total = len(results)
    passed = sum(1 for r in results if r.get("passed"))
    failed = total - passed
    errors = sum(1 for r in results if r.get("error"))
    empty = sum(1 for r in results if not (r.get("final_reply") or "").strip())
    pii_hits = sum(1 for r in results if r.get("pii_detected"))
    pdf_made = sum(1 for r in results if r.get("pdf_path"))

    latencies = [float(r.get("latency_s", 0.0)) for r in results if r.get("latency_s")]
    by_cat: Dict[str, Dict[str, int]] = {}
    for r in results:
        c = r.get("category", "unknown")
        slot = by_cat.setdefault(c, {"total": 0, "passed": 0, "failed": 0})
        slot["total"] += 1
        if r.get("passed"):
            slot["passed"] += 1
        else:
            slot["failed"] += 1

    summary: Dict[str, Any] = {
        "total": total,
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "empty_responses": empty,
        "pii_detections": pii_hits,
        "pdf_generated": pdf_made,
        "success_rate": round(passed / total, 4),
        "error_rate": round(errors / total, 4),
        "empty_rate": round(empty / total, 4),
        "completion_rate": round(pdf_made / total, 4),
        "latency": {
            "count": len(latencies),
            "min_s": round(min(latencies), 3) if latencies else 0.0,
            "max_s": round(max(latencies), 3) if latencies else 0.0,
            "mean_s": round(statistics.mean(latencies), 3) if latencies else 0.0,
            "median_s": round(statistics.median(latencies), 3) if latencies else 0.0,
            "stdev_s": round(statistics.stdev(latencies), 3) if len(latencies) > 1 else 0.0,
        },
        "by_category": {k: {**v, "success_rate": round(v["passed"] / v["total"], 4)}
                        for k, v in by_cat.items()},
    }

    # Highlight best / worst by latency among passes
    passed_results = [r for r in results if r.get("passed")]
    if passed_results:
        best = min(passed_results, key=lambda r: r.get("latency_s", float("inf")))
        worst = max(results, key=lambda r: r.get("latency_s", 0.0))
        summary["best_case"] = {"id": best.get("case_id"), "latency_s": best.get("latency_s")}
        summary["worst_case"] = {"id": worst.get("case_id"), "latency_s": worst.get("latency_s")}

    failures = [r.get("case_id") for r in results if not r.get("passed")]
    summary["failed_cases"] = failures
    return summary
