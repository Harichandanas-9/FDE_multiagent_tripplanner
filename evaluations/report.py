"""Aggregated reports: evaluation_summary.json + Markdown summary."""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger("evaluations.report")


def write_reports(
    results: List[Dict[str, Any]],
    summary: Dict[str, Any],
    deepeval_summary: Dict[str, Any],
    out_dir: Path,
) -> Dict[str, Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: Dict[str, Path] = {}

    # ---------- evaluation_summary.json ----------
    summary_path = out_dir / "evaluation_summary.json"
    payload = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "basic_metrics": summary,
        "deepeval": deepeval_summary,
    }
    summary_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    paths["summary_json"] = summary_path

    # ---------- Markdown report ----------
    md_path = out_dir / "evaluation_report.md"
    lines: List[str] = []
    lines.append("# Trip Planner — Evaluation Report")
    lines.append(f"_Generated {payload['generated_at']}_\n")

    lines.append("## Headline metrics")
    if summary.get("total"):
        lines.append(f"- Total cases: **{summary['total']}**")
        lines.append(f"- Passed: **{summary['passed']}** / Failed: **{summary['failed']}**")
        lines.append(f"- Success rate: **{summary['success_rate']*100:.1f}%**")
        lines.append(f"- Completion rate (PDF generated): **{summary['completion_rate']*100:.1f}%**")
        lines.append(f"- Error rate: **{summary['error_rate']*100:.1f}%**")
        lines.append(f"- Empty-response rate: **{summary['empty_rate']*100:.1f}%**")
        lines.append(f"- PII detections: **{summary['pii_detections']}**")
        lat = summary.get("latency", {})
        lines.append(
            f"- Latency: mean **{lat.get('mean_s', 0):.2f}s**, "
            f"median {lat.get('median_s', 0):.2f}s, "
            f"min {lat.get('min_s', 0):.2f}s, max {lat.get('max_s', 0):.2f}s"
        )

    lines.append("\n## Per-category breakdown")
    bc = summary.get("by_category", {}) or {}
    if bc:
        lines.append("| Category | Total | Passed | Failed | Success rate |")
        lines.append("|---|---|---|---|---|")
        for cat, slot in bc.items():
            lines.append(
                f"| {cat} | {slot['total']} | {slot['passed']} | {slot['failed']} | "
                f"{slot['success_rate']*100:.1f}% |"
            )

    if summary.get("best_case"):
        lines.append("\n## Best / worst")
        lines.append(f"- **Best (fastest pass):** {summary['best_case']['id']} "
                     f"({summary['best_case'].get('latency_s')}s)")
        lines.append(f"- **Slowest case:** {summary['worst_case']['id']} "
                     f"({summary['worst_case'].get('latency_s')}s)")

    if summary.get("failed_cases"):
        lines.append("\n## Failed cases")
        for cid in summary["failed_cases"]:
            lines.append(f"- {cid}")

    lines.append("\n## DeepEval results")
    if deepeval_summary.get("skipped"):
        lines.append(f"- _Skipped: {deepeval_summary.get('reason', 'unknown reason')}_")
    else:
        lines.append(f"- Threshold: {deepeval_summary.get('threshold')}")
        lines.append("- Metric averages:")
        for k, v in (deepeval_summary.get("metric_averages") or {}).items():
            lines.append(f"  - **{k}**: {v:.3f}")
        lines.append("- Metric pass rates:")
        for k, v in (deepeval_summary.get("metric_pass_rates") or {}).items():
            lines.append(f"  - **{k}**: {v*100:.1f}%")

    lines.append("\n## Files")
    lines.append("- evaluation_summary.json — full structured summary")
    lines.append("- evaluation_results.json / .csv — per-case raw results")
    lines.append("- deepeval_results.json — DeepEval scores")
    lines.append("- charts/ — PNG plots + optional Plotly dashboard.html")
    lines.append("- logs/ — eval.log\n")

    md_path.write_text("\n".join(lines), encoding="utf-8")
    paths["report_md"] = md_path

    logger.info("wrote %s and %s", summary_path, md_path)
    return paths
