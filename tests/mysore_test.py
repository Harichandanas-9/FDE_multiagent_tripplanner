"""Reproduce user's bug: 'plan a trip to mysore for 3 days in nextweek'."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from chat_flow import chat_turn

def main():
    sid = "mysore-1"
    # 1. Fresh greeting
    r0 = chat_turn(sid, "")
    print("=== greet ===\n" + r0.reply[:140])

    # 2. The exact user message — should pick up Mysore + 3 days + next week
    r1 = chat_turn(sid, "plan a trip to mysore for 3 days in next week")
    prefs = r1.state.get("trip_preferences", {})
    print("\n=== after first message ===\n" + r1.reply[:400])
    print("\nPrefs parsed:", {k: prefs.get(k) for k in
          ("source", "destination", "duration_days", "start_date", "end_date")})
    assert prefs.get("destination", "").lower() == "mysore", \
        f"Expected Mysore, got {prefs.get('destination')!r}"
    assert prefs.get("duration_days") == 3
    assert prefs.get("start_date"), "next-week date should be parsed"
    assert "goa" not in r1.reply.lower(), "old Goa data should NOT leak into bot reply"

    # 3. Provide remaining details — source + budget
    r2 = chat_turn(sid, "from Bangalore, budget rs 15000, heritage and shopping, train")
    print("\n=== after details (weather check) ===\n" + r2.reply[:600])
    assert "mysore" in r2.reply.lower(), "Weather should now be checked for Mysore"
    assert "weather" in r2.reply.lower() or "forecast" in r2.reply.lower()

    # 4. Plan it
    r3 = chat_turn(sid, "plan it")
    print("\n=== final ===\n" + r3.reply[:300])
    assert r3.pdf_path, "PDF should be generated"
    assert "mysore" in r3.pdf_path.lower(), f"PDF name should mention Mysore, got {r3.pdf_path}"
    assert "Thank you, happy journey" in r3.reply

    # 5. Now start a NEW trip in the same session — should NOT show Mysore data
    r4 = chat_turn(sid, "plan a trip to Goa from Mumbai for 4 days, budget 25000, beach")
    new_prefs = r4.state.get("trip_preferences", {})
    print("\n=== new trip after done ===")
    print("New prefs:", {k: new_prefs.get(k) for k in
          ("source", "destination", "duration_days", "start_date")})
    assert new_prefs.get("destination", "").lower() == "goa", \
        f"Should switch to Goa, got {new_prefs.get('destination')!r}"
    assert new_prefs.get("source", "").lower() == "mumbai"
    assert new_prefs.get("duration_days") == 4

    print("\n✅ Mysore-flow + new-trip reset test passed.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
