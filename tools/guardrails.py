"""PII guardrail."""
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

PII_PATTERNS: List[Tuple[str, str]] = [
    ("email",        r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"),
    ("credit_card",  r"\b(?:\d[ -]?){13,19}\b"),
    ("aadhaar",      r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}\b"),
    ("ssn",          r"\b\d{3}-\d{2}-\d{4}\b"),
    ("pan",          r"\b[A-Z]{5}\d{4}[A-Z]\b"),
    ("passport",     r"\b[A-PR-WY][1-9]\d{6}\b"),
    ("phone_in",     r"(?:(?<!\d)(?:\+?91[-\s]?)?[6-9]\d{9}(?!\d))"),
    ("phone_us",     r"\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b"),
    ("ipv4",         r"\b(?:25[0-5]|2[0-4]\d|[01]?\d\d?)(?:\.(?:25[0-5]|2[0-4]\d|[01]?\d\d?)){3}\b"),
]
_COMPILED = [(k, re.compile(p)) for k, p in PII_PATTERNS]


def _luhn_ok(s: str) -> bool:
    d = [int(c) for c in s if c.isdigit()]
    if not 13 <= len(d) <= 19: return False
    cs = 0; par = len(d) % 2
    for i, x in enumerate(d):
        if i % 2 == par:
            x *= 2
            if x > 9: x -= 9
        cs += x
    return cs % 10 == 0


@dataclass
class PiiHit:
    kind: str; value: str; start: int; end: int


def scan(text: str) -> List[PiiHit]:
    if not text: return []
    hits, occ = [], []
    for kind, rx in _COMPILED:
        for m in rx.finditer(text):
            s, e = m.span()
            if any(a < e and s < b for a, b in occ): continue
            v = m.group(0)
            if kind == "credit_card" and not _luhn_ok(v): continue
            hits.append(PiiHit(kind, v, s, e)); occ.append((s, e))
    hits.sort(key=lambda h: h.start)
    return hits


def redact(text: str, placeholder: str = "[REDACTED-{kind}]") -> Tuple[str, List[PiiHit]]:
    if not text: return text, []
    hits = scan(text)
    if not hits: return text, []
    out = text
    for h in sorted(hits, key=lambda h: h.start, reverse=True):
        out = out[:h.start] + placeholder.format(kind=h.kind.upper()) + out[h.end:]
    return out, hits


def redact_dict(obj: Any) -> Any:
    if isinstance(obj, str):
        c, _ = redact(obj); return c
    if isinstance(obj, dict):
        return {k: redact_dict(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact_dict(v) for v in obj]
    return obj


def summarise(hits: List[PiiHit]) -> str:
    if not hits: return ""
    counts: Dict[str, int] = {}
    for h in hits: counts[h.kind] = counts.get(h.kind, 0) + 1
    pretty = {"email": "email address", "phone_in": "phone number",
              "phone_us": "phone number", "aadhaar": "Aadhaar number",
              "pan": "PAN", "credit_card": "card number", "ssn": "SSN",
              "passport": "passport number", "ipv4": "IP address"}
    parts = []
    for k, n in counts.items():
        lbl = pretty.get(k, k); lbl = lbl + "s" if n > 1 else lbl
        parts.append(f"{n} {lbl}")
    if len(parts) == 1: return parts[0]
    return ", ".join(parts[:-1]) + " and " + parts[-1]
