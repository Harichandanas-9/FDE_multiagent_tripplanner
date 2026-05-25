"""OpenWeatherMap integration with mock fallback."""
from __future__ import annotations
from datetime import datetime, timedelta
from typing import Any, Dict, List
import httpx
from config import settings


def _mock_forecast(city: str, days: int) -> Dict[str, Any]:
    base = datetime.utcnow()
    presets = ["Sunny", "Partly cloudy", "Light rain", "Cloudy", "Clear", "Showers"]
    return {
        "source": "mock", "city": city,
        "forecast": [{
            "date": (base + timedelta(days=i)).strftime("%Y-%m-%d"),
            "summary": presets[i % len(presets)],
            "temp_min_c": 22 + (i % 3), "temp_max_c": 30 + (i % 4),
            "humidity": 60 + (i % 20),
            "rain_mm": 0 if i % 3 else 5,
        } for i in range(days)],
        "alerts": [],
    }


def get_weather_forecast(city: str, days: int = 5) -> Dict[str, Any]:
    if not settings.has_weather():
        return _mock_forecast(city, days)
    try:
        g = httpx.get("https://api.openweathermap.org/geo/1.0/direct",
                       params={"q": city, "limit": 1, "appid": settings.openweather_api_key},
                       timeout=10)
        g.raise_for_status()
        gd = g.json()
        if not gd: return _mock_forecast(city, days)
        r = httpx.get("https://api.openweathermap.org/data/2.5/forecast",
                       params={"lat": gd[0]["lat"], "lon": gd[0]["lon"],
                               "appid": settings.openweather_api_key, "units": "metric"},
                       timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception:
        return _mock_forecast(city, days)
    by_day = {}
    for e in data.get("list", []):
        d = e["dt_txt"].split(" ")[0]
        by_day.setdefault(d, []).append(e)
    daily = []
    for d, entries in list(by_day.items())[:days]:
        temps = [e["main"]["temp"] for e in entries]
        rains = [e.get("rain", {}).get("3h", 0) for e in entries]
        daily.append({
            "date": d,
            "summary": entries[len(entries)//2]["weather"][0]["description"].title(),
            "temp_min_c": round(min(temps), 1), "temp_max_c": round(max(temps), 1),
            "humidity": int(sum(e["main"]["humidity"] for e in entries) / len(entries)),
            "rain_mm": round(sum(rains), 1),
        })
    return {"source": "openweathermap", "city": data.get("city", {}).get("name", city),
            "forecast": daily, "alerts": []}


def is_weather_favourable(f: Dict[str, Any]) -> Dict[str, Any]:
    days = f.get("forecast", [])
    rainy = sum(1 for d in days if d.get("rain_mm", 0) >= 4)
    hot = sum(1 for d in days if d.get("temp_max_c", 0) >= 38)
    v = "good"
    if rainy >= max(1, len(days)//2): v = "rainy"
    elif hot >= max(1, len(days)//2): v = "very_hot"
    return {"verdict": v, "rainy_days": rainy, "hot_days": hot}
