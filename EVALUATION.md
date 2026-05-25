# Evaluation Framework

A drop-in evaluation suite for the Trip Planner. Does **not** modify any
existing agent, workflow, or guardrail — it only *consumes* them.

## Folder layout

```
trip_planner/
├── run_evaluations.py            # single entry point
├── evaluation_data/
│   └── evaluation_cases.txt      # 15 sample cases (happy_path / off_topic /
│                                 #  pii / budget_fit / weather / edge)
└── evaluations/
    ├── __init__.py
    ├── loader.py                 # parses evaluation_cases.txt
    ├── basic_eval.py             # runs cases through chat_turn(), CSV+JSON
    ├── deepeval_runner.py        # DeepEval — Answer Relevancy, Faithfulness,
    │                             #            Hallucination
    ├── metrics.py                # success_rate, latency stats, by-category
    ├── visualization.py          # matplotlib + seaborn + (optional) plotly
    ├── report.py                 # evaluation_summary.json + markdown report
    └── reports/                  # outputs land here
        ├── charts/               # PNG plots + dashboard.html (if plotly)
        ├── logs/                 # eval.log
        ├── evaluation_results.json / .csv
        ├── deepeval_results.json
        ├── evaluation_summary.json
        └── evaluation_report.md
```

## Install extra deps (one-time)

```bash
cd trip_planner
.venv\Scripts\activate          # Windows  |  source .venv/bin/activate on Mac/Linux
pip install -r requirements.txt
```

The new evaluation deps appended to `requirements.txt`:
`deepeval pandas matplotlib seaborn plotly`

## Run the full pipeline

```bash
python run_evaluations.py
```

This will:

1. **Load** evaluation cases from `evaluation_data/evaluation_cases.txt`
2. **Run** each case through the existing `chat_flow.chat_turn()`
3. **Measure** latency, capture reply / pdf_path / pii_warning
4. **Compare** against expected stage + keywords → pass/fail
5. **Compute** summary metrics (success rate, latency p50/p95, by-category)
6. **Run DeepEval** (Answer Relevancy + Faithfulness + Hallucination)
   — gracefully skipped if `deepeval` not installed or `OPENAI_API_KEY` missing
7. **Generate** PNG charts (pie / bar / line / histogram / guardrail / DeepEval)
   and optionally an interactive `dashboard.html`
8. **Write** `evaluation_summary.json` + `evaluation_report.md`
9. **Print** a console summary

## CLI flags

| Flag | Default | Meaning |
|---|---|---|
| `--cases <path>` | `evaluation_data/evaluation_cases.txt` | Alternate cases file |
| `--out-dir <path>` | `evaluations/reports` | Where to drop outputs |
| `--threshold <float>` | `0.5` | DeepEval pass threshold |
| `--skip-deepeval` | off | Run only basic eval + charts |

## Adding your own test cases

Edit `evaluation_data/evaluation_cases.txt`. One block per case, blocks separated by a blank line:

```
TC100 | happy_path | done | mysore,thank you
plan a 3-day Mysore trip from Bangalore, Rs 15000, train
plan it
```

Header columns: `case_id | category | expected_stage | expected_keywords`.
Following lines are user turns; the bot is exercised one turn at a time.

## What gets evaluated

### Basic evaluation (deterministic, always runs)
- **Pass criterion**: final `stage` matches `expected_status` AND at least
  half of `expected_keywords` are present in the final reply
- **Captured per case**: latency (per turn + total), final reply, stage,
  PDF path, PII warning flag, error/exception

### DeepEval (LLM-based, optional)
- `AnswerRelevancyMetric` — does the reply address the trip request?
- `FaithfulnessMetric` — is the reply faithful to the context (no fabrication)?
- `HallucinationMetric` — does the reply hallucinate vs the context?
- Each metric records score, pass/fail and reason per case

Skipped automatically if either:
- `deepeval` is not installed, or
- `OPENAI_API_KEY` is not set (DeepEval uses an LLM judge under the hood)

## Charts produced

- `pass_fail_pie.png` — overall pass/fail ratio
- `category_bar.png` — pass/fail stacked by category
- `latency_line.png` — latency per case with mean line
- `latency_histogram.png` — latency distribution
- `guardrail_violations.png` — PII activations
- `deepeval_scores.png` — per-metric averages with threshold line
- `dashboard.html` — interactive Plotly view (if plotly installed)

## Safety / non-breaking guarantees

- Evaluation modules **only import from existing code** (`chat_flow`,
  `tools.guardrails`, etc.). They do not modify, monkey-patch, or alter any
  existing module.
- The pipeline keeps going if any **single case** or **single chart** fails.
- DeepEval failures (e.g. missing key, network error) are caught — they only
  affect the DeepEval section of the report.
- Evaluation outputs are confined to `evaluations/reports/`.

## Quick smoke test (no API keys needed)

```bash
python run_evaluations.py --skip-deepeval
```

Generates: `evaluations/reports/evaluation_results.csv`,
`evaluations/reports/charts/*.png`,
`evaluations/reports/evaluation_report.md` — all from the deterministic
agent path. Should finish in well under a minute on a laptop.
