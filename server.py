"""FastAPI server — chat + embedded evaluation routes."""

from __future__ import annotations

import logging
import os
import sys
import traceback
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# =========================
# Project Root Setup
# =========================

ROOT = Path(__file__).resolve().parent

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# =========================
# Local Imports
# =========================

from chat_flow import chat_turn, GREETING
from tracing import send_feedback, is_enabled as ls_enabled, get_run_url
from config import settings

# =========================
# Logging
# =========================

logger = logging.getLogger("trip_planner")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

# =========================
# FastAPI App
# =========================

app = FastAPI(
    title="Multi-Agent Trip Planner",
    version="1.0.0"
)

# =========================
# Frontend Static Files
# =========================

FRONTEND = ROOT / "frontend"

if FRONTEND.exists():
    app.mount(
        "/static",
        StaticFiles(directory=str(FRONTEND)),
        name="static"
    )

# =========================
# Request / Response Models
# =========================

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
    run_id: Optional[str] = None
    run_url: Optional[str] = None
    guardrail_status: Optional[dict] = None


class FeedbackIn(BaseModel):
    run_id: str
    key: str = "user_thumbs"
    score: float
    comment: Optional[str] = None

# =========================
# Routes
# =========================

@app.get("/", response_class=HTMLResponse)
def index():

    p = FRONTEND / "index.html"

    headers = {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
    }

    if p.exists():
        return HTMLResponse(
            p.read_text(encoding="utf-8"),
            headers=headers
        )

    return HTMLResponse(
        "<h1>Trip Planner</h1>",
        headers=headers
    )


@app.get("/api/health")
def health():

    return {
        "ok": True,
        "openai": settings.has_openai(),
        "weather": settings.has_weather()
    }


@app.get("/api/greeting")
def greeting():

    return {
        "greeting": GREETING
    }


@app.post("/api/chat", response_model=ChatOut)
def chat(payload: ChatIn):

    sid = payload.session_id or uuid.uuid4().hex[:12]

    try:
        result = chat_turn(sid, payload.message or "")

    except Exception as e:

        logger.error(
            "chat_turn crashed (sid=%s):\n%s",
            sid,
            traceback.format_exc()
        )

        return ChatOut(
            session_id=sid,
            reply=f"Internal error: {e.__class__.__name__}: {e}",
            stage="error"
        )

    pdf_url = (
        f"/api/pdf/{Path(result.pdf_path).name}"
        if result.pdf_path else None
    )

    rid = getattr(result, "run_id", None)

    return ChatOut(
        session_id=sid,
        reply=result.reply,
        stage=result.stage,
        pdf_url=pdf_url,
        done=result.done,
        pii_warning=getattr(result, "pii_warning", None),
        run_id=rid,
        run_url=get_run_url(rid) if rid else None,
        guardrail_status=getattr(result, "guardrail_status", None)
    )


@app.get("/api/pdf/{name}")
def get_pdf(name: str):

    safe = Path(name).name

    path = settings.outputs_dir / safe

    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail="PDF not found"
        )

    return FileResponse(
        str(path),
        media_type="application/pdf",
        filename=safe
    )


@app.post("/api/chat/feedback")
def chat_feedback(payload: FeedbackIn):

    """Forward thumbs up/down to LangSmith."""

    ok = send_feedback(
        payload.run_id,
        payload.key,
        payload.score,
        payload.comment or ""
    )

    return {
        "ok": ok,
        "langsmith_enabled": ls_enabled()
    }


@app.get("/api/langsmith/status")
def langsmith_status():

    from tracing import get_project_url

    return {
        "enabled": ls_enabled(),
        "project_url": get_project_url()
    }

# =========================
# Evaluation Routes
# =========================

try:

    from api.evaluation_routes import router as eval_router

    app.include_router(eval_router)

    logger.info("Evaluation routes mounted")

except Exception as e:

    logger.error(
        "Could not mount evaluation routes: %s",
        e
    )

    from fastapi import APIRouter

    fallback = APIRouter()

    @fallback.get("/api/evaluations/summary")
    def _no_summary():

        raise HTTPException(
            status_code=404,
            detail=(
                "Evaluation framework not available. "
                "Make sure api/evaluation_routes.py "
                "and the evaluations/ folder are present."
            )
        )

    app.include_router(fallback)

# =========================
# Main Entry
# =========================

def main():

    import uvicorn

    # Render automatically provides PORT
    port = int(os.environ.get("PORT", 10000))

    print(f"Starting server on 0.0.0.0:{port}")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        reload=False
    )

# =========================
# Start Server
# =========================

if __name__ == "__main__":
    main()