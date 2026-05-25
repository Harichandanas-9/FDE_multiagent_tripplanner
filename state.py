"""Shared LangGraph state schema."""
from __future__ import annotations
from typing import Annotated, Any, Dict, List, Optional, TypedDict
from langgraph.graph.message import add_messages


class TripState(TypedDict, total=False):
    messages: Annotated[list, add_messages]
    conversation_stage: str
    user_profile: Dict[str, Any]
    trip_preferences: Dict[str, Any]
    weather_data: Dict[str, Any]
    hotel_data: Dict[str, Any]
    transport_data: Dict[str, Any]
    places_data: Dict[str, Any]
    budget_summary: Dict[str, Any]
    itinerary: Dict[str, Any]
    review_status: Dict[str, Any]
    pdf_status: Dict[str, Any]
    orchestrator_decision: Dict[str, Any]
    memory_hits: List[Dict[str, Any]]
    retry_counts: Dict[str, int]
    errors: List[str]
    pdf_path: Optional[str]
    final_message: Optional[str]


def new_state(user_id: str = "guest") -> TripState:
    return {
        "messages": [], "conversation_stage": "greet",
        "user_profile": {"user_id": user_id},
        "trip_preferences": {}, "weather_data": {}, "hotel_data": {},
        "transport_data": {}, "places_data": {}, "budget_summary": {},
        "itinerary": {}, "review_status": {}, "pdf_status": {},
        "orchestrator_decision": {}, "memory_hits": [], "retry_counts": {},
        "errors": [], "pdf_path": None, "final_message": None,
    }
