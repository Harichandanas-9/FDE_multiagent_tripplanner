"""Single entry point — runs full eval pipeline incl. RAGAS-style metrics."""
from __future__ import annotations
import argparse, logging, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from evaluations.loader import load_cases
from evaluations.basic_eval import run_basic_eval
from evaluations.deepeval_runner import run_deepeval
from evaluations.metrics import compute_summary
from evaluations.visualization import make_all_charts, make_ragas_charts
from evaluations.report import write_reports
from evaluations.ragas_metrics import compute_all, summarise_ragas


def _setup_logging(log_path):
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.FileHandler(log_path, encoding="utf-8"),
                  logging.StreamHandler(sys.stdout)],
        force=True,
    )


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--cases", default=str(ROOT / "evaluation_data" / "evaluation_cases.txt"))
    p.add_argument("--out-dir", default=str(ROOT / "evaluations" / "reports"))
    p.add_argument("--threshold", type=float, default=0.5)
    p.add_argument("--skip-deepeval", action="store_true")
    args = p.parse_args(argv)

    out_dir = Path(args.out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    charts_dir = out_dir / "charts"
    _setup_logging(out_dir / "logs" / "eval.log")
    log = logging.getLogger("run_evaluations")

    cases = load_cases(args.cases)
    if not cases:
        log.error("no eval cases"); return 2

    log.info("running BASIC eval ...")
    results = run_basic_eval(cases, out_dir=out_dir)

    log.info("computing summary ...")
    summary = compute_summary(results)

    log.info("computing RAGAS-style metrics ...")
    results_with_metrics = compute_all(results)
    ragas_summary = summarise_ragas(results_with_metrics)
    # save ragas csv + json
    import json
    (out_dir / "ragas_full_report.json").write_text(
        json.dumps({"summary": ragas_summary, "per_case": results_with_metrics},
                   indent=2, default=str), encoding="utf-8")

    if args.skip_deepeval:
        de = {"skipped": True, "reason": "--skip-deepeval"}
    else:
        log.info("running DeepEval ...")
        de = run_deepeval(results, out_dir=out_dir, threshold=args.threshold)

    log.info("generating charts ...")
    make_all_charts(results, de, charts_dir)
    make_ragas_charts(ragas_summary, charts_dir)

    log.info("writing reports ...")
    write_reports(results, summary, de, out_dir)

    # Print headline
    print("\n" + "=" * 60)
    print(" TRIP PLANNER — EVALUATION SUMMARY")
    print("=" * 60)
    print(f"  Cases run        : {summary.get('total', 0)}")
    print(f"  Passed / Failed  : {summary.get('passed', 0)} / {summary.get('failed', 0)}")
    print(f"  Success rate     : {summary.get('success_rate', 0)*100:.1f}%")
    print(f"  Mean latency     : {summary.get('latency', {}).get('mean_s', 0):.2f}s")
    print("\n  RAGAS-style averages:")
    for k, v in (ragas_summary.get("overall_means") or {}).items():
        print(f"    {k:25s} : {v:.3f}")
    print(f"  Reports in       : {out_dir}")
    print("=" * 60 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
