# Trip Planner — Evaluation Report
_Generated 2026-05-25T06:01:47.146410Z_

## Headline metrics
- Total cases: **15**
- Passed: **12** / Failed: **3**
- Success rate: **80.0%**
- Completion rate (PDF generated): **66.7%**
- Error rate: **0.0%**
- Empty-response rate: **0.0%**
- PII detections: **2**
- Latency: mean **2.13s**, median 2.64s, min 0.00s, max 3.62s

## Per-category breakdown
| Category | Total | Passed | Failed | Success rate |
|---|---|---|---|---|
| happy_path | 5 | 5 | 0 | 100.0% |
| off_topic | 2 | 2 | 0 | 100.0% |
| pii | 2 | 2 | 0 | 100.0% |
| budget_fit | 2 | 0 | 2 | 0.0% |
| weather_conflict | 1 | 0 | 1 | 0.0% |
| edge | 3 | 3 | 0 | 100.0% |

## Best / worst
- **Best (fastest pass):** TC004 (0.001s)
- **Slowest case:** TC014 (3.617s)

## Failed cases
- TC008
- TC009
- TC010

## DeepEval results
- _Skipped: no usable test cases_

## Files
- evaluation_summary.json — full structured summary
- evaluation_results.json / .csv — per-case raw results
- deepeval_results.json — DeepEval scores
- charts/ — PNG plots + optional Plotly dashboard.html
- logs/ — eval.log
