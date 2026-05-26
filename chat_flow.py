"""Conversational flow controller — chat + guardrails + agents (bulletproof)."""
from __future__ import annotations
import logging, re, traceback
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from langchain_core.messages import AIMessage, HumanMessage

from agents.user_input_agent import user_input_agent, _heuristic_parse, KNOWN_CITIES
from agents.pii_agent import pii_guardrail_agent
from agents.memory_agent import memory_retrieval_agent, memory_update_agent
from agents.weather_agent import weather_agent
from agents.places_agent import places_agent
from agents.transport_agent import transport_agent
from agents.hotel_agent import hotel_agent
from agents.budget_agent import budget_agent
from agents.itinerary_agent import itinerary_agent
from agents.review_agent import final_review_agent
from agents.orchestrator_agent import orchestrator_validation
from agents.pdf_agent import pdf_generator_agent
from agents._llm import chat_text
from memory import get_session_memory
from state import TripState, new_state
from tools.places_api import suggest_places, DESTINATION_CATALOG
from tools.guardrails import redact, summarise
from tracing import traceable, capture_run_id

logger = logging.getLogger("trip_planner")

GREETING = (
    "Hello! I'm your AI Trip Planner. How can I help you today?\n\n"
    "Tell me where you'd like to go and I'll plan the whole trip - flights, "
    "hotels, day-wise itinerary and a downloadable PDF. For example: "
    "*Plan a 4-day Mysore trip from Bangalore, budget Rs 15,000, "
    "heritage + temples, train preferred.*"
)


def _safe(label, fn, state, default=None):
    """Call an agent (wrapped in a LangSmith span if enabled)."""
    try:
        traced_fn = traceable(name=f"agent_{label}")(fn)
        return traced_fn(state) or {}
    except BaseException as e:
        logger.error("agent '%s' failed: %s: %s\n%s",
                     label, e.__class__.__name__, e, traceback.format_exc())
        return default or {}


def _merge(s, p):
    if not p: return s
    for k, v in p.items(): s[k] = v
    return s


def _has_basic_inputs(state):
    prefs = state.get("trip_preferences", {}) or {}
    miss = []
    if not prefs.get("destination"): miss.append("destination")
    if not prefs.get("source"): miss.append("source city")
    if not prefs.get("duration_days") and not (prefs.get("start_date") and prefs.get("end_date")):
        miss.append("duration or travel dates")
    if not prefs.get("budget"): miss.append("budget (approx.)")
    return miss


def _format_weather(w):
    days = w.get("forecast", [])
    if not days: return "Could not fetch weather data."
    header = f"Weather forecast for {w.get('city','destination')}"
    if w.get("source") == "openweathermap": header += " (live)"
    lines = [f"  - {d['date']}: {d['summary']}, {d['temp_min_c']}-{d['temp_max_c']}C, rain {d.get('rain_mm',0)}mm"
             for d in days]
    v = (w.get("assessment") or {}).get("verdict", "good")
    tone = {"good":"Looks great for travel.","rainy":"Expect rain - indoor focus.",
            "very_hot":"Will be hot - stay hydrated."}.get(v, "")
    return "\n".join([header, *lines, "", tone])


def _format_suggestions(sugs):
    if not sugs: return ""
    lines = ["Top places matching your interests:"]
    for i, s in enumerate(sugs[:5], 1):
        lines.append(f"  {i}. **{s['city']}** - {s['tagline']}\n"
                     f"     Season: {s['season']}  |  {', '.join(s['highlights'])}")
    return "\n".join(lines)


TRIP_PHRASES = [r"\bplan(?:ning)?\s+(?:a\s+)?trip\b", r"\btrip\s+(?:to|from)\b",
                r"\btravel\s+(?:to|from)\b", r"\bgo\s+to\b", r"\bvisit\s+\w+",
                r"\bvacation\s+to\b", r"\bholiday\s+(?:to|in)\b",
                r"\bbook\s+(?:a\s+)?(?:flight|train|hotel|trip)\b",
                r"\bitinerary\b", r"\bplan\s+it\b",
                r"\bsuggest\s+(?:a\s+)?(?:place|destination|alternative)"]
DEFINITION_PREFIXES = [r"^what\s+is\b", r"^what\s+are\b", r"^what\'s\b",
                       r"^who\s+is\b", r"^who\s+are\b", r"^who\'s\b",
                       r"^why\s+", r"^how\s+do\s+", r"^how\s+does\s+",
                       r"^explain\b", r"^define\b", r"^tell\s+me\s+about\b"]


