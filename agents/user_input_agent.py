"""Agent 1: User Input parser."""
from __future__ import annotations
import re
from datetime import datetime, timedelta
from typing import Any, Dict
from state import TripState
from ._llm import chat_json

SYSTEM = """Extract trip preferences as JSON: source, destination, start_date, end_date,
duration_days, budget, currency, travelers, travel_type, hotel_pref, food_pref,
transport_pref, interests, luxury_level. Return ONLY JSON."""

_DURATION_RE = re.compile(r"(\d+)\s*[- ]?day", re.I)
_BUDGET_RE = re.compile(r"(?:budget\s*[:=]?\s*)?(?:rs\.?|inr|usd|\$|₹)\s*([\d,]+)", re.I)

KNOWN_CITIES = [
    "goa","jaipur","manali","kerala","paris","mumbai","delhi","bangalore","bengaluru",
    "chennai","kochi","hyderabad","pune","kolkata","agra","udaipur","shimla","ooty",
    "darjeeling","rishikesh","varanasi","amritsar","mysore","mysuru","coorg","madikeri",
    "wayanad","munnar","alleppey","alappuzha","thekkady","thiruvananthapuram","trivandrum",
    "pondicherry","puducherry","mahabaleshwar","lonavala","khandala","matheran","panchgani",
    "nashik","ahmedabad","jodhpur","jaisalmer","pushkar","ajmer","ranthambore","leh","ladakh",
    "srinagar","gulmarg","pahalgam","sonmarg","kasol","kullu","spiti","dharamshala",
    "mcleodganj","dalhousie","kasauli","nainital","mussoorie","haridwar","dehradun","auli",
    "jim corbett","ranikhet","almora","kausani","binsar","tirupati","rameshwaram",
    "kanyakumari","madurai","thanjavur","kodaikanal","yercaud","hampi","badami","gokarna",
    "karwar","puri","konark","bhubaneswar","gangtok","pelling","lachung","shillong",
    "cherrapunji","kaziranga","tawang","andaman","port blair","havelock","lakshadweep",
    "london","new york","tokyo","dubai","singapore","bali","bangkok","phuket","kathmandu",
    "pokhara","colombo","kandy",
]


def _find_city(text: str, exclude: str = "") -> str:
    t = text.lower()
    for city in sorted(KNOWN_CITIES, key=len, reverse=True):
        if city == exclude: continue
        if re.search(rf"\b{re.escape(city)}\b", t):
            return city.title()
    return ""


def _parse_relative_dates(text: str):
    t = text.lower()
    today = datetime.utcnow().date()
    start = None
    if re.search(r"\bnext\s+week\b", t):
        days = (7 - today.weekday()) % 7 or 7
        start = today + timedelta(days=days)
    elif re.search(r"\btomorrow\b", t):
        start = today + timedelta(days=1)
    elif re.search(r"\bin\s+(\d+)\s+days?\b", t):
        m = re.search(r"\bin\s+(\d+)\s+days?\b", t)
        start = today + timedelta(days=int(m.group(1)))
    if start is None:
        return None, None
    return start.strftime("%Y-%m-%d"), None


