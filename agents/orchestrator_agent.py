"""Orchestrator agent — budget-fit retries + decision routing."""
from __future__ import annotations
from typing import Any, Dict
from state import TripState

MAX_RETRIES = 4


def orchestrator_agent(state: TripState) -> Dict[str, Any]:
    p = state.get("trip_preferences", {})
    missing = [k for k in ("source", "destination") if not p.get(k)]
    decision: Dict[str, Any] = {
        "stage": state.get("conversation_stage", "greet"),
        "missing_inputs": missing,
    }
    if missing:
        decision["next"] = "await_user_input"
    elif not state.get("weather_data"):    decision["next"] = "weather"
    elif not state.get("places_data"):     decision["next"] = "places"
    elif not state.get("transport_data"):  decision["next"] = "transport"
    elif not state.get("hotel_data"):      decision["next"] = "hotel"
    elif not state.get("budget_summary"):  decision["next"] = "budget"
    elif not state.get("itinerary"):       decision["next"] = "itinerary"
    elif not state.get("review_status"):   decision["next"] = "review"
    else:                                   decision["next"] = "validate"
    return {"orchestrator_decision": decision}


def _downgrade_hotel(prefs):
    new = dict(prefs)
    band = new.get("hotel_pref", "mid")
    if band == "luxury": new["hotel_pref"] = "mid"
    elif band == "mid":  new["hotel_pref"] = "budget"
    return new


def orchestrator_validation(state: TripState) -> Dict[str, Any]:
    review = dict(state.get("review_status", {}) or {})
    decision = dict(state.get("orchestrator_decision", {}) or {})
    retries = dict(state.get("retry_counts", {}) or {})
    prefs = dict(state.get("trip_preferences", {}) or {})
    budget = state.get("budget_summary", {}) or {}
    needs = list(review.get("needs_retry", []) or [])

    if budget and not budget.get("within_budget", True):
        if prefs.get("hotel_pref") in ("luxury", "mid") and retries.get("hotel", 0) < MAX_RETRIES:
            new_prefs = _downgrade_hotel(prefs)
            retries["hotel"] = retries.get("hotel", 0) + 1
            decision["next"] = "hotel"; decision["retry"] = "hotel"
            return {"trip_preferences": new_prefs, "hotel_data": {}, "budget_summary": {},
                    "review_status": {}, "retry_counts": retries,
                    "orchestrator_decision": decision}
        if prefs.get("transport_pref") == "flight" and retries.get("transport", 0) < MAX_RETRIES:
            new_prefs = dict(prefs); new_prefs["transport_pref"] = "train"
            retries["transport"] = retries.get("transport", 0) + 1
            decision["next"] = "transport"; decision["retry"] = "transport"
            return {"trip_preferences": new_prefs, "transport_data": {}, "budget_summary": {},
                    "review_status": {}, "retry_counts": retries,
                    "orchestrator_decision": decision}

    wassess = (state.get("weather_data", {}) or {}).get("assessment", {})
    if wassess.get("verdict") == "rainy" and retries.get("places", 0) < 1:
        retries["places"] = retries.get("places", 0) + 1
        decision["next"] = "places"; decision["retry"] = "places"
        return {"places_data": {}, "retry_counts": retries,
                "orchestrator_decision": decision}

    for agent in needs:
        if retries.get(agent, 0) < MAX_RETRIES:
            retries[agent] = retries.get(agent, 0) + 1
            clear = {"hotel": "hotel_data", "places": "places_data",
                     "transport": "transport_data", "itinerary": "itinerary",
                     "budget": "budget_summary", "weather": "weather_data"}
            upd = {"review_status": {}, "retry_counts": retries,
                   "orchestrator_decision": {**decision, "next": agent, "retry": agent}}
            if agent in clear: upd[clear[agent]] = {}
            return upd

    decision["next"] = "memory_update"; decision["approved"] = True
    review["approved"] = True
    return {"review_status": review, "orchestrator_decision": decision}


def decide_next(state: TripState) -> str:
    return (state.get("orchestrator_decision", {}) or {}).get("next", "validate")
