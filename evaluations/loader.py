"""Parses evaluation_data/evaluation_cases.txt into EvalCase objects.

Header format (5 fields):
    ID | category | expected_status | expected_keywords | quality

`quality` is optional — defaults to "medium" if missing (for backward compat).
"""
from __future__ import annotations
import logging, os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

logger = logging.getLogger("evaluations.loader")


@dataclass
class EvalCase:
    case_id: str
    category: str
    expected_status: str
    expected_keywords: List[str]
    user_turns: List[str] = field(default_factory=list)
    quality: str = "medium"

    def to_dict(self):
        return {"case_id": self.case_id, "category": self.category,
                "expected_status": self.expected_status,
                "expected_keywords": self.expected_keywords,
                "user_turns": self.user_turns, "quality": self.quality}


def _default_path() -> Path:
    return Path(__file__).resolve().parent.parent / "evaluation_data" / "evaluation_cases.txt"


def load_cases(path=None) -> List[EvalCase]:
    p = Path(path) if path else _default_path()
    if not p.exists():
        logger.warning("cases file not found: %s", p)
        return []
    cases: List[EvalCase] = []
    block: List[str] = []

    def _flush(b):
        non = [l for l in b if l.strip() and not l.strip().startswith("#")]
        if not non: return
        parts = [p.strip() for p in non[0].split("|")]
        if len(parts) < 4:
            logger.warning("malformed header: %s", non[0]); return
        case_id, category, expected_status, kw_raw = parts[:4]
        quality = parts[4] if len(parts) > 4 else "medium"
        keywords = [k.strip().lower() for k in kw_raw.split(",") if k.strip()]
        user_turns = non[1:]
        if not user_turns: return
        cases.append(EvalCase(case_id=case_id, category=category,
                              expected_status=expected_status,
                              expected_keywords=keywords,
                              user_turns=user_turns,
                              quality=quality.lower() if quality.lower() in ("good","medium","bad") else "medium"))

    with p.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                _flush(block); block = []
            else:
                block.append(line.rstrip("\n"))
        _flush(block)
    logger.info("loaded %d cases", len(cases))
    return cases