def _has_trip_signal(text, state):
    t = text.lower().strip()
    if not t: return False
    if state.get("trip_preferences", {}).get("destination"): return True
    if state.get("conversation_stage") in ("confirm", "plan"): return True
    prefs = state.get("trip_preferences", {}) or {}
    if prefs.get("source") or prefs.get("duration_days") or prefs.get("budget"): return True
    for pre in DEFINITION_PREFIXES:
        if re.search(pre, t):
            for city in KNOWN_CITIES:
                if re.search(rf"\b{re.escape(city)}\b", t): return True
            return False
    try:
        p = _heuristic_parse(text)
        if p.get("destination") or p.get("source") or p.get("duration_days") or p.get("budget"):
            return True
    except Exception: pass
    for pat in TRIP_PHRASES:
        if re.search(pat, t): return True
    for city in KNOWN_CITIES:
        if re.search(rf"\b{re.escape(city)}\b", t): return True
    return False


def _general_reply(msg):
    fb = {"what is travel": "Travel is the act of going from one place to another. Tell me where you want to go!",
          "who are you": "I'm your AI Trip Planner. Tell me where you'd like to go!"}
    k = msg.lower().strip(" ?.!")
    if k in fb: return fb[k]
    return chat_text(
        "You are a friendly AI assistant inside a Trip Planner. Answer briefly then invite the user to plan a trip.",
        msg,
        fallback="I'm best at planning trips. Tell me where you'd like to go!"
    )


def _looks_like_new_trip(t):
    return any(k in t.lower() for k in ("plan","trip to","travel to","go to","visit","vacation","holiday","tour"))


@traceable(name="agent_pipeline")
def _run_plan(state):
    s = dict(state)
    s = _merge(s, _safe("pii_guardrail", pii_guardrail_agent, s))
    s = _merge(s, _safe("user_input", user_input_agent, s))
    s = _merge(s, _safe("memory_retrieval", memory_retrieval_agent, s))
    for _ in range(6):
        if not s.get("weather_data"):   s = _merge(s, _safe("weather", weather_agent, s))
        if not s.get("places_data"):    s = _merge(s, _safe("places", places_agent, s))
        if not s.get("transport_data"): s = _merge(s, _safe("transport", transport_agent, s))
        if not s.get("hotel_data"):     s = _merge(s, _safe("hotel", hotel_agent, s))
        if not s.get("budget_summary"): s = _merge(s, _safe("budget", budget_agent, s))
        if not s.get("itinerary"):      s = _merge(s, _safe("itinerary", itinerary_agent, s))
        if not s.get("review_status"):  s = _merge(s, _safe("review", final_review_agent, s))
        v = _safe("validate", orchestrator_validation, s)
        s = _merge(s, v)
        if (s.get("orchestrator_decision", {}) or {}).get("approved"): break
    s = _merge(s, _safe("memory_update", memory_update_agent, s))
    s = _merge(s, _safe("pdf", pdf_generator_agent, s))
    return s


@dataclass
class ChatResponse:
    reply: str
    state: TripState
    stage: str
    pdf_path: Optional[str] = None
    done: bool = False
    pii_warning: Optional[str] = None
    run_id: Optional[str] = None
    guardrail_status: Optional[Dict[str, Any]] = None


def _resp(reply, state, stage, pii_warning=None, guardrail_status=None,
          pdf_path=None, done=False):
    """Helper that always carries run_id + guardrail_status into ChatResponse."""
    return ChatResponse(
        reply=reply, state=state, stage=stage,
        pdf_path=pdf_path, done=done,
        pii_warning=pii_warning,
        run_id=capture_run_id(),
        guardrail_status=guardrail_status,
    )


@traceable(name="chat_turn")
def chat_turn(session_id, user_message):
    """ONE bulletproof entry point. Cannot raise an exception."""
    try:
        return _chat_turn_inner(session_id, user_message)
    except BaseException as e:
        logger.error("chat_turn fatal: %s\n%s", e, traceback.format_exc())
        return _resp("Internal error. Try again.",
                     new_state(user_id=session_id), "error")


