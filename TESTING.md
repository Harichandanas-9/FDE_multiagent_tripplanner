# Testing & Running the Multi-Agent Trip Planner

## 1. Install (one-time)

```bash
cd C:\Users\harichandana.p.PRODAPT\Documents\Multiagent\trip_planner
python -m venv .venv
.venv\Scripts\activate              # Windows PowerShell / cmd
# (on Mac/Linux: source .venv/bin/activate)
pip install -r requirements.txt
```

## 2. Configure API keys

```bash
copy .env.example .env               # Windows  (cp on Mac/Linux)
```
Edit `.env`:
```
OPENAI_API_KEY=sk-...                # required for LLM + Realtime voice
OPENWEATHER_API_KEY=...              # gives you LIVE weather
```
If you leave OPENAI_API_KEY blank, the bot still works — it falls back to a
heuristic parser and a built-in general-chat responder.

## 3. Start the server

```bash
python run.py
```
Open <http://127.0.0.1:8000>. Browser tab shows:
- text chat (Enter to send)
- 🎤 voice button → OpenAI Realtime API via WebRTC

If VS Code is open on the same files, **close + reopen** any edited file so VS
Code reads the latest version. If `python run.py` hangs on an import,
`del /s /q __pycache__` (Windows) or `find . -name __pycache__ -exec rm -rf {} +`
(Mac/Linux).

## 4. Run the test suite

All tests live in `tests/` and work without any API keys (they exercise the
heuristic + mock fallback paths). Run from the project root:

```bash
# Each script is self-contained and prints a green tick on success
python tests/smoke_test.py            # original Goa happy path
python tests/mysore_test.py           # "trip to mysore for 3 days in next week" + session reset
python tests/offtopic_budget_test.py  # off-topic chat + tight-budget downgrade
python tests/pii_test.py              # PII redaction (email, phone, PAN, Aadhaar, card, SSN, passport)
```

Or all at once:
```bash
for f in tests\*.py do python %f
```
(on Windows) — or on Mac/Linux:
```bash
for f in tests/*.py; do python "$f"; done
```

## 5. What each test covers

### `smoke_test.py`
1. Send empty message → greeting fires.
2. Send the assignment sample query (5-day Goa from Bangalore, Rs 30k, couple, beach + nightlife, seafood, flight).
3. Confirm with "plan it".
4. Asserts a real PDF file is generated and the chat ends with "Thank you, happy journey!".

### `mysore_test.py`
Reproduces the bug you hit ("everything returns Goa"):
1. Send `"plan a trip to mysore for 3 days in next week"`.
2. Bot picks up Mysore, 3 days, start date = next Monday.
3. After source + budget are added, weather is checked for **Mysore** (not Goa).
4. PDF filename contains "Mysore".
5. A follow-up "plan a trip to Goa from Mumbai" cleanly resets to a Goa plan.

### `offtopic_budget_test.py`
Two scenarios:
- **off-topic** — `"what is travel"`, `"who are you"` route to general LLM chat (no "destination missing" template). Then `"plan a trip to mysore"` still works.
- **tight budget** — `"4-day Goa luxury trip, budget Rs 15000"`. Orchestrator detects overshoot, downgrades hotel band luxury→mid→budget, switches flight→train, until estimated_total ≤ budget. Chat reply lists what was adjusted.

### `pii_test.py`
Four assertions:
- `redact()` redacts each pattern (email / phone_in / Aadhaar / PAN / credit_card / SSN / passport).
- Normal travel text has **zero** false positives.
- A user message with email + phone produces a `pii_warning` and removes raw PII from the reply.
- A generated PDF does **not** contain raw PAN or Aadhaar strings.

## 6. Manual smoke-test in the browser

Open <http://127.0.0.1:8000> and try in order:

1. `hi` → bot greets and asks how it can help.
2. `what is travel` → general-LLM answer (NOT a "destination missing" template).
3. `plan a trip to mysore for 3 days in next week` → bot tells you what's still missing.
4. `from Bangalore, budget Rs 15000, heritage and shopping, train` → bot fetches **Mysore** weather (live OpenWeatherMap) and lists Mysore Palace, Chamundi Hills, etc.
5. `plan it` → full plan + PDF download card → ends with "Thank you, happy journey!"
6. Try a PII test: `contact me at hari@example.com or 9876543210, plan a Goa trip from Mumbai for 3 days, Rs 18000`. The PDF/chat won't contain your email or phone.

## 7. Where each guardrail lives

| Concern | File | What it does |
|---|---|---|
| PII detection patterns | `tools/guardrails.py` | Regexes + Luhn check; `redact()`, `scan()`, `summarise()`, `redact_dict()` |
| Scrub user input | `chat_flow.py` (top of `chat_turn`) | Every user message is redacted before storing / parsing / calling LLM |
| Scrub vector memory | `agents/memory_agent.py` | `memory_update_agent` redacts the trip summary before FAISS write |
| Scrub PDF | `agents/pdf_agent.py` (`_build_pdf`) | Recursively redacts the whole state before building the PDF |
| Surface PII warning to UI | `api/server.py` + `frontend/index.html` | `ChatOut.pii_warning` returned; UI shows it as a yellow card above the bot reply |

## 8. Common gotchas

- **VS Code shows old code** — the editor caches the buffer. *File → Revert File* or close+reopen.
- **`__pycache__` stale** — delete it or run `python -B run.py`.
- **Voice mode disabled** — needs `OPENAI_API_KEY` on the server, plus mic permission in the browser.
- **`socksio` import error** — only matters if you have a SOCKS HTTP proxy set in env vars; the guardrail catches it and the planner falls back to heuristic mode.
