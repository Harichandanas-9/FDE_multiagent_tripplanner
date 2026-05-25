from __future__ import annotations
from typing import Any, Dict, List
from state import TripState


def final_review_agent(state: TripState) -> Dict[str, Any]:
    issues: List[str] = []; approved = True
    p = state.get("trip_preferences", {})
    if not p.get("destination"): issues.append("Destination missing"); approved = False
    if not state.get("weather_data"): issues.append("Weather missing"); approved = False
    if not state.get("hotel_data", {}).get("options"): issues.append("Hotel missing"); approved = False
    if not state.get("transport_data", {}).get("recommended"): issues.append("Transport missing"); approved = False
    if not state.get("itinerary", {}).get("days"): issues.append("Itinerary missing"); approved = False
    budget = state.get("budget_summary", {})
    review = {"approved": approved, "issues": issues, "needs_retry": []}
    if budget and budget.get("overshoot", 0) > 0.25 * float(p.get("budget") or 1):
        review["needs_retry"].append("hotel")
    return {"review_status": review}
