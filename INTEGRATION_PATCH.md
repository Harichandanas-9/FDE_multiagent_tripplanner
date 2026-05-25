# Wire the Evaluation UI into your existing FastAPI server

Add **just two lines** to your existing `api/server.py`. The rest is the
new files from the zip — no other existing code is modified.

## Patch (api/server.py)

Find the `app = FastAPI(...)` line near the top, and right after the
`app.mount("/static", ...)` line (the line that already mounts your frontend
folder), add:

```python
# --- Evaluation UI (new) -------------------------------------------------
from api.evaluation_routes import router as evaluation_router
app.include_router(evaluation_router)
# -------------------------------------------------------------------------
```

That's it. Restart `python run.py` and visit:

- <http://127.0.0.1:8000/>            ← chat UI (unchanged)
- <http://127.0.0.1:8000/evaluations> ← **new** evaluation dashboard

## What the dashboard does

1. **Run evaluation** button → POST `/api/evaluations/run` → runs the full
   evaluation pipeline server-side, writes results to `evaluations/reports/`,
   returns the summary JSON. The page then renders charts, tables and the
   markdown report.

2. **Skip DeepEval** checkbox (default ON) → so it works without an OpenAI
   key. Uncheck it to run Answer Relevancy / Faithfulness / Hallucination.

3. **Refresh** button → re-reads the last saved results without re-running.

## Endpoints added (all under the existing FastAPI app)

| Method | Path | Purpose |
|---|---|---|
| GET  | `/evaluations`                    | HTML dashboard |
| POST | `/api/evaluations/run`            | Trigger the pipeline |
| GET  | `/api/evaluations/summary`        | evaluation_summary.json |
| GET  | `/api/evaluations/results`        | evaluation_results.json (per case) |
| GET  | `/api/evaluations/report`         | Markdown report (text/plain) |
| GET  | `/api/evaluations/chart/{name}`   | PNG chart, e.g. `pass_fail_pie.png` |

## Optional: add a link in the chat UI

If you want, add this single anchor inside the header `<div>` of
`frontend/index.html` (above or below the existing badges):

```html
<a href="/evaluations" style="color:white;text-decoration:none;
   background:rgba(255,255,255,0.15);padding:6px 12px;border-radius:999px;
   font-size:12px;font-weight:600;">📊 Evaluations</a>
```

That gives users a one-click jump from chat to the eval dashboard.

## Safety

- Zero changes to `chat_flow.py`, `graph.py`, `agents/*`, `tools/*`, `memory/*`,
  or any guardrail.
- The new module catches all errors so a failed eval cannot break the chat app.
- Outputs are confined to `evaluations/reports/`.
