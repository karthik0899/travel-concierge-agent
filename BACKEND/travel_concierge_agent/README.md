# Travel Concierge Agent

A multi-agent system that handles the full recovery journey when a customer's
flight is disrupted — verification, assessment, rebooking, accommodation,
compensation, and claims — under **Indian aviation law (DGCA CAR Section 3 /
Carriage by Air Act)**.

## Design in one picture

```
DisruptionReport
      │
      ▼
Orchestrator  ── fixed pipeline, branches on structured signals ──► CaseFile (persisted, JSONB)
      │                                                                   ▲
      │  for each step, runs a Skill through ...                          │ merges each slice
      ▼                                                                   │
General Agent Engine (agent/runner.py)  ── loose tool-calling loop ───────┘
      │  via a Provider (Cortex native tools | Claude prompted tools)
      ▼
Tools (flat registry, scoped per skill by allowed_tools)
      │
      ▼
Postgres 18  ── the "world": bookings, flights, hotels, DGCA & baggage rules
```

- **One general engine, seven skills.** Each agent is a folder (`SKILL.md` +
  `schema.json`), not bespoke code — persona + scoped tools + output schema.
- **Fixed pipeline, structured-signal branching.** Order is deterministic;
  whether a step runs is decided by typed flags (`verified`, `needs_rebooking`,
  `needs_accommodation`, `eligible`) — not LLM routing.
- **Two interchangeable providers** behind one Protocol: Cortex (Gemini, native
  function calling) and Claude (Agent SDK, prompted JSON tool protocol).
- **Compensation is data, not magic numbers.** DGCA block-time / denied-boarding
  rules and baggage liability live in the DB; tools compute `min(cap, …)`.

## Layout

```
app/
  agent/        7 skills (identity, disruption, rebooking, accommodation,
                compensation, claim, summary) + runner.py (the engine) + _skill.py
  api/main.py   FastAPI app
  application/  orchestrator/ (pipeline + persistence) + workflow/ (steps + branches)
  tools/        8 tools (schema.py + tool.py) + registry
  db/           connection.py + schema.sql + seed.sql
  domain/       case_file.py (CaseFile + slices) + enums.py
  utils/        constants.py, serialize.py, jsonx.py
  llm/          dispatcher + cortex_provider.py + claude_provider.py
cli.py
```

## Setup

Uses [uv](https://docs.astral.sh/uv/).

```bash
uv sync                       # create .venv from pyproject.toml / uv.lock
cp .env.example .env          # set DATABASE_URL + provider keys

# create the database (Postgres 18)
psql "$DATABASE_URL" -f app/db/schema.sql   # tables + DGCA/baggage rules (the law)
psql "$DATABASE_URL" -f app/db/seed.sql     # demo world: 6 PNRs, flights, hotels
```

## Run

```bash
# CLI — one scenario, or all six demos
uv run cli.py PNR001 cancelled_flight "6E2341 DEL-BOM cancelled tonight"
uv run cli.py --demo
uv run cli.py PNR005 lost_baggage "Baggage lost on UK945" --provider claude

# API
uv run uvicorn app.api.main:app --reload
#   POST /cases  {"booking_ref":"PNR001","disruption_type":"cancelled_flight","raw_text":"..."}
#   GET  /cases/{case_id}
#   GET  /health
```

## Demo scenarios (seeded)

| PNR | Disruption | Exercises |
|-----|------------|-----------|
| PNR001 | Cancelled (airline fault) | rebook + overnight hotel + **₹9,500** compensation |
| PNR002 | Cancelled (weather) | rebook + hotel, **₹0** (extraordinary circumstance) |
| PNR003 | Missed connection | rebook leg 2 only |
| PNR004 | Denied boarding | rebook + **₹10,000** (200% capped) |
| PNR005 | Lost baggage | claim only (no rebook/hotel) — **₹8,325** (₹450/kg) |
| PNR006 | 4h delay | duty of care, no cash |
```
