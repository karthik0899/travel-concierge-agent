# Developer Notes — Travel Concierge Agent

Internal design notes for engineers working on this codebase. The top-level
`BACKEND/travel_concierge_agent/README.md` covers setup/run; this document
covers **how it works and why it's built this way**.

---

## 1. The idea in one paragraph

A customer describes a flight disruption in plain language. The system runs a
**deterministic pipeline of seven specialised agents** (identity → disruption
assessment → rebooking → accommodation → compensation → claim → summary), each of
which is the *same general engine* configured by a **skill** (persona + scoped
tools + output schema). Agents never call each other — they read and write one
shared **CaseFile**. Tools are the only things that touch the world (a PostgreSQL
database). Compensation follows **Indian aviation law** (DGCA CAR Section 3 and
the Carriage by Air Act), encoded as data, not magic numbers.

---

## 2. Architecture at a glance

```
 free-text message
        │
        ▼
   intake  ─────────────────────► DisruptionReport {booking_ref, disruption_type}
        │                          (one LLM call, no tools)
        ▼
  Orchestrator  ── fixed pipeline; branches on structured signals
        │            persists progress after every step
        ▼                                        ┌──────────────────────────────┐
  General Agent Engine (agent/runner.py)         │  CaseFile (persisted, JSONB)  │
        │  loose tool-calling loop per skill ───►│  report + 7 slices + audit    │
        │  via a Provider                        └──────────────────────────────┘
        ▼
  Provider  ── Claude (Agent SDK, prompted tools)  |  Cortex (OpenAI, native tools)
        │
        ▼
  Tools  ── flat registry; each skill is scoped by allowed_tools
        │
        ▼
  PostgreSQL 18  ── "the world": bookings, flights, hotels, customers,
                     DGCA + baggage rules, claims, case_files
        │
        ▼
  Notifications  ── Twilio SMS on each case transition (best-effort)
```

Three layers, cleanly separated:

| Layer | Owns | Lives in |
|-------|------|----------|
| **Orchestration** | order + branching + persistence | `app/application/` |
| **Agent engine + skills** | reasoning, parameterised per skill | `app/agent/` |
| **Tools** | the actual work / data access | `app/tools/` + `app/db/` |

The two providers only differ *inside* the engine layer — the orchestration and
tool layers are provider-agnostic, which keeps the Claude-vs-Cortex comparison
honest (same path, same tools, same DB).

---

## 3. Request lifecycle

1. **Intake** (`app/application/intake.py`) — one LLM call extracts
   `booking_ref` + `disruption_type` from the message (regex fallback for the PNR).
2. **`Orchestrator.begin`** — creates a `case_files` row (`status=open`), fires
   the `opened` SMS, returns a `case_id` immediately (API responds `202`).
3. **`Orchestrator.execute`** — walks `workflow.STEPS` in order; for each step
   whose predicate passes, runs the skill through the engine, merges the result
   slice into the CaseFile, appends the audit trail, persists.
4. **Pause** — if an agent calls `request_user_input`, the engine stops; the
   orchestrator saves `pending` (the question) + `runstate` (engine messages),
   sets `status=awaiting_input`, and returns. The customer answers via
   `POST /cases/{id}/messages` → **`Orchestrator.resume`** continues the same
   agent loop with the answer injected.