def _chat_turn_inner(sid, user_message):
    sm = get_session_memory()
    sess = sm.get(sid)
    state = sess.get("state") or new_state(user_id=sid)
    pii_warning: Optional[str] = None
    guardrail_status: Dict[str, Any] = {
        "checked": False, "pii_found": False, "pii_count": 0,
        "kinds": [], "scrubbed": False,
    }

    # First-turn greeting on empty input
    if state.get("conversation_stage") == "greet" and not user_message.strip():
        sm.update_state(sid, state)
        return _resp(GREETING, state, "greet", guardrail_status=guardrail_status)

    # Reset state if previous trip already finished
    if state.get("conversation_stage") == "done" or (
        state.get("pdf_path") and _looks_like_new_trip(user_message)):
        uid = state.get("user_profile", {}).get("user_id", sid)
        state = new_state(user_id=uid)
        state["conversation_stage"] = "collect"

    # ============ PII GUARDRAIL — always runs, status always reported ============
    if user_message:
        try:
            cleaned, hits = redact(user_message)
            guardrail_status["checked"] = True
            guardrail_status["pii_count"] = len(hits)
            guardrail_status["kinds"] = sorted({h.kind for h in hits})
            if hits:
                guardrail_status["pii_found"] = True
                guardrail_status["scrubbed"] = True
                pii_warning = ("I noticed " + summarise(hits) + " in your message; "
                               "redacted before processing.")
                user_message = cleaned
            logger.info("guardrail status: %s", guardrail_status)
        except Exception as e:
            logger.warning("guardrail check failed: %s", e)
            guardrail_status["checked"] = False
            guardrail_status["error"] = str(e)

    state["messages"] = list(state.get("messages", [])) + [HumanMessage(content=user_message)]
    sm.append_history(sid, "user", user_message)

    # Bare "hi" echoes greeting
    if state.get("conversation_stage") == "greet":
        if re.fullmatch(r"\s*(hi|hello|hey|namaste|good (morning|evening|afternoon))[\.!]?\s*",
                         user_message, re.I):
            state["conversation_stage"] = "ask_help"
            state["messages"].append(AIMessage(content=GREETING))
            sm.update_state(sid, state)
            return _resp(GREETING, state, "ask_help",
                         pii_warning=pii_warning, guardrail_status=guardrail_status)

    if not _has_trip_signal(user_message, state):
        reply = _general_reply(user_message)
        state["messages"].append(AIMessage(content=reply))
        if state.get("conversation_stage") in ("greet", "ask_help"):
            state["conversation_stage"] = "ask_help"
        sm.update_state(sid, state)
        return _resp(reply, state, "chat",
                     pii_warning=pii_warning, guardrail_status=guardrail_status)

    if state.get("conversation_stage") in ("greet", "ask_help"):
        state["conversation_stage"] = "collect"

    state = _merge(state, _safe("user_input", user_input_agent, state))

    miss = _has_basic_inputs(state)
    if miss:
        p = state.get("trip_preferences", {}) or {}
        reply = (f"Got it. So far I have:\n"
                 f"  - destination: {p.get('destination') or '-'}\n"
                 f"  - source: {p.get('source') or '-'}\n"
                 f"  - duration: {p.get('duration_days') or '-'} days\n"
                 f"  - budget: {p.get('budget') or '-'} {p.get('currency','')}\n\n"
                 f"I still need: **{', '.join(miss)}**.")
        state["conversation_stage"] = "collect"
        state["messages"].append(AIMessage(content=reply))
        sm.update_state(sid, state)
        return _resp(reply, state, "collect",
                     pii_warning=pii_warning, guardrail_status=guardrail_status)

    if not state.get("weather_data"):
        state = _merge(state, _safe("weather", weather_agent, state))
        state = _merge(state, _safe("places", places_agent, state))
        wt = _format_weather(state.get("weather_data", {}))
        sugs = (state.get("places_data", {}) or {}).get("alt_suggestions", [])
        p = state["trip_preferences"]
        info = (state.get("places_data", {}) or {}).get("destination_info", {})
        atts = info.get("attractions", [])[:5]
        atts_txt = ""
        if atts:
            atts_txt = "\n\nTop picks in " + p["destination"] + ":\n" + "\n".join(
                f"  - {a['name']} ({a['type']}) rating {a['rating']}" for a in atts)
        reply = (f"Let me check the weather for **{p['destination']}** first.\n\n"
                 f"{wt}{atts_txt}\n\n{_format_suggestions(sugs)}\n\n"
                 "Reply **plan it** to generate the full plan + PDF.")
        state["conversation_stage"] = "confirm"
        state["messages"].append(AIMessage(content=reply))
        sm.update_state(sid, state)
        return _resp(reply, state, "confirm",
                     pii_warning=pii_warning, guardrail_status=guardrail_status)

    state["conversation_stage"] = "plan"
    final_state = _run_plan(state)
    pdf_path = final_state.get("pdf_path")
    reply_lines = []
    p = final_state.get("trip_preferences", {})
    b = final_state.get("budget_summary", {}) or {}
    if pdf_path:
        reply_lines.append(f"Your **{p.get('duration_days','?')}-day {p.get('destination','trip')}** plan is ready!")
        if b:
            status = "within budget" if b.get("within_budget") else f"over by Rs {int(b.get('overshoot',0))}"
            reply_lines.append(f"Estimated: Rs {int(b.get('estimated_total',0))} of Rs {int(b.get('budget',0))} - {status}")
            tweaks = []
            if p.get("hotel_pref") == "budget": tweaks.append("hotel tier")
            if p.get("transport_pref") == "train": tweaks.append("switched to train")
            if tweaks: reply_lines.append("Adjusted: " + ", ".join(tweaks))
        reply_lines.append("PDF ready.")
        reply_lines.append("\n**Thank you, happy journey!**")
    else:
        reply_lines.append("Could not finalize the PDF this time.")
    reply = "\n\n".join(reply_lines)
    final_state["messages"].append(AIMessage(content=reply))
    final_state["conversation_stage"] = "done"
    sm.update_state(sid, final_state)
    return _resp(reply, final_state, "done",
                 pii_warning=pii_warning, guardrail_status=guardrail_status,
                 pdf_path=pdf_path, done=True)
