// Thin wrapper over the Travel Concierge Agent API.
// In dev, calls go to /api/* and Vite proxies them to the FastAPI backend
// (see vite.config.js). Override with VITE_API_BASE for a deployed backend.
const BASE = import.meta.env.VITE_API_BASE ?? "/api";

async function json(res) {
  if (!res.ok) {
    let detail = await res.text();
    try {
      detail = JSON.parse(detail).detail ?? detail;
    } catch {
      /* keep raw text */
    }
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json();
}

const get = (path) => fetch(`${BASE}${path}`).then(json);

const post = (path, body) =>
  fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).then(json);

// ---- Cases (the conversational loop) ---------------------------------------
export const startCase = (message, provider) =>
  post("/cases", { message, ...(provider ? { provider } : {}) });

export const getCase = (caseId) => get(`/cases/${caseId}`);

export const replyToCase = (caseId, message) =>
  post(`/cases/${caseId}/messages`, { message });

export const listCases = (limit = 50) => get(`/cases?limit=${limit}`);

// ---- Reference data (read-only, for the UI side panels) --------------------
export const getHealth = () => get("/health");
export const getProviders = () => get("/providers");
export const getDemos = () => get("/demos");
export const listBookings = () => get("/bookings");
export const listFlights = (params = {}) => {
  const q = new URLSearchParams(params).toString();
  return get(`/flights${q ? `?${q}` : ""}`);
};
export const listHotels = (nearAirport) =>
  get(`/hotels${nearAirport ? `?near_airport=${nearAirport}` : ""}`);
export const listRules = () => get("/rules");
export const listClaims = (limit = 50) => get(`/claims?limit=${limit}`);

export const TERMINAL_STATUSES = new Set([
  "closed",
  "rebooked",
  "compensated",
  "failed",
]);

export const isTerminal = (status) => TERMINAL_STATUSES.has(status);
