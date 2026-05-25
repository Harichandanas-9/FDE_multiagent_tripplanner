"""In-memory session store."""
from __future__ import annotations
import threading, time
from typing import Any, Dict, Optional


class SessionMemory:
    def __init__(self):
        self._store: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def get(self, sid: str) -> Dict[str, Any]:
        with self._lock:
            return self._store.setdefault(sid,
                {"created_at": time.time(), "history": [], "state": {}})

    def update_state(self, sid: str, state: Dict[str, Any]):
        with self._lock:
            s = self._store.setdefault(sid,
                {"created_at": time.time(), "history": [], "state": {}})
            s["state"] = state; s["updated_at"] = time.time()

    def append_history(self, sid: str, role: str, content: str):
        with self._lock:
            s = self._store.setdefault(sid,
                {"created_at": time.time(), "history": [], "state": {}})
            s["history"].append({"role": role, "content": content, "ts": time.time()})

    def clear(self, sid: str):
        with self._lock: self._store.pop(sid, None)


_singleton: Optional[SessionMemory] = None


def get_session_memory() -> SessionMemory:
    global _singleton
    if _singleton is None: _singleton = SessionMemory()
    return _singleton
