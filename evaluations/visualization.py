"""Chart generation for evaluation runs.

All charts save as PNG into ``reports/charts/``. An optional interactive
Plotly HTML dashboard is also produced when plotly is available.

Every plot call is wrapped — a single chart failure never aborts the run.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger("evaluations.viz")

try:
    import matplotlib
    matplotlib.use("Agg")  # non-interactive backend - safe for servers
    import matplotlib.pyplot as plt
    HAS_MPL = True
except Exception as e:
    logger.warning("matplotlib not available: %s", e)
    HAS_MPL = False

try:
    import seaborn as sns
    sns.set_theme(style="whitegrid")
    HAS_SNS = True
except Exception:
    HAS_SNS = False

try:
    import plotly.graph_objects as go
    HAS_PLOTLY = True
except Exception:
    HAS_PLOTLY = False


# ---------- helpers ----------
def _safe(fn):
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            logger.warning("chart '%s' failed: %s", fn.__name__, e)
            return None
    return wrapper


def _save(fig, out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, bbox_inches="tight", dpi=120)
    plt.close(fig)
    return out


# ---------- individual charts ----------
@_safe
def chart_pass_fail_pie(results: List[Dict[str, Any]], out: Path) -> Path:
    passed = sum(1 for r in results if r.get("passed"))
    failed = len(results) - passed
    fig, ax = plt.subplots(figsize=(5, 5))
    ax.pie([passed, failed], labels=[f"Passed ({passed})", f"Failed ({failed})"],
           autopct="%1.1f%%",
           colors=["#22c55e", "#ef4444"],
           startangle=90)
    ax.set_title("Pass / Fail ratio")
    return _save(fig, out)


@_safe
def chart_category_bar(results: List[Dict[str, Any]], out: Path) -> Path:
    cats: Dict[str, Dict[str, int]] = {}
    for r in results:
        c = r.get("category", "unknown")
        slot = cats.setdefault(c, {"passed": 0, "failed": 0})
        if r.get("passed"):
            slot["passed"] += 1
        else:
            slot["failed"] += 1
    labels = list(cats.keys())
    passed = [cats[c]["passed"] for c in labels]
    failed = [cats[c]["failed"] for c in labels]
    fig, ax = plt.subplots(figsize=(8, 5))
    x = range(len(labels))
    ax.bar(x, passed, label="Passed", color="#22c55e")
    ax.bar(x, failed, bottom=passed, label="Failed", color="#ef4444")
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, rotation=20)
    ax.set_ylabel("Number of cases")
    ax.set_title("Pass / Fail by category")
    ax.legend()
    return _save(fig, out)


@_safe
def chart_latency_line(results: List[Dict[str, Any]], out: Path) -> Path:
    ids = [r.get("case_id", "?") for r in results]
    lat = [float(r.get("latency_s", 0.0)) for r in results]
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.plot(ids, lat, marker="o", color="#0ea5e9")
    ax.set_xticks(range(len(ids)))
    ax.set_xticklabels(ids, rotation=60, ha="right")
    ax.set_ylabel("Latency (s)")
    ax.set_title("Response time per case")
    ax.axhline(sum(lat) / max(1, len(lat)), color="#f59e0b",
               linestyle="--", label="mean")
    ax.legend()
    return _save(fig, out)


@_safe
def chart_latency_histogram(results: List[Dict[str, Any]], out: Path) -> Path:
    lat = [float(r.get("latency_s", 0.0)) for r in results]
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.hist(lat, bins=10, color="#6366f1", edgecolor="white")
    ax.set_xlabel("Latency (s)")
    ax.set_ylabel("Case count")
    ax.set_title("Latency distribution")
    return _save(fig, out)


@_safe
def chart_guardrail_violations(results: List[Dict[str, Any]], out: Path) -> Path:
    pii_yes = sum(1 for r in results if r.get("pii_detected"))
    pii_no = len(results) - pii_yes
    fig, ax = plt.subplots(figsize=(5, 5))
    ax.bar(["PII detected", "Clean"], [pii_yes, pii_no],
           color=["#f59e0b", "#94a3b8"])
    ax.set_title("PII guardrail activations")
    ax.set_ylabel("Cases")
    for i, v in enumerate([pii_yes, pii_no]):
        ax.text(i, v + 0.05, str(v), ha="center")
    return _save(fig, out)


@_safe
def chart_deepeval_scores(deepeval_summary: Dict[str, Any], out: Path) -> Path:
    if deepeval_summary.get("skipped"):
        return None
    avgs = deepeval_summary.get("metric_averages") or {}
    if not avgs:
        return None
    metrics = list(avgs.keys())
    scores = [avgs[m] for m in metrics]
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(metrics, scores, color="#0ea5e9")
    ax.axhline(deepeval_summary.get("threshold", 0.5),
               color="#ef4444", linestyle="--", label="threshold")
    ax.set_ylim(0, 1)
    ax.set_ylabel("Average score")
    ax.set_title("DeepEval metric averages")
    for i, v in enumerate(scores):
        ax.text(i, v + 0.02, f"{v:.2f}", ha="center")
    ax.legend()
    plt.xticks(rotation=20)
    return _save(fig, out)


@_safe
def chart_plotly_dashboard(results, deepeval_summary, out_html: Path) -> Path:
    if not HAS_PLOTLY:
        return None
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=[r.get("case_id") for r in results],
        y=[r.get("latency_s") for r in results],
        marker_color=["#22c55e" if r.get("passed") else "#ef4444" for r in results],
        name="Latency (s)",
        text=[("PASS" if r.get("passed") else "FAIL") for r in results],
    ))
    fig.update_layout(
        title="Trip Planner Evaluation — Latency by case (green=pass, red=fail)",
        xaxis_title="Case ID",
        yaxis_title="Latency (s)",
        template="plotly_white",
    )
    out_html.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(str(out_html), include_plotlyjs="cdn")
    return out_html


# ---------- entry point ----------
def make_all_charts(
    results: List[Dict[str, Any]],
    deepeval_summary: Dict[str, Any],
    charts_dir: Path,
) -> List[Path]:
    charts_dir = Path(charts_dir)
    charts_dir.mkdir(parents=True, exist_ok=True)

    paths: List[Path] = []
    if not HAS_MPL:
        logger.warning("matplotlib missing — skipping all static charts.")
    else:
        for fn, name in [
            (chart_pass_fail_pie, "pass_fail_pie.png"),
            (chart_category_bar, "category_bar.png"),
            (chart_latency_line, "latency_line.png"),
            (chart_latency_histogram, "latency_histogram.png"),
            (chart_guardrail_violations, "guardrail_violations.png"),
        ]:
            p = fn(results, charts_dir / name)
            if p:
                paths.append(p)

        p = chart_deepeval_scores(deepeval_summary, charts_dir / "deepeval_scores.png")
        if p:
            paths.append(p)

    p = chart_plotly_dashboard(results, deepeval_summary, charts_dir / "dashboard.html")
    if p:
        paths.append(p)

    logger.info("generated %d chart files", len(paths))
    return paths


# ---------------- RAGAS-style charts (new) ----------------
@_safe
def chart_ragas_overall_bar(ragas_summary, out: Path) -> Path:
    if ragas_summary.get("skipped"): return None
    means = ragas_summary.get("overall_means") or {}
    metric_cols = ragas_summary.get("metric_cols") or list(means.keys())
    if not metric_cols: return None
    colors = ['#4e79a7', '#f28e2b', '#59a14f', '#e15759', '#76b7b2']
    vals = [means.get(m, 0) for m in metric_cols]
    fig, ax = plt.subplots(figsize=(9, 5))
    bars = ax.bar(range(len(metric_cols)), vals,
                   color=colors[:len(metric_cols)],
                   edgecolor='white', linewidth=1.5)
    ax.set_xticks(range(len(metric_cols)))
    ax.set_xticklabels([m.replace('_', '\n') for m in metric_cols], fontsize=9)
    ax.set_ylim(0, 1.2)
    ax.set_title('RAGAS — Overall Metric Scores', fontsize=13, fontweight='bold')
    ax.set_ylabel('Score')
    for bar, v in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width()/2, v + 0.03,
                f'{v:.2f}', ha='center', fontsize=10, fontweight='bold')
    return _save(fig, out)


@_safe
def chart_ragas_heatmap(ragas_summary, out: Path) -> Path:
    if ragas_summary.get("skipped"): return None
    rows = ragas_summary.get("per_case") or []
    metric_cols = ragas_summary.get("metric_cols") or []
    if not rows or not metric_cols: return None
    import numpy as np
    mat = np.array([[r.get(c, 0) for c in metric_cols] for r in rows])
    fig, ax = plt.subplots(figsize=(8, max(4, len(rows) * 0.4)))
    im = ax.imshow(mat, cmap='RdYlGn', vmin=0, vmax=1, aspect='auto')
    ax.set_xticks(range(len(metric_cols)))
    ax.set_xticklabels([m.replace('_', '\n') for m in metric_cols], fontsize=9)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([r.get("case_id", f"Q{i+1}") for i, r in enumerate(rows)], fontsize=9)
    ax.set_title('RAGAS — Per-Case Heatmap', fontsize=13, fontweight='bold')
    # annotate cells
    for i in range(mat.shape[0]):
        for j in range(mat.shape[1]):
            ax.text(j, i, f"{mat[i, j]:.2f}", ha='center', va='center',
                    color='black' if mat[i, j] > 0.5 else 'white', fontsize=8)
    plt.colorbar(im, ax=ax, fraction=0.04)
    return _save(fig, out)


@_safe
def chart_ragas_quality_tier(ragas_summary, out: Path) -> Path:
    if ragas_summary.get("skipped"): return None
    tier_means = ragas_summary.get("tier_means") or {}
    metric_cols = ragas_summary.get("metric_cols") or []
    if not tier_means or not metric_cols: return None
    import numpy as np
    tier_color = {'good': '#2ecc71', 'medium': '#f39c12', 'bad': '#e74c3c'}
    tiers = [t for t in ('good', 'medium', 'bad') if t in tier_means]
    x = np.arange(len(metric_cols))
    w = 0.25
    fig, ax = plt.subplots(figsize=(9, 5))
    for idx, t in enumerate(tiers):
        vals = [tier_means[t].get(c, 0) for c in metric_cols]
        ax.bar(x + idx*w, vals, w, label=t.capitalize(), color=tier_color[t])
    ax.set_xticks(x + w * (len(tiers)-1) / 2)
    ax.set_xticklabels([m.replace('_', '\n') for m in metric_cols], fontsize=9)
    ax.set_ylim(0, 1.2)
    ax.set_ylabel('Mean score')
    ax.set_title('RAGAS — Quality Tier Comparison', fontsize=13, fontweight='bold')
    ax.legend()
    return _save(fig, out)


@_safe
def chart_ragas_dashboard(ragas_summary, out: Path) -> Path:
    """The 1x3 combined panel matching the reference dashboard."""
    if ragas_summary.get("skipped"): return None
    means = ragas_summary.get("overall_means") or {}
    metric_cols = ragas_summary.get("metric_cols") or list(means.keys())
    rows = ragas_summary.get("per_case") or []
    tier_means = ragas_summary.get("tier_means") or {}
    if not metric_cols: return None
    import numpy as np

    fig, axes = plt.subplots(1, 3, figsize=(22, 6))
    fig.suptitle('RAGAS Evaluation Dashboard', fontsize=16, fontweight='bold')

    # Panel 1: overall bar
    colors = ['#4e79a7', '#f28e2b', '#59a14f', '#e15759', '#76b7b2']
    vals = [means.get(m, 0) for m in metric_cols]
    bars = axes[0].bar(range(len(metric_cols)), vals,
                        color=colors[:len(metric_cols)], edgecolor='white', linewidth=1.5)
    axes[0].set_xticks(range(len(metric_cols)))
    axes[0].set_xticklabels([m.replace('_', '\n') for m in metric_cols], fontsize=8)
    axes[0].set_ylim(0, 1.2)
    axes[0].set_title('Overall Metric Scores')
    for bar, v in zip(bars, vals):
        axes[0].text(bar.get_x() + bar.get_width()/2, v + 0.03,
                      f'{v:.2f}', ha='center', fontsize=9, fontweight='bold')

    # Panel 2: heatmap
    if rows:
        mat = np.array([[r.get(c, 0) for c in metric_cols] for r in rows])
        im = axes[1].imshow(mat, cmap='RdYlGn', vmin=0, vmax=1, aspect='auto')
        axes[1].set_xticks(range(len(metric_cols)))
        axes[1].set_xticklabels([m.replace('_', '\n') for m in metric_cols], fontsize=7)
        axes[1].set_yticks(range(len(rows)))
        axes[1].set_yticklabels([r.get("case_id", f"Q{i+1}") for i, r in enumerate(rows)], fontsize=8)
        axes[1].set_title('Per-Case Heatmap')
        plt.colorbar(im, ax=axes[1], fraction=0.04)

    # Panel 3: quality tier
    if tier_means:
        tier_color = {'good': '#2ecc71', 'medium': '#f39c12', 'bad': '#e74c3c'}
        tiers = [t for t in ('good', 'medium', 'bad') if t in tier_means]
        x = np.arange(len(metric_cols))
        w = 0.25
        for idx, t in enumerate(tiers):
            tvals = [tier_means[t].get(c, 0) for c in metric_cols]
            axes[2].bar(x + idx*w, tvals, w, label=t.capitalize(), color=tier_color[t])
        axes[2].set_xticks(x + w * (len(tiers)-1) / 2)
        axes[2].set_xticklabels([m.replace('_', '\n') for m in metric_cols], fontsize=7)
        axes[2].set_ylim(0, 1.2)
        axes[2].set_title('Quality Tier Comparison')
        axes[2].legend()

    plt.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, bbox_inches='tight', dpi=120)
    plt.close(fig)
    return out


def make_ragas_charts(ragas_summary, charts_dir: Path):
    """Generate all 4 RAGAS PNG charts. Returns list of generated paths."""
    charts_dir = Path(charts_dir); charts_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for fn, name in [
        (chart_ragas_dashboard,     "ragas_dashboard.png"),
        (chart_ragas_overall_bar,   "ragas_overall_bar.png"),
        (chart_ragas_heatmap,       "ragas_heatmap.png"),
        (chart_ragas_quality_tier,  "ragas_quality_tier.png"),
    ]:
        p = fn(ragas_summary, charts_dir / name)
        if p: paths.append(p)
    return paths
