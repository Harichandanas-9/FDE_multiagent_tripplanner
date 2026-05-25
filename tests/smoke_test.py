"""End-to-end smoke test — runs the chat flow with a sample query and verifies
that a PDF is produced. Works with no API keys (uses mocks)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from chat_flow import chat_turn


def main() -> int:
    sid = "smoke-1"
    # 1. greet
    r0 = chat_turn(sid, "")
    print("=== greeting ===\n" + r0.reply[:200])
    assert "Hello" in r0.reply

    # 2. sample query from the assignment
    query = ("Plan a 5-day Goa trip from Bangalore for a couple, budget ₹30,000, "
             "beach resort, nightlife, sightseeing, seafood, flight preferred")
    r1 = chat_turn(sid, query)
    print("\n=== weather check ===\n" + r1.reply[:600])
    assert "weather" in r1.reply.lower() or "forecast" in r1.reply.lower(), \
        "Weather check should run first"
    assert r1.stage == "confirm"

    # 3. confirm planning
    r2 = chat_turn(sid, "plan it")
    print("\n=== final plan ===\n" + r2.reply[:500])
    assert r2.pdf_path, "PDF should be generated"
    assert Path(r2.pdf_path).exists(), f"PDF missing: {r2.pdf_path}"
    assert "Thank you, happy journey" in r2.reply
    size_kb = Path(r2.pdf_path).stat().st_size / 1024
    print(f"\nPDF: {r2.pdf_path}  ({size_kb:.1f} KB)")
    print(f"Stage: {r2.stage}  Done: {r2.done}")

    assert size_kb > 5, "PDF looks too small"
    print("\n✅ Smoke test passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
