"""FastAPI backend for the Multi-Agent Trip Planner.

Endpoints:
  GET  /                 → chat UI (HTML)
  POST /api/chat         → text chat turn
  POST /api/realtime/session → mint an ephemeral OpenAI Realtime API token
  GET  /api/pdf/{name}   → download a generated trip PDF
  GET  /api/health       → liveness
"""
from __future__ import annotations

import os
import sys
import logging
import traceback
import uuid
from pathlib import Path
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Make ``trip_planner`` package root importable when run via uvicorn
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from chat_flow import chat_turn, GREETING
from config import settings

app = FastAPI(title="Multi-Agent Trip Planner", version="1.0.0")
logger = logging.getLogger("trip_planner")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# Mount frontend statics
FRONTEND = ROOT / "frontend"
if FRONTEND.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND)), name="static")


# ---------- Models ----------
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


class RealtimeSessionOut(BaseModel):
    client_secret: dict
    model: str
    enabled: bool


# ---------- Routes ----------
@app.get("/", response_class=HTMLResponse)
def index():
    index_path = FRONTEND / "index.html"
    if index_path.exists():
        return HTMLResponse(index_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Trip Planner</h1><p>Frontend not found.</p>")


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "openai": settings.has_openai(),
        "weather": settings.has_weather(),
    }


@app.get("/api/greeting")
def greeting():
    return {"greeting": GREETING}


@app.post("/api/chat", response_model=ChatOut)
def chat(payload: ChatIn):
    sid = payload.session_id or uuid.uuid4().hex[:12]
    try:
        result = chat_turn(sid, payload.message or "")
    except Exception as e:
        # Log full traceback to the SERVER CONSOLE so you can see what failed
        tb = traceback.format_exc()
        logger.error("chat_turn crashed (sid=%s):\n%s", sid, tb)
        # Give the BROWSER a useful, human-readable message
        kind = e.__class__.__name__
        msg = str(e) or "no exception message"
        # Friendly response so the UI shows something the user can act on
        return ChatOut(
            session_id=sid,
            reply=(
                "I hit an internal error while processing that message and "
                "couldn't complete your request. The full error is in the "
                "server console.\n\n"
                f"**{kind}**: {msg}\n\n"
                "Tip: try a simpler trip request like *Plan a 3-day Mysore "
                "trip from Bangalore, Rs 15000, train, heritage*."
            ),
            stage="error",
            pdf_url=None,
            done=False,
            pii_warning=None,
        )
    pdf_url = None
    if result.pdf_path:
        pdf_url = f"/api/pdf/{Path(result.pdf_path).name}"
    return ChatOut(
        session_id=sid,
        reply=result.reply,
        stage=result.stage,
        pdf_url=pdf_url,
        done=result.done,
        pii_warning=getattr(result, "pii_warning", None),
    )


@app.get("/api/pdf/{name}")
def get_pdf(name: str):
    # prevent path traversal
    safe = Path(name).name
    path = settings.outputs_dir / safe
    if not path.exists():
        raise HTTPException(status_code=404, detail="PDF not found")
    return FileResponse(
        str(path),
        media_type="application/pdf",
        filename=safe,
    )


@app.post("/api/realtime/session", response_model=RealtimeSessionOut)
def realtime_session():
    """Mint an ephemeral OpenAI Realtime API session token.

    The browser uses this short-lived token to open a WebRTC peer connection
    directly to OpenAI — keeping your real API key on the server.
    """
    if not settings.has_openai():
        # Return a sentinel response so the UI can fall back to text-only
        return RealtimeSessionOut(
            client_secret={"value": "", "expires_at": 0},
            model=settings.realtime_model,
            enabled=False,
        )

    try:
        r = httpx.post(
            "https://api.openai.com/v1/realtime/sessions",
            headers={
                "Authorization": f"Bearer {settings.openai_api_key}",
                "Content-Type": "application/json",
                "OpenAI-Beta": "realtime=v1",
            },
            json={
                "model": settings.realtime_model,
                "voice": "alloy",
                "instructions": (
                    "You are a friendly AI Trip Planner. Begin by saying hello and asking "
                    "how you can help. When the user describes a trip, always check the "
                    "weather first, then suggest places based on what you find. Help the "
                    "user finalize details (source, destination, dates, budget, interests). "
                    "When the plan is complete, tell the user a PDF will be generated and "
                    "end with 'thank you, happy journey!' Keep replies concise."
                ),
            },
            timeout=20,
        )
        r.raise_for_status()
        data = r.json()
        return RealtimeSessionOut(
            client_secret=data.get("client_secret", {}),
            model=data.get("model", settings.realtime_model),
            enabled=True,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Realtime session failed: {e}")


def main():
    import uvicorn
    uvicorn.run("api.server:app", host=settings.host, port=settings.port, reload=False)


if __name__ == "__main__":
    main()
