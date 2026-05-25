"""Flight/train search - mock with realistic numbers."""
from __future__ import annotations
import random
from typing import Any, Dict, List


ROUTE_DISTANCES = {
    ("bangalore","goa"):560,("bengaluru","goa"):560,("mumbai","goa"):590,
    ("delhi","jaipur"):280,("delhi","manali"):540,("chennai","kerala"):700,
    ("bangalore","mysore"):150,("bengaluru","mysore"):150,
    ("bangalore","ooty"):270,("bangalore","coorg"):250,
}


def _distance_km(s, d):
    k = (s.lower().strip(), d.lower().strip())
    if k in ROUTE_DISTANCES: return ROUTE_DISTANCES[k]
    if (k[1], k[0]) in ROUTE_DISTANCES: return ROUTE_DISTANCES[(k[1], k[0])]
    return 800


def search_flights(source, dest, date, travelers=1):
    dist = _distance_km(source, dest)
    base = max(2500, int(dist * random.uniform(4.0, 6.5)))
    airlines = ["IndiGo","Vistara","Air India","Akasa Air","SpiceJet"]
    options = []
    for i, a in enumerate(airlines[:3]):
        price = int(base * random.uniform(0.85, 1.25))
        options.append({"airline": a, "flight_no": f"{a[:2].upper()}-{random.randint(100,999)}",
                        "depart": f"{6+i*3:02d}:{random.randint(0,5)}0",
                        "arrive": f"{8+i*3:02d}:{random.randint(0,5)}0",
                        "duration": f"{1+dist//800}h {random.randint(0,50):02d}m",
                        "stops": 0 if i < 2 else 1,
                        "price_per_person": price, "total_price": price * travelers,
                        "currency": "INR"})
    options.sort(key=lambda x: x["price_per_person"])
    return {"source_city": source.title(), "dest_city": dest.title(), "date": date,
            "options": options, "cheapest": options[0]}


def search_trains(source, dest, date, travelers=1):
    dist = _distance_km(source, dest)
    base_3a = max(800, int(dist * 1.4))
    options = [{"name": f"{source.title()}-{dest.title()} Express",
                "number": f"{random.randint(12000,22999)}", "class": "3A",
                "depart": "20:30", "arrive": "08:45",
                "duration": f"{8+dist//200}h",
                "price_per_person": base_3a, "total_price": base_3a*travelers,
                "currency": "INR"},
               {"name": "Rajdhani Express", "number": f"{random.randint(12000,22999)}",
                "class": "2A", "depart": "16:50", "arrive": "06:20",
                "duration": f"{7+dist//200}h",
                "price_per_person": int(base_3a*1.6),
                "total_price": int(base_3a*1.6)*travelers, "currency": "INR"}]
    return {"source_city": source.title(), "dest_city": dest.title(), "date": date,
            "options": options, "cheapest": options[0]}
