# Multi-Agent Trip Planner — How It Works

A practical guide to explain the project: what each piece does, how the agents
delegate work to each other, what external tools/APIs are used, and how a
single user message flows all the way to a PDF.

---

## 1. What the project is

An AI-powered Trip Planning Assistant. A user chats with it in natural
language (text or voice) — the system asks for a destination, dates, budget,
interests, then:

1. Greets the user and asks "How can I help?"
2. Checks the weather for the destination **first**.
3. Suggests places based on API data.
4. Coordinates many specialised agents (transport, hotel, budget, itinerary…).
5. Produces a downloadable PDF travel report.
6. Ends the conversation with **"Thank you, happy journey!"**

It is built as a true multi-agent system: a **Supervisor (Orchestrator)
Agent** decides which specialised agent runs next, retries failures, resolves
conflicts (e.g. budget overrun), and finally triggers PDF generation.

---

## 2. High-level architecture

```
User (browser chat — text + voice via OpenAI Realtime API)
         │
         ▼
FastAPI server  ──►  chat_flow.py  (conversational controller)
                         │
                         ▼
                LangGraph workflow
                         │
                         ▼
   ┌───────────────── Orchestrator Agent ──────────────────┐
   │  decides which agent runs, retries, resolves conflicts │
   └─────────┬────────────────────────────────────────────-─┘
             │
             ▼
   ┌────────────────────────────────────────────────────────┐
   │  Specialised agents (all read/write the shared TripState) │
   │                                                        │
   │  User Input · Memory · Weather · Places · Transport     │
   │  Hotel · Budget · Itinerary · Final Review · PDF Gen   │
   └────────────────────────────────────────────────────────┘
             │                       │
             ▼                       ▼
   External APIs              FAISS vector memory
   (OpenWeatherMap, Google    (past trip preferences)
    Places, Realtime API…)
```

Everything reads and writes one shared dictionary called **TripState** —
that's how agents pass information to each other without calling each other
directly.

---

## 3. The 11 agents and what each one does

| # | Agent | Responsibility | Source file |
|---|---|---|---|
| 1 | **User Input Agent** | Parse free-text user request into structured fields (source, destination, dates, budget, interests…). Uses a regex/heuristic parser as fallback when no OpenAI key, else asks GPT-4o for structured JSON. | `agents/user_input_agent.py` |
| 2 | **Memory Retrieval Agent** | Search the FAISS vector store for similar past trips by the same user — biases planning toward their known preferences. | `agents/memory_agent.py` |
| 3 | **Weather Agent** | Calls OpenWeatherMap (real API) for a 5-day forecast at the destination. Returns a per-day breakdown + a verdict (good / rainy / very_hot). | `agents/weather_agent.py` |
| 4 | **Transport Agent** | Searches flights and trains between source and destination, picks the cheapest matching the user's preferred mode. | `agents/transport_agent.py` |
| 5 | **Hotel Agent** | Finds hotels within budget band (budget / mid / luxury), with per-night and total cost. | `agents/hotel_agent.py` |
| 6 | **Places Explorer Agent** | Looks up the destination's top attractions and ranks **alternative destinations** that match the user's interests. | `agents/places_agent.py` |
| 7 | **Budget Agent** | Sums transport + hotel + food + activities + local transport + buffer. Reports overshoot and offers optimisation tips. | `agents/budget_agent.py` |
| 8 | **Itinerary Agent** | Builds a day-wise plan, respecting weather (indoor activities if rain) and using the attractions from agent #6. | `agents/itinerary_agent.py` |
| 9 | **Final Review Agent** | Validates that everything required is present and consistent. Reports any conflicts (e.g. hotel exceeds budget, weather is rainy). | `agents/review_agent.py` |
| 10 | **PDF Generator Agent** | Builds the final downloadable PDF (cover, weather, flights, hotels, day-wise itinerary, budget report, packing checklist, emergency contacts). | `agents/pdf_agent.py` |
| 11 | **Orchestrator Agent** | The brain. Decides the order, retries failures, resolves conflicts, approves the plan, and triggers the PDF. | `agents/orchestrator_agent.py` |

There's also a **Memory Update** node (after approval) that persists the
finalised trip preferences back into FAISS for future personalisation.

---

## 4. How delegation happens

This is the most important part to explain. The Orchestrator does **not**
call agents directly. Instead, all agents and the orchestrator live as
**nodes** in a LangGraph state graph. The orchestrator decides what the
*next* node should be by writing a value into `state["orchestrator_decision"]
["next"]`. A conditional edge in the graph reads that value and routes to the
matching agent node.

### The decision tree (Orchestrator step 2 — Route to agents)

