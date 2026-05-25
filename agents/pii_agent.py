"""LangGraph node: PII guardrail."""
from __future__ import annotations
from typing import Any, Dict, List
from langchain_core.messages import HumanMessage
from state import TripState
from tools.guardrails import redact, redact_dict, summarise


def pii_guardrail_agent(state: TripState) -> Dict[str, Any]:
    updates: Dict[str, Any] = {}
    messages = list(state.get("messages", []) or [])
    all_hits: List[Any] = []
    new_messages = []
    for m in messages:
        if isinstance(m, HumanMessage) and isinstance(m.content, str):
            cleaned, hits = redact(m.content)
            if hits:
                all_hits.extend(hits)
                m = HumanMessage(content=cleaned)
        new_messages.append(m)
    if all_hits:
        updates["messages"] = new_messages
    prefs = state.get("trip_preferences", {}) or {}
    if prefs:
        updates["trip_preferences"] = redact_dict(prefs)
    if all_hits:
        decision = dict(state.get("orchestrator_decision", {}) or {})
        decision["pii_warning"] = (
            "I noticed " + summarise(all_hits) + " in your message; "
            "redacted before processing."
        )
        updates["orchestrator_decision"] = decision
    return updates
