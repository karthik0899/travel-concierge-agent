# Travel Concierge Agent — Frontend

Vanilla React (no framework) + Vite + Tailwind v4. A single-screen console for the
disruption-recovery agent: start a case, watch the 7-agent pipeline run live, answer
the agent's approval questions, and browse reference data.

## Run

```bash
npm install
npm run dev        # http://localhost:5173
```

The dev server proxies `/api/*` → the FastAPI backend (default `http://localhost:8000`).
Point it elsewhere with:

```bash
VITE_API_TARGET=http://localhost:9000 npm run dev
```

For a deployed build, set `VITE_API_BASE` to the backend origin (calls go straight
there; the backend already sends permissive CORS):

```bash
VITE_API_BASE=https://api.example.com npm run build
```

Make sure the backend is up first (`docker compose up -d` for the DB, then the
uvicorn server).

## What it does

- **Chat + live progress** — `POST /cases` then polls `GET /cases/{id}` every 1.5s,
  rendering the pipeline timeline, per-agent results, and the tool-call activity log.
- **Approval gates** — when a case is `awaiting_input`, the agent's question (and any
  options) render inline; your reply goes to `POST /cases/{id}/messages` and the
  pipeline resumes.
- **Provider toggle** — `cortex` vs `claude` (`GET /providers`); the server default is
  marked ★.
- **Demo prompts** — one-click scenarios from `GET /demos` (each has a valid PNR).
- **Reference panels** — bookings, flights, DGCA rules, and claims (read-only endpoints).

## Layout

```
src/
  api.js            fetch wrapper for every endpoint
  useCase.js        the start → poll → reply → terminal loop (custom hook)
  steps.js          pipeline metadata + status colors
  App.jsx           3-column layout
  components/
    Composer.jsx      new-case message box
    ProviderToggle.jsx
    DemoPicker.jsx
    Timeline.jsx      7-step pipeline tracker
    PendingPrompt.jsx awaiting_input question + reply
    Results.jsx       per-slice result cards
    AuditLog.jsx      tool-call trace
    SidePanels.jsx    bookings / flights / rules / claims
    Badge.jsx         status pill
```

The loop and endpoint contract are documented in `../docs/CHATBOT_CLIENT.md`.

## Note on providers

`claude` is the known-good provider. If `cortex` returns a 500 on starting a case,
the backend's Cortex gateway credentials (`CORTEX_API_KEY` / `CORTEX_BASE_URL`) are
unreachable or invalid — switch the toggle to `claude`.