```python
if missing_inputs:          next = "await_user_input"
elif no weather data:       next = "weather"        ← user's rule: weather FIRST
elif no places data:        next = "places"
elif no transport data:     next = "transport"
elif no hotel data:         next = "hotel"
elif no budget summary:     next = "budget"
elif no itinerary:          next = "itinerary"
elif no review status:      next = "review"
else:                       next = "validate"
```

After each specialised agent runs, control returns to the Orchestrator, which
looks at the updated state and decides what's next. This is a classic
**Supervisor pattern** — the orchestrator is the only node that holds the
"what should we do next?" logic. Workers are pure functions of state.

### Conflict resolution (Orchestrator step 3)

The `orchestrator_validation` node runs after Final Review and applies these
rules:

- **Budget overshoot** → re-run the Hotel Agent at a lower price band (mid → budget, luxury → mid). Drop the previous hotel + budget output so they recompute.
- **Heavy rain forecast** → re-run the Places Agent once for indoor-friendly suggestions.
- **Failed agent / missing data** → retry the failing agent up to `MAX_RETRIES = 2`.

Each retry increments a counter in `state["retry_counts"]` so we don't loop
forever. If we run out of retries, the orchestrator approves the plan anyway
(with a "caveat") so the user always gets a PDF.

### Final approval + PDF trigger (steps 5 + 6)

Only when `review.approved == True` AND no retries are queued does the graph
proceed to:

```
validate → memory_update → pdf → END
```

The PDF Generator refuses to run unless `review_status.approved == True`, so
the supervisor really is gating the final output.

---

## 5. The conversational flow on top of the graph

`chat_flow.py` is a thin controller that sits between the FastAPI endpoint
and the LangGraph workflow. It enforces the specific script you asked for:

1. **Greet** — say hello and ask "How can I help you?"
2. **Collect** — extract destination, source, dates, budget, interests from
   each user message. If anything is missing, list it back and ask for it.
3. **Check weather FIRST** — as soon as we have a destination, call the
   Weather Agent + Places Agent and present the forecast + suggestions.
4. **Confirm or suggest alternatives** — if the forecast is rainy, offer to
   suggest a drier destination via the Places Explorer.
5. **Run the full graph** when the user says *"plan it"*.
6. **Reset state** if the previous trip was already done, so the next message
   starts a fresh plan rather than extending Goa with Mysore data.
7. **End with "Thank you, happy journey!"** after the PDF is delivered.

`chat_flow.py` is also where the session state lives — keyed by `session_id`
via `memory/session_memory.py`. Each browser tab gets its own session.

---

## 6. Tools and APIs

| Layer | Tool | Real or mock | Source file |
|---|---|---|---|
| LLM (chat) | OpenAI GPT-4o-mini | Real if `OPENAI_API_KEY` set | `agents/_llm.py` |
| LLM (voice) | OpenAI Realtime API (WebRTC) | Real if `OPENAI_API_KEY` set | `api/server.py` + `frontend/index.html` |
| Embeddings (memory) | OpenAI text-embedding-3-small | Real if key set, hashed fallback otherwise | `memory/vector_memory.py` |
| Weather | OpenWeatherMap forecast + geocoding | **Real** if `OPENWEATHER_API_KEY` set | `tools/weather_api.py` |
| Places | Google Places Text Search | Real if `GOOGLE_PLACES_API_KEY` set, curated catalog otherwise | `tools/places_api.py` |
| Transport | Flight + train search | Mock with realistic per-km pricing | `tools/transport_api.py` |
| Hotels | Booking-style search | Mock with realistic price bands | `tools/hotel_api.py` |
| Budget | Python calculator (no API) | Real | `tools/budget_calc.py` |
| Web search (tips) | Curated travel-tips lookup | Mock (replaceable with Tavily/SerpAPI) | `tools/web_search.py` |
| Vector DB | FAISS `IndexFlatIP` (cosine) | Real, local | `memory/vector_memory.py` |
| Session memory | In-memory dict (Redis-style API) | Real, local | `memory/session_memory.py` |
| PDF | ReportLab platypus | Real, local | `agents/pdf_agent.py` |
| Graph runtime | LangGraph `StateGraph` | Real | `graph.py` |
| HTTP server | FastAPI + Uvicorn | Real | `api/server.py` |

The architecture matches the assignment PDF spec exactly. Anything not wired
to a real API is mocked with realistic data so the project runs end-to-end
out of the box.

---

## 7. State schema

A single TypedDict (`state.py`) is the canonical place to look at "what does
the system know right now?" Mirrors the PDF spec:

