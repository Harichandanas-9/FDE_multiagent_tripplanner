"""Shared LLM helper. Falls back to heuristic when OpenAI is unavailable."""
from __future__ import annotations
import json
from typing import Any, Optional
from config import settings

try:
    from openai import OpenAI
    _HAS_OPENAI = True
except Exception:
    _HAS_OPENAI = False

_client: Optional[Any] = None
_client_init_failed: bool = False


def get_client():
    global _client, _client_init_failed
    if _client_init_failed:
        return None
    if not (_HAS_OPENAI and settings.has_openai()):
        return None
    if _client is None:
        try:
            _client = OpenAI(api_key=settings.openai_api_key)
        except Exception:
            _client_init_failed = True
            return None
    return _client


def chat_json(system: str, user: str, fallback: Any) -> Any:
    try:
        client = get_client()
        if client is None:
            return fallback
        resp = client.chat.completions.create(
            model=settings.chat_model,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
            response_format={"type": "json_object"},
            temperature=0.4,
        )
        return json.loads(resp.choices[0].message.content)
    except Exception:
        return fallback


def chat_text(system: str, user: str, fallback: str = "") -> str:
    try:
        client = get_client()
        if client is None:
            return fallback
        resp = client.chat.completions.create(
            model=settings.chat_model,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
            temperature=0.5,
        )
        return resp.choices[0].message.content or fallback
    except Exception:
        return fallback
