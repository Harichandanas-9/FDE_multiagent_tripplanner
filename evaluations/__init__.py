"""Evaluation framework for the Multi-Agent Trip Planner.

Modules:
  basic_eval        — runs every test case through chat_turn, captures
                      latency / pass-fail / guardrail status, saves CSV+JSON
  deepeval_runner   — optional integration with DeepEval (Answer Relevancy,
                      Faithfulness, Hallucination, Tool Correctness, etc.)
  metrics           — pure functions: success rate, latency stats, etc.
  visualization     — bar / pie / line / histogram PNG charts
  report            — produces evaluation_summary.json + markdown report
  loader            — parses evaluation_data/evaluation_cases.txt
"""
from .loader import load_cases, EvalCase
from .basic_eval import run_basic_eval, BasicResult
from .metrics import compute_summary
from .visualization import make_all_charts
from .report import write_reports

__all__ = [
    "load_cases", "EvalCase",
    "run_basic_eval", "BasicResult",
    "compute_summary",
    "make_all_charts",
    "write_reports",
]