```python
class TripState(TypedDict, total=False):
    messages: list                        # full chat transcript
    conversation_stage: str               # greet | collect | confirm | plan | done

    user_profile: dict
    trip_preferences: dict                # source, destination, dates, budget…
    weather_data: dict                    # OpenWeatherMap output + verdict
    hotel_data: dict
    transport_data: dict
    places_data: dict                     # attractions + alt suggestions
    budget_summary: dict                  # totals + overshoot + tips
    itinerary: dict                       # day-wise plan
    review_status: dict                   # approved / issues / needs_retry
    pdf_status: dict
    orchestrator_decision: dict           # next, missing_inputs, retry, caveat

    memory_hits: list                     # FAISS retrieval results
    retry_counts: dict                    # per-agent retry counters
    errors: list

    pdf_path: str | None
    final_message: str | None
```

---

## 8. End-to-end example: "Plan a 3-day Mysore trip from Bangalore"

1. **Turn 1** — user message arrives.
   `chat_flow.chat_turn()` appends the message to state and calls the
   **User Input Agent** directly to extract prefs. Result:
   `{destination: "Mysore", source: "Bangalore", duration_days: 3, ...}`

2. Still missing budget. The controller asks the user for it.

3. **Turn 2** — user adds budget and interests.
   User Input Agent runs again and fills in the gaps.

4. **Weather first** — the controller calls the **Weather Agent** (real
   OpenWeatherMap if key is set). Also calls the **Places Agent** to get
   Mysore Palace, Chamundi Hills, etc., plus suggestions for alternative
   destinations. Replies with weather forecast + attractions.

5. **Turn 3** — user says *"plan it"*.
   The controller now hands the entire state to the LangGraph workflow:

   ```
   user_input → memory_retrieval → orchestrator
   orchestrator → weather (already done — skipped)
   orchestrator → places (already done — skipped)
   orchestrator → transport     → orchestrator
   orchestrator → hotel         → orchestrator
   orchestrator → budget        → orchestrator
   orchestrator → itinerary     → orchestrator
   orchestrator → review        → validate
   validate (no conflicts) → memory_update → pdf → END
   ```

6. The PDF Generator writes `outputs/TripPlan_Mysore_<hash>.pdf` with cover,
   weather, flights, hotels, day-wise itinerary, budget report, packing
   checklist, and emergency contacts.

7. The controller replies with the summary, a download link, and
   **"Thank you, happy journey!"** — and marks the conversation `done`.

8. If the user starts a new message after this, the controller resets the
   working state so the next trip is independent.

---

## 9. Where the assignment's "agent steps" live in code

| Assignment step | Where in code |
|---|---|
| Step 1 — Understand user goal | `agents/orchestrator_agent.py :: orchestrator_agent()` (decides `missing_inputs`, `next`) |
| Step 2 — Route to agents | Same function — sets `orchestrator_decision.next`; conditional edge in `graph.py :: _route_after_orchestrator` |
| Step 3 — Resolve conflicts | `orchestrator_validation()` — handles budget overshoot, rainy weather |
| Step 4 — Retry failed tasks | `orchestrator_validation()` — uses `retry_counts` with `MAX_RETRIES` |
| Step 5 — Final approval | `orchestrator_validation()` — sets `decision.approved = True` only when checks pass |
| Step 6 — Trigger PDF | `graph.py` — only after `memory_update` does the graph reach the `pdf` node |

---

## 10. Tech stack summary

- **LangGraph** for the multi-agent state machine
- **OpenAI GPT-4o-mini** (chat) and **Realtime API** (voice, WebRTC)
- **FastAPI** + plain HTML/JS chat frontend
- **FAISS** vector store + OpenAI embeddings (with a deterministic hashed
  fallback so the system never breaks)
- **OpenWeatherMap** for real weather
- **ReportLab** for PDF generation
- **httpx** for HTTP calls, **Pydantic** for request/response models
- **Python 3.10+**

---

## 11. How to talk about it in one minute

> "It's a production-style agentic AI trip planner. A user chats with it
> over text or voice, and a Supervisor Agent — implemented in LangGraph —
> orchestrates ten specialised agents that each handle one slice of the
> work: weather, places, transport, hotels, budget, itinerary, and so on.
> All agents read and write a single shared state, and the supervisor uses
> that state to decide which agent runs next, when to retry, and when to
> resolve conflicts like budget overshoot. The system always checks weather
> first, then suggests places based on the user's interests, then runs the
> rest of the agents to build a complete plan. At the end, a PDF generator
> turns the state into a downloadable trip report and the bot signs off
> with 'thank you, happy journey'. Real APIs are wired in (OpenAI for the
> chat brain and voice, OpenWeatherMap for live weather); others are
> mocked with realistic data so the project runs out of the box."
