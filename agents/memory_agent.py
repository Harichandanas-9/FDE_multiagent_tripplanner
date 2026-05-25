"""Memory retrieval and update agents."""
from __future__ import annotations
from typing import Any, Dict
from memory import get_vector_memory
from tools.guardrails import redact
from state import TripState


def memory_retrieval_agent(state: TripState) -> Dict[str, Any]:
    prefs = state.get("trip_preferences", {})
    parts = [prefs.get("destination", ""), prefs.get("travel_type", ""),
             " ".join(prefs.get("interests", []) or [])]
    query = " ".join(p for p in parts if p).strip()
    if not query:
        return {"memory_hits": []}
    return {"memory_hits": get_vector_memory().search(query, k=3)}


def memory_update_agent(state: TripState) -> Dict[str, Any]:
    prefs = state.get("trip_preferences", {})
    if not prefs.get("destination"):
        return {}
    uid = state.get("user_profile", {}).get("user_id", "guest")
    summary = (
        f"User {uid} planned a {prefs.get('duration_days','?')}-day "
        f"{prefs.get('travel_type','trip')} to {prefs.get('destination')} "
        f"from {prefs.get('source','?')}, budget {prefs.get('budget','?')}, "
        f"interests: {', '.join(prefs.get('interests', []) or [])}"
    )
    summary, _ = redact(summary)
    get_vector_memory().add(summary, {"user_id": uid, "prefs": prefs})
    return {}
