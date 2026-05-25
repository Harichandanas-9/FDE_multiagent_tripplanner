"""Hotel search - mock with bands."""
from __future__ import annotations
import random
from typing import Any, Dict, List

PRICE_BANDS = {"budget": (1200, 2800), "mid": (3000, 6000), "luxury": (8000, 22000)}

HOTEL_POOL = {
    "goa": [("Taj Fort Aguada","luxury",4.7),("Acron Waterfront","mid",4.4),
            ("Whispering Palms","mid",4.3),("Zostel Goa","budget",4.2)],
    "jaipur": [("Rambagh Palace","luxury",4.8),("Pearl Palace","mid",4.5),
               ("Zostel Jaipur","budget",4.3)],
    "manali": [("The Himalayan","luxury",4.6),("Apple Country Resort","mid",4.4),
               ("Zostel Old Manali","budget",4.3)],
    "kerala": [("Kumarakom Lake Resort","luxury",4.7),("Spice Tree Munnar","mid",4.5),
               ("Zostel Kochi","budget",4.2)],
    "mysore": [("Radisson Blu Plaza","luxury",4.6),("Hotel Pai Vista","mid",4.4),
                ("Zostel Mysore","budget",4.2)],
    "coorg": [("Taj Madikeri","luxury",4.7),("Club Mahindra","mid",4.4),
              ("Zostel Coorg","budget",4.1)],
    "ooty": [("Savoy Hotel","luxury",4.6),("Sterling Ooty","mid",4.3),
             ("Zostel Ooty","budget",4.2)],
}


def search_hotels(city, nights, travelers=2, band="mid"):
    pool = HOTEL_POOL.get(city.lower().strip(),
                          [(f"{city.title()} Grand","luxury",4.5),
                           (f"{city.title()} City Inn","mid",4.3),
                           (f"{city.title()} Backpackers","budget",4.1)])
    band = band if band in PRICE_BANDS else "mid"
    lo, hi = PRICE_BANDS[band]
    options = []
    for name, hb, rating in pool:
        if hb == band or band == "mid":
            per = random.randint(lo, hi)
            options.append({"name": name, "band": hb, "rating": rating,
                            "per_night": per, "nights": nights,
                            "total": per * nights, "currency": "INR",
                            "amenities": ["WiFi","AC","Breakfast"] +
                                         (["Pool","Spa"] if hb == "luxury" else [])})
    options.sort(key=lambda x: x["per_night"])
    return {"city": city.title(), "nights": nights, "travelers": travelers, "band": band,
            "options": options[:5],
            "recommended": options[len(options)//2] if options else None}
