"""FastAPI server — chat + embedded evaluation routes."""
from __future__ import annotations
import logging, sys, traceback, uuid
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))

from chat_flow import chat_turn, GREETING
from config import settings

logger = logging.getLogger("trip_planner")
logging.basicConfig(level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

app = FastAPI(title="Multi-Agent Trip Planner", version="1.0.0")

FRONTEND = ROOT / "frontend"
if FRONTEND.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND)), name="static")


class ChatIn(BaseModel):
    session_id: Optional[str] = None
    message: str


class ChatOut(BaseModel):
    session_id: str
    reply: str
    stage: str
    pdf_url: Optional[str] = None
    done: bool = False
    pii_warning: Optional[str] = None


@app.get("/", response_class=HTMLResponse)
def index():
    p = FRONTEND / "index.html"
    headers = {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
    }
    if p.exists():
        return HTMLResponse(p.read_text(encoding="utf-8"), headers=headers)
    return HTMLResponse("<h1>Trip Planner</h1>", headers=headers)


@app.get("/api/health")
def health():
    return {"ok": True, "openai": settings.has_openai(), "weather": settings.has_weather()}


@app.get("/api/greeting")
def greeting():
    return {"greeting": GREETING}


@app.post("/api/chat", response_model=ChatOut)
def chat(payload: ChatIn):
    sid = payload.session_id or uuid.uuid4().hex[:12]
    try:
        result = chat_turn(sid, payload.message or "")
    except Exception as e:
        logger.error("chat_turn crashed (sid=%s):\n%s", sid, traceback.format_exc())
        return ChatOut(session_id=sid,
            reply=f"Internal error: {e.__class__.__name__}: {e}",
            stage="error")
    pdf_url = f"/api/pdf/{Path(result.pdf_path).name}" if result.pdf_path else None
    return ChatOut(session_id=sid, reply=result.reply, stage=result.stage,
                    pdf_url=pdf_url, done=result.done,
                    pii_warning=getattr(result, "pii_warning", None))


@app.get("/api/pdf/{name}")
def get_pdf(name: str):
    safe = Path(name).name
    path = settings.outputs_dir / safe
    if not path.exists():
        raise HTTPException(status_code=404, detail="PDF not found")
    return FileResponse(str(path), media_type="application/pdf", filename=safe)


# ==================== Evaluation routes ====================
# Loads /api/evaluations/* endpoints + /evaluations standalone page.
try:
    from api.evaluation_routes import router as eval_router
    app.include_router(eval_router)
    logger.info("Evaluation routes mounted")
except Exception as e:
    logger.error("Could not mount evaluation routes: %s", e)
    # Fallback: minimal inline routes so the modal still works partially
    from fastapi import APIRouter
    fallback = APIRouter()

    @fallback.get("/api/evaluations/summary")
    def _no_summary():
        raise HTTPException(404, detail="Evaluation framework not available. "
                                         "Make sure api/evaluation_routes.py and the evaluations/ folder are present.")
    app.include_router(fallback)


def main():
    import uvicorn
    uvicorn.run("server:app", host=settings.host, port=settings.port, reload=False)


if __name__ == "__main__":
    main()