def _heuristic_parse(text: str) -> Dict[str, Any]:
    out = {
        "source": "", "destination": "", "start_date": None, "end_date": None,
        "duration_days": None, "budget": None, "currency": "INR", "travelers": 1,
        "travel_type": "solo", "hotel_pref": "mid", "food_pref": [],
        "transport_pref": "flight", "interests": [], "luxury_level": "standard",
    }
    t = text.lower()
    m = re.search(r"from\s+([a-z][a-z ]+?)\s+to\s+([a-z][a-z ]+?)(?:[\.,]|$|\s+for\b|\s+with\b|\s+budget\b|\s+\d)", t)
    if m:
        out["source"] = m.group(1).strip().title()
        out["destination"] = m.group(2).strip().title()
    if not out["destination"]:
        m = re.search(r"\bto\s+([a-z][a-z ]+?)\s+from\s+([a-z][a-z ]+?)(?:[\.,]|$|\s+for\b|\s+with\b|\s+budget\b|\s+\d)", t)
        if m:
            out["destination"] = m.group(1).strip().title()
            out["source"] = m.group(2).strip().title()
    if not out["destination"]:
        m = re.search(r"([a-z][a-z ]+?)\s+trip\s+from\s+([a-z][a-z ]+?)(?:[\.,]|$|\s+for\b|\s+with\b|\s+budget\b|\s+\d)", t)
        if m:
            out["destination"] = m.group(1).strip().split()[-1].title()
            out["source"] = m.group(2).strip().title()
    if not out["destination"]:
        m = re.search(r"\b(?:trip\s+to|travel\s+to|go\s+to|visit|plan(?:\s+a)?(?:\s+trip)?\s+to)\s+([a-z][a-z ]+?)(?:\s+for\b|\s+in\b|\s+on\b|\s+next\b|\s+this\b|[\.,]|$|\s+\d)", t)
        if m:
            cand = m.group(1).strip().lower()
            hit = _find_city(cand)
            out["destination"] = hit or m.group(1).strip().split()[-1].title()
    if not out["source"]:
        m = re.search(r"from\s+([a-z][a-z ]+?)(?:[\.,]|$|\s+for\b|\s+with\b|\s+budget\b|\s+\d|\s+to\b)", t)
        if m:
            out["source"] = m.group(1).strip().title()
    if not out["destination"]:
        out["destination"] = _find_city(t, exclude=out["source"].lower())
    if not out["source"]:
        out["source"] = _find_city(t, exclude=out["destination"].lower())
    m = _DURATION_RE.search(t)
    if m: out["duration_days"] = int(m.group(1))
    m = _BUDGET_RE.search(t)
    if m: out["budget"] = float(m.group(1).replace(",", ""))
    rel_start, _ = _parse_relative_dates(t)
    if rel_start:
        out["start_date"] = rel_start
        if out["duration_days"]:
            end = datetime.strptime(rel_start, "%Y-%m-%d") + timedelta(days=int(out["duration_days"]) - 1)
            out["end_date"] = end.strftime("%Y-%m-%d")
    if "couple" in t or "honeymoon" in t:
        out["travel_type"] = "couple"; out["travelers"] = 2
    elif "family" in t:
        out["travel_type"] = "family"; out["travelers"] = 4
    elif "business" in t:
        out["travel_type"] = "business"
    for kw in ["beach","nightlife","sightseeing","seafood","adventure","snow","mountains",
               "heritage","shopping","spa","wildlife","trekking","temple","palace","lake"]:
        if kw in t and kw not in out["interests"]:
            out["interests"].append(kw)
    if "seafood" in t: out["food_pref"].append("seafood")
    if re.search(r"\bveg\b", t) and "non-veg" not in t: out["food_pref"].append("veg")
    if "train" in t: out["transport_pref"] = "train"
    elif "car" in t or "road" in t: out["transport_pref"] = "car"
    if "luxury" in t: out["hotel_pref"] = "luxury"; out["luxury_level"] = "luxury"
    elif "budget" in t: out["hotel_pref"] = "budget"; out["luxury_level"] = "budget"
    return out


def user_input_agent(state: TripState) -> Dict[str, Any]:
    messages = state.get("messages", [])
    text = ""
    for msg in reversed(messages):
        role = getattr(msg, "type", None)
        content = getattr(msg, "content", None)
        if role is None and isinstance(msg, dict):
            role = msg.get("role"); content = msg.get("content", "")
        if role in ("human", "user") and content:
            text = content; break
    if not text:
        return {}
    fallback = _heuristic_parse(text)
    parsed = chat_json(SYSTEM, text, fallback) or fallback
    existing = dict(state.get("trip_preferences", {}))
    new_dest = (parsed.get("destination") or "").lower()
    old_dest = (existing.get("destination") or "").lower()
    if new_dest and old_dest and new_dest != old_dest:
        for k in ("destination","source","start_date","end_date"):
            existing.pop(k, None)
    for k, v in parsed.items():
        if v not in (None, "", []):
            existing[k] = v
    if existing.get("duration_days") and not existing.get("start_date"):
        start = datetime.utcnow() + timedelta(days=14)
        existing["start_date"] = start.strftime("%Y-%m-%d")
        existing["end_date"] = (start + timedelta(days=int(existing["duration_days"]) - 1)).strftime("%Y-%m-%d")
    for k, v in [("currency","INR"),("travelers",1),("travel_type","solo"),
                  ("hotel_pref","mid"),("transport_pref","flight"),
                  ("luxury_level","standard"),("interests",[]),("food_pref",[])]:
        existing.setdefault(k, v)
    return {"trip_preferences": existing}
