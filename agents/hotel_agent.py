from __future__ import annotations
from typing import Any, Dict
from state import TripState
from tools.hotel_api import search_hotels


def hotel_agent(state: TripState) -> Dict[str, Any]:
    p = state.get("trip_preferences", {})
    dest = p.get("destination", "")
    if not dest: return {"hotel_data": {}}
    nights = max(1, int(p.get("duration_days") or 3) - 1)
    return {"hotel_data": search_hotels(dest, nights=nights,
                                          travelers=int(p.get("travelers") or 1),
                                          band=p.get("hotel_pref", "mid"))}
