from __future__ import annotations
from typing import Any, Dict
from state import TripState
from tools.weather_api import get_weather_forecast, is_weather_favourable


def weather_agent(state: TripState) -> Dict[str, Any]:
    prefs = state.get("trip_preferences", {})
    dest = prefs.get("destination")
    if not dest: return {"weather_data": {}}
    days = prefs.get("duration_days") or 5
    f = get_weather_forecast(dest, days=days)
    f["assessment"] = is_weather_favourable(f)
    return {"weather_data": f}
