from __future__ import annotations
from typing import Any, Dict
from state import TripState
from tools.places_api import get_attractions, suggest_places


def places_agent(state: TripState) -> Dict[str, Any]:
    p = state.get("trip_preferences", {})
    dest = p.get("destination", "")
    info = get_attractions(dest) if dest else {}
    return {"places_data": {"destination_info": info,
                             "alt_suggestions": suggest_places(p.get("interests", []) or [])}}
