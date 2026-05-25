from __future__ import annotations
from typing import Any, Dict
from state import TripState
from tools.budget_calc import optimize_budget


def budget_agent(state: TripState) -> Dict[str, Any]:
    p = state.get("trip_preferences", {})
    days = int(p.get("duration_days") or 3)
    travelers = int(p.get("travelers") or 1)
    budget = float(p.get("budget") or 25000)
    rec_tr = (state.get("transport_data", {}) or {}).get("recommended", {})
    transport_cost = float(rec_tr.get("total_price", 0)) * 2
    hd = state.get("hotel_data", {}) or {}
    rec_h = hd.get("recommended") or (hd.get("options", [{}])[0] if hd.get("options") else {})
    hotel_cost = float(rec_h.get("total", 0))
    return {"budget_summary": optimize_budget(budget, transport_cost, hotel_cost, travelers, days)}
