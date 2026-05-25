"""Direct sequential pipeline (LangGraph bypassed for cross-platform stability)."""
from __future__ import annotations
import os, logging
from typing import Any, Dict
from agents import (user_input_agent, memory_retrieval_agent, memory_update_agent,
                    weather_agent, transport_agent, hotel_agent, places_agent,
                    budget_agent, itinerary_agent, final_review_agent,
                    pdf_generator_agent, orchestrator_validation)
from state import TripState

logger = logging.getLogger("trip_planner.graph")


def _merge(s, p):
    if not p: return s
    out = dict(s)
    for k, v in p.items(): out[k] = v
    return out


def run_direct(state: TripState) -> TripState:
    s = dict(state)
    s = _merge(s, user_input_agent(s) or {})
    s = _merge(s, memory_retrieval_agent(s) or {})
    for _ in range(6):
        if not s.get("weather_data"):    s = _merge(s, weather_agent(s) or {})
        if not s.get("places_data"):     s = _merge(s, places_agent(s) or {})
        if not s.get("transport_data"):  s = _merge(s, transport_agent(s) or {})
        if not s.get("hotel_data"):      s = _merge(s, hotel_agent(s) or {})
        if not s.get("budget_summary"):  s = _merge(s, budget_agent(s) or {})
        if not s.get("itinerary"):       s = _merge(s, itinerary_agent(s) or {})
        if not s.get("review_status"):   s = _merge(s, final_review_agent(s) or {})
        v = orchestrator_validation(s) or {}
        s = _merge(s, v)
        if (s.get("orchestrator_decision", {}) or {}).get("approved"):
            break
    s = _merge(s, memory_update_agent(s) or {})
    s = _merge(s, pdf_generator_agent(s) or {})
    return s


def run_workflow(state: TripState) -> TripState:
    return run_direct(state)
