from __future__ import annotations
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List
from state import TripState
from ._llm import chat_json

SYSTEM = """You are a travel itinerary planner. Output JSON:
{"days":[{"day":1,"date":"...","title":"...","morning":"...","afternoon":"...","evening":"...","meals":["..."],"notes":"..."}]}"""


def _heuristic(state):
    p = state.get("trip_preferences", {})
    days = int(p.get("duration_days") or 3)
    start = p.get("start_date")
    try:
        sdt = datetime.strptime(start, "%Y-%m-%d") if start else datetime.utcnow() + timedelta(days=14)
    except Exception:
        sdt = datetime.utcnow() + timedelta(days=14)
    attractions = (state.get("places_data", {}) or {}).get("destination_info", {}).get("attractions", [])
    weather_days = (state.get("weather_data", {}) or {}).get("forecast", [])
    food = (state.get("places_data", {}) or {}).get("destination_info", {}).get("local_food", [])
    out = []
    for i in range(days):
        date = (sdt + timedelta(days=i)).strftime("%Y-%m-%d")
        w = weather_days[i] if i < len(weather_days) else {}
        rainy = w.get("rain_mm", 0) > 5
        morn = attractions[i % max(1, len(attractions))]["name"] if attractions else "Local"
        evn = attractions[(i+1) % max(1, len(attractions))]["name"] if attractions else "Stroll"
        out.append({
            "day": i+1, "date": date,
            "title": f"Day {i+1} in {p.get('destination', '')}",
            "morning": f"Visit {morn}" + (" (indoor alt)" if rainy else ""),
            "afternoon": "Lunch + relaxed sightseeing" if rainy else "Outdoor activity",
            "evening": f"Explore {evn}",
            "meals": food[:3] if food else ["Local cuisine"],
            "notes": "Carry umbrella" if rainy else "Light layers",
        })
    return {"days": out}


def itinerary_agent(state: TripState) -> Dict[str, Any]:
    fb = _heuristic(state)
    res = chat_json(SYSTEM, json.dumps({
        "preferences": state.get("trip_preferences", {}),
        "weather": state.get("weather_data", {}),
        "places": state.get("places_data", {}),
    }), fb)
    if not res or "days" not in res or not res["days"]:
        res = fb
    return {"itinerary": res}
