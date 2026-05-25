"""Places/attractions - Google Places + curated catalog fallback."""
from __future__ import annotations
from typing import Any, Dict, List
import httpx
from config import settings


DESTINATION_CATALOG: Dict[str, Dict[str, Any]] = {
    "goa": {"tagline": "Beaches, nightlife and Portuguese heritage",
            "best_for": ["beach","nightlife","seafood","couple","watersports"],
            "season": "Nov-Feb",
            "attractions": [{"name":"Baga Beach","type":"Beach","rating":4.4},
                            {"name":"Calangute Beach","type":"Beach","rating":4.3},
                            {"name":"Dudhsagar Falls","type":"Nature","rating":4.6},
                            {"name":"Old Goa Churches","type":"Heritage","rating":4.5},
                            {"name":"Anjuna Flea Market","type":"Shopping","rating":4.2}],
            "local_food": ["Goan fish curry","Prawn balchao","Bebinca","Feni"]},
    "jaipur": {"tagline": "The Pink City - palaces and Rajasthani culture",
               "best_for": ["heritage","family","photography","shopping"],
               "season": "Oct-Mar",
               "attractions": [{"name":"Amber Fort","type":"Heritage","rating":4.6},
                               {"name":"Hawa Mahal","type":"Heritage","rating":4.4},
                               {"name":"City Palace","type":"Heritage","rating":4.5},
                               {"name":"Jantar Mantar","type":"Heritage","rating":4.4}],
               "local_food": ["Dal baati churma","Laal maas","Pyaaz kachori"]},
    "manali": {"tagline": "Snow, mountains and adventure",
               "best_for": ["mountains","snow","adventure","honeymoon"],
               "season": "Dec-Feb / Apr-Jun",
               "attractions": [{"name":"Solang Valley","type":"Adventure","rating":4.5},
                               {"name":"Rohtang Pass","type":"Mountain","rating":4.6},
                               {"name":"Hadimba Temple","type":"Temple","rating":4.4}],
               "local_food": ["Trout fish","Siddu","Madra"]},
    "kerala": {"tagline": "Backwaters, beaches and hill stations",
               "best_for": ["honeymoon","nature","ayurveda","family"],
               "season": "Sep-Mar",
               "attractions": [{"name":"Alleppey Backwaters","type":"Nature","rating":4.7},
                               {"name":"Munnar Tea Estates","type":"Hills","rating":4.6},
                               {"name":"Kovalam Beach","type":"Beach","rating":4.3},
                               {"name":"Fort Kochi","type":"Heritage","rating":4.4}],
               "local_food": ["Appam with stew","Karimeen pollichathu","Sadya"]},
    "paris": {"tagline": "City of light, art and romance",
              "best_for": ["couple","art","honeymoon","city"],
              "season": "Apr-Jun, Sep-Oct",
              "attractions": [{"name":"Eiffel Tower","type":"Landmark","rating":4.7},
                              {"name":"Louvre Museum","type":"Museum","rating":4.7},
                              {"name":"Notre-Dame","type":"Heritage","rating":4.6}],
              "local_food": ["Croissant","Coq au vin","Macarons"]},
    "mysore": {"tagline": "City of palaces - Karnataka heritage",
               "best_for": ["heritage","family","palace","temple","shopping"],
               "season": "Oct-Mar",
               "attractions": [{"name":"Mysore Palace","type":"Heritage","rating":4.7},
                               {"name":"Chamundi Hills","type":"Temple","rating":4.5},
                               {"name":"Brindavan Gardens","type":"Garden","rating":4.3},
                               {"name":"St. Philomena's Cathedral","type":"Heritage","rating":4.4},
                               {"name":"Mysore Zoo","type":"Wildlife","rating":4.4}],
               "local_food": ["Mysore Pak","Mysore Masala Dosa","Bisi Bele Bath"]},
    "coorg": {"tagline": "Scotland of India - coffee plantations",
              "best_for": ["nature","couple","honeymoon","mountains"],
              "season": "Oct-Mar",
              "attractions": [{"name":"Abbey Falls","type":"Nature","rating":4.5},
                              {"name":"Raja's Seat","type":"Viewpoint","rating":4.4},
                              {"name":"Dubare Elephant Camp","type":"Wildlife","rating":4.5}],
              "local_food": ["Pandi curry","Akki roti","Coorg coffee"]},
    "ooty": {"tagline": "Queen of hill stations",
             "best_for": ["family","honeymoon","mountains","nature"],
             "season": "Mar-Jun, Sep-Nov",
             "attractions": [{"name":"Ooty Lake","type":"Lake","rating":4.3},
                             {"name":"Botanical Gardens","type":"Garden","rating":4.4},
                             {"name":"Doddabetta Peak","type":"Viewpoint","rating":4.5}],
             "local_food": ["Varkey","Avial"]},
}


def _mock_attractions(city: str) -> Dict[str, Any]:
    key = city.lower().strip()
    if key in DESTINATION_CATALOG:
        return {"source": "catalog", "city": city.title(), **DESTINATION_CATALOG[key]}
    return {"source": "catalog-generic", "city": city.title(),
            "tagline": f"Highlights of {city.title()}",
            "best_for": ["sightseeing"], "season": "Year-round",
            "attractions": [{"name": f"{city.title()} Main Square", "type":"City", "rating":4.2},
                            {"name": f"{city.title()} Museum", "type":"Museum", "rating":4.1}],
            "local_food": []}


def get_attractions(city: str) -> Dict[str, Any]:
    if not settings.google_places_api_key:
        return _mock_attractions(city)
    try:
        r = httpx.get("https://maps.googleapis.com/maps/api/place/textsearch/json",
                       params={"query": f"top tourist attractions in {city}",
                               "key": settings.google_places_api_key}, timeout=15)
        r.raise_for_status()
        items = r.json().get("results", [])[:6]
        mock = _mock_attractions(city)
        return {"source": "google_places", "city": city.title(),
                "attractions": [{"name": p.get("name"),
                                  "type": ", ".join(p.get("types", [])[:2]),
                                  "rating": p.get("rating", 0)} for p in items],
                "local_food": mock.get("local_food", []),
                "best_for": mock.get("best_for", []),
                "season": mock.get("season", "Year-round"),
                "tagline": mock.get("tagline", f"Discover {city.title()}")}
    except Exception:
        return _mock_attractions(city)


def suggest_places(interests: List[str], season_hint: str = None) -> List[Dict[str, Any]]:
    il = [i.lower() for i in (interests or [])]
    ranked, seen = [], set()
    for slug, info in DESTINATION_CATALOG.items():
        title = slug.title()
        if title.lower() in seen: continue
        seen.add(title.lower())
        score = sum(1 for i in il if any(i in tag for tag in info["best_for"]))
        ranked.append({"city": title, "tagline": info["tagline"], "score": score,
                       "season": info["season"],
                       "highlights": [a["name"] for a in info["attractions"][:3]]})
    ranked.sort(key=lambda x: x["score"], reverse=True)
    return ranked[:5]