5. **Close** — after the last step, `status` becomes `closed` (or `failed` if
   identity didn't verify); `runstate` is cleared; the `closed` SMS fires.

---

## 4. Core concepts

### CaseFile & slices (`app/domain/case_file.py`)
The CaseFile is the **shared case file for one disruption journey** — opened on
report, passed through each agent, closed as the audit record. It is a sum of
**slices**, one per agent:

| Slice | Written by | Key fields |
|-------|-----------|-----------|
| `identity` | identity | `verified`, `loyalty_tier`, `itinerary` |
| `assessment` | disruption | `cause` (the hinge), `needs_rebooking`, `needs_accommodation` |
| `rebooking` | rebooking | `selected`, `booked`, `overnight_required` |
| `accommodation` | accommodation | `selected`, `booked`, `confirmation` |
| `compensation` | compensation | `eligible`, `amount`, `rule_id`/`baggage_rule_id` |
| `claim` | claim | `claim_submitted`, `claim_ref` |
| `summary` | summary | `narrative`, `actions_taken`, `confirmations`, `next_steps` |

Rules: **an agent writes only its own slice**; the orchestrator owns the merge.
The four **branch signals** (`identity.verified`, `assessment.needs_rebooking`,
`needs_accommodation`/`rebooking.overnight_required`, `compensation.eligible`)
are typed fields — branching is data, not LLM routing.

### Skills — agents as folders (`app/agent/<name>/`)
Each agent is a folder, not bespoke code:
```
agent/identity/
  SKILL.md      # frontmatter (name, description, allowed_tools, max_steps, model) + persona
  schema.json   # the output slice's JSON Schema (generated from the Pydantic model)
  __init__.py   # SKILL = load_skill(this dir)
```
`_skill.py` parses these into a `Skill` dataclass; `load_all()` discovers every
folder. Adding/editing an agent is editing files, not writing a class.

### The engine (`app/agent/runner.py`)
One **loose tool-calling loop** runs *any* skill:
```
system = persona + output schema + "finish with JSON"
loop up to skill.max_steps:
    turn = provider.complete(system, messages, tools=scoped)
    if tool_calls:  run them, feed results back (errors become results, never raise)
    else:           parse the text as result JSON, validate vs the slice schema
                    valid → done;  invalid → feed errors back, retry
last step forces a text answer so the loop always terminates
```
The engine is **provider-agnostic and domain-agnostic**: it takes a `Skill` + a
context dict and returns an `AgentResult` (slice + audit, or a paused state). It
imports neither the providers nor the CaseFile.

### Tools & the registry (`app/tools/`)
One flat folder; each tool is `schema.py` (function-calling spec) + `tool.py`
(`run(**args)`). The registry maps name → module. A skill is granted a subset via
`allowed_tools` in its frontmatter — **that list is the scoping and the safety
boundary** (e.g. the compensation agent literally cannot call `book_flight`).
Everything reads/writes through the single data doorway `app/db/connection.py`.

### Orchestrator & workflow (`app/application/`)
- `workflow/__init__.py` — `STEPS`: the fixed order + a `should_run(case)`
  predicate per step.
- `orchestrator/__init__.py` — runs the steps, merges slices, fires SMS,
  handles pause/resume.
- `orchestrator/persistence.py` — the only writer of `case_files`; also
  `load_case` (reconstructs a CaseFile for resume) and runstate save/clear.

### Providers (`app/llm/`)
Both implement one Protocol —
`complete(system, messages, tools, model, temperature, force_text) -> {text, tool_calls}`:
- **CortexProvider** — Gemini via the Cortex OpenAI-compatible gateway, **native
  function calling**.
- **ClaudeProvider** — Claude Agent SDK (Claude Code auth, no API key). The SDK
  does text, so tool-calling is a **prompted JSON protocol**: the model emits
  `{"tool_call": {...}}` to call a tool or its result JSON to finish. The engine
  loop is identical either way.

Select with `LLM_PROVIDER=cortex|claude` (or `--provider` / the API `provider` field).

### Multi-turn approval gates (pause/resume)
A control tool, `request_user_input(question, options?)`, is in the registry but
**never executed** — when a gated agent (rebooking, accommodation) calls it, the
engine pauses and hands back the conversation. The orchestrator persists it and
waits for `POST /cases/{id}/messages`. Resume re-enters the same agent loop with
the customer's reply appended as the tool's answer. Gated steps: rebooking and
accommodation; identity/disruption/compensation/claim run automatically.

### Notifications (`app/notifications/`)
`notify(case, event)` sends a Twilio SMS on `opened`, `rebooked`, `hotel`,
`claim`, `closed`/`failed`. Best-effort (never raises), no-op-with-log when Twilio
isn't configured. `NOTIFY_OVERRIDE_PHONE` routes all SMS to one number (demo /
trial accounts). Lives in the orchestrator, not the tools, so world-mutation
stays side-effect-free.

---

## 5. Data model (PostgreSQL 18)

`app/db/schema.sql` (DDL + the rules, which ARE the law) and `seed.sql` (demo
world). Highlights:

- **`flights`** — both the customer's itinerary source *and* the rebooking
  supply. `cancel_cause` (`airline_fault` | `extraordinary_circumstance`) is the
  hinge for compensation; `block_minutes` is a generated column (the band key).
- **`booking_segments`** — the booking↔flights join; `segment_order` makes
  missed connections detectable.
- **`bookings`** — fare decomposed into `basic_fare` + `fuel_charge` + `taxes_fees`
  because DGCA compensation is `min(cap, multiplier × (basic_fare + fuel_charge))`.
- **`dgca_compensation_rules`** — cancellation (block-time bands) + denied
  boarding (alt-delay bands), with a CHECK enforcing the right band shape per event.
- **`baggage_liability_rules`** — Carriage by Air Act / Montreal (weight × per-kg,
  capped), with statutory claim deadlines.
- **`case_files`** — the persisted CaseFile: `report`, `slices`, `audit_log`,
  `pending`, `runstate` as JSONB + a GIN index on `slices`. `booking_ref` is a
  nullable FK set only once identity verifies (so failed verifications still persist).

PG18 specifics used: `uuidv7()` PKs, virtual generated columns (`block_minutes`,
`delay_hours`), partial indexes for the search hot paths.

---

## 6. The compensation logic (three regimes)

`calculate_compensation` dispatches on `event_type` — this is *why* it can't be
one formula:

| Event | Basis | Formula | Source |
|-------|-------|---------|--------|
| `cancellation` | flight block time + cause + notice | `min(cap, 1.0 × (basic+fuel))`, **₹0 if extraordinary** | DGCA CAR S3 M IV |
| `denied_boarding` | hours to the alternate flight | `min(cap, {2,4}× (basic+fuel))` | DGCA CAR S3 M IV |
| `*_baggage` | bag weight + jurisdiction | domestic `min(₹20k, ₹450×kg)`; intl Montreal cap | Carriage by Air Act 1972 |

