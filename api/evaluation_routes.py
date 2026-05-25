"""FastAPI routes for the evaluation UI.

Adds /evaluations (HTML) + /api/evaluations/* endpoints.
"""
from __future__ import annotations
import json, logging, sys
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))

logger = logging.getLogger("trip_planner.eval_routes")
router = APIRouter()

REPORTS_DIR = ROOT / "evaluations" / "reports"
CHARTS_DIR = REPORTS_DIR / "charts"
FRONTEND_HTML = ROOT / "frontend" / "evaluations.html"


class RunEvalIn(BaseModel):
    skip_deepeval: bool = True
    threshold: float = 0.5


def _read_json(p: Path):
    if not p.exists(): return None
    try: return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning("read %s failed: %s", p, e); return None


def _list_charts():
    if not CHARTS_DIR.exists(): return []
    return sorted(p.name for p in CHARTS_DIR.glob("*.png"))


def _build_full_summary():
    s = _read_json(REPORTS_DIR / "evaluation_summary.json")
    if not s: return None
    s["charts"] = _list_charts()
    ragas = _read_json(REPORTS_DIR / "ragas_full_report.json")
    if ragas: s["ragas"] = ragas.get("summary", {})
    return s


@router.get("/evaluations", response_class=HTMLResponse)
def eval_page():
    if FRONTEND_HTML.exists():
        return HTMLResponse(FRONTEND_HTML.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Evaluations</h1><p>evaluations.html missing.</p>")


@router.get("/api/evaluations/summary")
def get_summary():
    s = _build_full_summary()
    if not s: raise HTTPException(status_code=404, detail="No evaluation run yet.")
    return s


@router.get("/api/evaluations/results")
def get_results():
    p = REPORTS_DIR / "evaluation_results.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


@router.get("/api/evaluations/ragas")
def get_ragas():
    p = REPORTS_DIR / "ragas_full_report.json"
    if not p.exists():
        return {"skipped": True, "reason": "ragas_full_report.json not found"}
    return json.loads(p.read_text(encoding="utf-8"))


@router.get("/api/evaluations/report", response_class=PlainTextResponse)
def get_md():
    p = REPORTS_DIR / "evaluation_report.md"
    return p.read_text(encoding="utf-8") if p.exists() else ""


@router.get("/api/evaluations/chart/{name}")
def get_chart(name: str):
    safe = Path(name).name
    path = CHARTS_DIR / safe
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"chart {safe} not found")
    return FileResponse(str(path), media_type="image/png")


@router.post("/api/evaluations/run")
def run_eval(payload: RunEvalIn):
    try:
        from evaluations.loader import load_cases
        from evaluations.basic_eval import run_basic_eval
        from evaluations.deepeval_runner import run_deepeval
        from evaluations.metrics import compute_summary
        from evaluations.visualization import make_all_charts, make_ragas_charts
        from evaluations.report import write_reports
        from evaluations.ragas_metrics import compute_all, summarise_ragas
    except Exception as e:
        raise HTTPException(500, detail=f"eval modules not importable: {e}")

    cases = load_cases(ROOT / "evaluation_data" / "evaluation_cases.txt")
    if not cases:
        raise HTTPException(400, detail="no eval cases")
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    try:
        results = run_basic_eval(cases, out_dir=REPORTS_DIR)
        summary = compute_summary(results)
        # RAGAS-style metrics
        rwm = compute_all(results)
        ragas_summary = summarise_ragas(rwm)
        (REPORTS_DIR / "ragas_full_report.json").write_text(
            json.dumps({"summary": ragas_summary, "per_case": rwm},
                       indent=2, default=str), encoding="utf-8")

        if payload.skip_deepeval:
            de = {"skipped": True, "reason": "skipped from UI"}
        else:
            de = run_deepeval(results, out_dir=REPORTS_DIR, threshold=payload.threshold)
        make_all_charts(results, de, CHARTS_DIR)
        make_ragas_charts(ragas_summary, CHARTS_DIR)
        write_reports(results, summary, de, REPORTS_DIR)
    except Exception as e:
        logger.exception("eval run failed")
        raise HTTPException(500, detail=f"eval failed: {e}")

    return {"ok": True, "cases_run": len(cases),
            "summary": _build_full_summary() or {
                "basic_metrics": summary, "deepeval": de,
                "ragas": ragas_summary, "charts": _list_charts()}}
