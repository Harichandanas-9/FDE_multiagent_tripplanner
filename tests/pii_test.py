"""
Tests the PII guardrail:
  * unit: each pattern type is redacted
  * integration: chat_turn returns pii_warning when input contains PII
  * integration: the generated PDF does NOT contain raw PII text
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.guardrails import redact, scan, summarise
from chat_flow import chat_turn


def test_unit_patterns():
    samples = {
        "email":       "Reach me at john.doe@example.com please.",
        "phone_in":    "My number is +91-9876543210, call any time.",
        "aadhaar":     "Aadhaar 1234 5678 9012 is for ID.",
        "pan":         "PAN ABCDE1234F for tax.",
        "credit_card": "Card 4539 1488 0343 6467 expires soon.",   # Luhn-valid Visa
        "ssn":         "SSN 123-45-6789 is sensitive.",
        "passport":    "Passport P1234567 details.",
    }
    for kind, text in samples.items():
        red, hits = redact(text)
        kinds = {h.kind for h in hits}
        print(f"  {kind:12} -> {red}")
        assert kind in kinds, f"Expected {kind} hit in: {text} (got {kinds})"
        assert kind.upper() in red, f"Placeholder missing in {red}"
    print("✅ unit pattern tests passed.\n")


def test_no_false_positive():
    """Ordinary travel text should not trip the guardrail."""
    samples = [
        "Plan a 5-day Goa trip from Bangalore, budget Rs 30000, beach + nightlife",
        "Take me to Mysore next week, 3 days, train preferred",
        "What is travel?",
    ]
    for text in samples:
        hits = scan(text)
        assert not hits, f"FALSE POSITIVE on '{text}': {hits}"
    print("✅ no-false-positive tests passed.\n")


def test_chat_integration():
    sid = "pii-1"
    chat_turn(sid, "")  # greet
    # User leaks an email + phone
    r = chat_turn(
        sid,
        "Plan a Goa trip from Bangalore for 4 days, budget Rs 20000, "
        "contact me at hari@example.com or +91-9876543210"
    )
    print("--- bot reply (after PII redaction) ---")
    print(r.reply[:200])
    print(f"pii_warning: {r.pii_warning}")
    assert r.pii_warning is not None, "pii_warning should be set"
    assert "email" in r.pii_warning.lower() or "phone" in r.pii_warning.lower()

    # No raw PII in the bot reply
    assert "hari@example.com" not in r.reply
    assert "9876543210" not in r.reply
    print("✅ chat integration test passed.\n")


def test_pdf_no_pii():
    sid = "pii-pdf-1"
    chat_turn(sid, "")
    # Inject PII alongside trip request
    chat_turn(
        sid,
        "Plan a 3-day Mysore trip from Bangalore, Rs 15000, train, heritage. "
        "My PAN is ABCDE1234F and Aadhaar 1234 5678 9012"
    )
    r = chat_turn(sid, "plan it")
    assert r.pdf_path, "PDF should still be generated"
    print(f"PDF: {r.pdf_path}")
    # Read the generated PDF as bytes; quick text check
    pdf_bytes = Path(r.pdf_path).read_bytes()
    # The redaction placeholder may be inside, but raw PII must not
    assert b"ABCDE1234F" not in pdf_bytes, "PAN leaked to PDF!"
    assert b"1234 5678 9012" not in pdf_bytes, "Aadhaar leaked to PDF!"
    print("✅ PDF redaction test passed.\n")


if __name__ == "__main__":
    test_unit_patterns()
    test_no_false_positive()
    test_chat_integration()
    test_pdf_no_pii()
    print("\n🛡️  All PII guardrail tests passed.")