All amounts come from the rule tables — the agent never does arithmetic.

---

## 7. API surface (`app/api/main.py`)

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/cases` | submit a disruption message → `202 {case_id}` (runs async) |
| `POST` | `/cases/{id}/messages` | answer a pending question → resumes (async) |
| `GET` | `/cases` · `/cases/{id}` | history list · full case (poll here) |
| `GET` | `/bookings[/{ref}]` · `/customers[/{id}]` · `/flights[/{no}]` · `/airports` · `/hotels` | world data |
| `GET` | `/rules` · `/claims` | the law (for transparency) · filed claims |
| `GET` | `/health` · `/providers` · `/demos` | meta |

Async job pattern: `POST` returns `202` immediately and runs the pipeline in a
FastAPI BackgroundTask; the UI polls `GET /cases/{id}` and watches `current_step`
/ `pending` advance. CORS is open for dev. Swagger at `/docs`.

---

## 8. CLI (`cli.py`)

```
uv run cli.py "<message>" [--provider claude|cortex] [--yes]
uv run cli.py --demo --provider claude        # all six seeded scenarios
```
`--yes` auto-approves the multi-turn gates (otherwise it prompts on stdin).

---

## 9. Extending the system

**Add a tool**
1. `app/tools/<name>/schema.py` — `SCHEMA = {name, description, parameters}`.
2. `app/tools/<name>/tool.py` — `def run(**args)` (go through `app.db.connection`).
3. `app/tools/<name>/__init__.py` — re-export.
4. Register it in `app/tools/__init__.py` (`_MODULES`).
5. Add the name to the relevant skill's `allowed_tools`.

**Add a skill (agent)**
1. `app/agent/<name>/SKILL.md` (frontmatter + persona) + `schema.json` (the slice).
2. Add a slice model to `app/domain/case_file.py` and a `(attr, model)` entry in
   the orchestrator's `_SLICE`.
3. Add a `Step(<name>, predicate)` to `workflow.STEPS` in the right position.

**Add an approval gate** — give the skill `request_user_input` in `allowed_tools`
and instruct the persona to call it before committing.

**Add a disruption type / rule** — extend the enums (DB + `app/domain/enums.py`),
add rows to the rule tables, and handle the event in `calculate_compensation`.

---

## 10. Design decisions & rationale

- **Fixed pipeline + structured-signal branching** (not a free-form supervisor):
  the journey is inherently linear; deterministic order is testable, auditable,
  and keeps the provider comparison clean. Adaptivity lives *inside* steps (the
  loose loop) and in typed branch flags, not in an LLM router.
- **One engine + skills-as-data** (not 7 bespoke agents): DRY, provider parity,
  agents become config. The real differentiation is `allowed_tools` + output
  schema, not just the persona text.
- **Agents finish via final JSON, not a `submit_result` tool**: avoids the
  nested-schema-as-tool-parameters problem and works identically for both providers.
- **Compensation in the DB, not code**: defensible, auditable, and updatable
  without a deploy; the agent reasons over real rules.
- **CaseFile persisted as JSONB**: gives the audit story, resumability, and
  A/B comparison by `provider` — for a banking-style audience this matters.
- **Notifications in the orchestrator, not tools**: keeps the world-mutation
  layer free of external side-effects and testable.
- **Pause/resume via a control tool**: keeps agents genuinely in control of when
  to ask, rather than the orchestrator second-guessing them.

---

## 11. Testing

Validation was done against a real PostgreSQL 18 (Docker) with the schema + seed
loaded, using a **scripted mock provider** that drives the engine deterministically
(so tests don't depend on a live LLM), plus live runs against the Claude Agent SDK.
Coverage: each tool, the engine loop (retry / error-as-result / exhaustion), both
providers, the full orchestration across all branches, the API endpoints, and the
multi-turn pause/resume cycle.

---

## 12. Known limitations / TODO

- **Hotel check-in/out times**: the accommodation agent occasionally picks
  slightly odd clock times — tighten the persona to derive them from the
  disruption time and the rebooked departure.
- **Intake requires the PNR in the message** — no flight→booking lookup; a real
  product would ask a clarifying question instead of erroring.
- **Single-leg assumptions** in a few places (e.g. itinerary[0]) — multi-leg
  missed-connection handling is modelled in the DB but lightly exercised.
- **No auth / rate limiting** on the API (dev CORS is wide open).
- **Concurrency**: background tasks run in-process; a real deployment would use
  a job queue.

---

## 13. Project layout

```
BACKEND/travel_concierge_agent/
  app/
    agent/        7 skills + runner.py (engine) + _skill.py (loader)
    api/main.py   FastAPI
    application/  orchestrator/ (pipeline, persistence) + workflow/ + intake.py
    tools/        9 tools (8 + request_user_input) + registry
    db/           connection.py + schema.sql + seed.sql
    domain/       case_file.py + enums.py
    llm/          dispatcher + claude_provider + cortex_provider
    notifications/ Twilio SMS
    utils/        constants, serialize, jsonx
  cli.py · docker-compose.yml · pyproject.toml · README.md
FRONT_END/        (placeholder)
docs/             this file
```
