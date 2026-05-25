from __future__ import annotations
from typing import Any, Dict
from state import TripState
from tools.transport_api import search_flights, search_trains


def transport_agent(state: TripState) -> Dict[str, Any]:
    p = state.get("trip_preferences", {})
    src, dest = p.get("source") or "Bangalore", p.get("destination", "")
    if not dest: return {"transport_data": {}}
    date = p.get("start_date") or "2026-06-01"
    travelers = int(p.get("travelers") or 1)
    mode = p.get("transport_pref", "flight").lower()
    flights = search_flights(src, dest, date, travelers)
    trains = search_trains(src, dest, date, travelers)
    rec = flights["cheapest"] if mode == "flight" else trains["cheapest"]
    return {"transport_data": {"preferred_mode": mode, "flights": flights,
                               "trains": trains, "recommended": rec}}
