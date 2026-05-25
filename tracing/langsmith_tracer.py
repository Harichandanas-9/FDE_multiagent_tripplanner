"""Optional LangSmith tracing.

If `langsmith` is installed AND env var `LANGSMITH_API_KEY` is set, every
@traceable function gets logged to LangSmith. Otherwise these decorators
are no-ops — the project runs identically with zero overhead.

Environment variables:
  LANGSMITH_API_KEY      - your LangSmith key (required to enable)
  LANGSMITH_PROJECT      - project name (default "trip-planner")
  LANGSMITH_ENDPOINT     - API endpoint (default https://api.smith.langchain.com)
"""
from __future__ import annotations
import logging
import os
from typing import Any, Callable, Optional

logger = logging.getLogger("trip_planner.tracing")

LANGSMITH_API_KEY  = os.environ.get("LANGSMITH_API_KEY", "")
LANGSMITH_PROJECT  = os.environ.get("LANGSMITH_PROJECT", "trip-planner")
LANGSMITH_ENDPOINT = os.environ.get("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")

# Try to import langsmith
try:
    from langsmith import Client as _Client
    from langsmith import traceable as _ls_traceable
    try:
        from langsmith.run_helpers import get_current_run_tree as _get_run_tree
    except ImportError:
        from langsmith import get_current_run_tree as _get_run_tree
    _HAS_LANGSMITH = True
except Exception as e:
    _HAS_LANGSMITH = False
    logger.info("LangSmith not available (%s) - tracing disabled.", e)

_client: Optional[Any] = None
_client_failed = False


def is_enabled() -> bool:
    """Return True if LangSmith is installed AND API key is set."""
    return bool(_HAS_LANGSMITH and LANGSMITH_API_KEY)


def _ensure_env():
    """Set the LangChain env vars LangSmith expects."""
    if is_enabled():
        os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
        os.environ.setdefault("LANGCHAIN_API_KEY", LANGSMITH_API_KEY)
        os.environ.setdefault("LANGCHAIN_PROJECT", LANGSMITH_PROJECT)
        os.environ.setdefault("LANGCHAIN_ENDPOINT", LANGSMITH_ENDPOINT)


def get_client():
    """Lazy-init LangSmith client. Returns None if disabled or init fails."""
    global _client, _client_failed
    if _client_failed or not is_enabled():
        return None
    if _client is None:
        try:
            _ensure_env()
            _client = _Client(api_url=LANGSMITH_ENDPOINT, api_key=LANGSMITH_API_KEY)
            logger.info("LangSmith client initialised - project '%s'", LANGSMITH_PROJECT)
        except Exception as e:
            _client_failed = True
            logger.warning("LangSmith client init failed: %s", e)
            return None
    return _client


def traceable(name: Optional[str] = None, **kw):
    """Decorator. Real LangSmith @traceable if enabled, no-op otherwise.

    Usage:
        @traceable(name="my-agent")
        def my_agent(state): ...
    """
    # If the user used it bare like @traceable (no parens), Python passes the
    # function as the first arg. Handle that case too.
    if callable(name):
        fn = name
        if is_enabled():
            _ensure_env()
            return _ls_traceable()(fn)
        return fn
    # Parenthesised: @traceable(name="X")
    def decorator(fn):
        if is_enabled():
            _ensure_env()
            return _ls_traceable(name=name or fn.__name__, **kw)(fn)
        return fn
    return decorator


def capture_run_id() -> Optional[str]:
    """Return the current LangSmith run id (or None if not in a traced run)."""
    if not is_enabled():
        return None
    try:
        tree = _get_run_tree()
        return str(tree.id) if tree else None
    except Exception:
        return None


def send_feedback(run_id: str, key: str, score: float, comment: str = "") -> bool:
    """Attach a feedback record (e.g. thumbs up/down) to a LangSmith run."""
    c = get_client()
    if not c or not run_id:
        return False
    try:
        c.create_feedback(run_id=run_id, key=key, score=score, comment=comment or None)
        return True
    except Exception as e:
        logger.warning("LangSmith feedback failed: %s", e)
        return False


def get_project_url() -> Optional[str]:
    """Best-effort URL to the LangSmith project dashboard."""
    if not is_enabled():
        return None
    return f"https://smith.langchain.com/o/-/projects/p/{LANGSMITH_PROJECT}"


def get_run_url(run_id: str) -> Optional[str]:
    """Best-effort URL to a specific run."""
    if not is_enabled() or not run_id:
        return None
    return f"https://smith.langchain.com/o/-/projects/p/{LANGSMITH_PROJECT}/r/{run_id}"
