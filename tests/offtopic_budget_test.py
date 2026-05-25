"""
Tests the two new behaviours:
  1. Off-topic messages get an LLM-style answer, NOT 'destination missing'.
  2. A tight budget forces the orchestrator to downgrade hotel / switch
     transport until the plan fits.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from chat_flow import chat_turn


def test_off_topic():
    sid = "off-topic-1"
    chat_turn(sid, "")  # greeting

    # Off-topic question
    r = chat_turn(sid, "what is travel")
    print("=== off-topic 'what is travel' ===")
    print(r.reply[:300])
    print(f"stage: {r.stage}")
    assert "destination" not in r.reply.lower()[:80], \
        "Off-topic message should NOT trigger 'destination missing'"
    assert "travel" in r.reply.lower(), "Should actually explain travel"
    assert r.stage == "chat", f"Expected stage=chat, got {r.stage}"

    # Another off-topic
    r2 = chat_turn(sid, "who are you")
    print("\n=== off-topic 'who are you' ===")
    print(r2.reply[:300])
    assert "trip planner" in r2.reply.lower() or "assistant" in r2.reply.lower()

    # Now a trip query should still work
    r3 = chat_turn(sid, "plan a trip to mysore for 3 days")
    print("\n=== back to trip ===")
    print(r3.reply[:200])
    assert r3.state["trip_preferences"]["destination"].lower() == "mysore"
    print("\n✅ off-topic test passed.")


def test_budget_fit():
    """Tight budget should force the orchestrator to downgrade hotel / switch transport."""
    sid = "budget-fit-1"
    chat_turn(sid, "")
    # ask for a LUXURY plan with a very tight budget — forces downgrade
    r = chat_turn(
        sid,
        "Plan a 4-day Goa trip from Bangalore for a couple, "
        "budget Rs 15000, luxury beach resort, nightlife, flight preferred",
    )
    print("\n=== tight-budget weather check ===")
    print(r.reply[:250])
    assert r.stage == "confirm"

    r2 = chat_turn(sid, "plan it")
    print("\n=== tight-budget final ===")
    print(r2.reply)
    budget = r2.state.get("budget_summary", {})
    prefs = r2.state.get("trip_preferences", {})
    print("\nFinal hotel_pref:", prefs.get("hotel_pref"))
    print("Final transport_pref:", prefs.get("transport_pref"))
    print("Estimated:", budget.get("estimated_total"),
          "Budget:", budget.get("budget"),
          "Within:", budget.get("within_budget"),
          "Overshoot:", budget.get("overshoot"))
    # The orchestrator must have downgraded the luxury hotel
    assert prefs.get("hotel_pref") in ("budget", "mid"), \
        "Luxury hotel should have been downgraded under tight budget"
    # Should at least be a lot closer to budget than the original luxury estimate
    assert budget.get("estimated_total") < 80_000, \
        f"Plan still wildly over budget: Rs {budget.get('estimated_total')}"
    assert r2.pdf_path, "PDF should still be generated"
    print("\n✅ budget-fit test passed.")


if __name__ == "__main__":
    test_off_topic()
    print("\n" + "=" * 60 + "\n")
    test_budget_fit()
