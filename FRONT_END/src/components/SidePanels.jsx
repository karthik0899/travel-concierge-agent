import { useEffect, useState } from "react";
import { listBookings, listClaims, listFlights, listRules } from "../api.js";

const TABS = ["Bookings", "Flights", "Rules", "Claims"];

export function SidePanels({ onUseBooking }) {
  const [tab, setTab] = useState("Bookings");
  return (
    <div className="flex h-full flex-col">
      <div className="flex gap-1 border-b border-ink-800 px-2 pb-2">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`rounded-md px-2.5 py-1 text-xs font-medium transition ${
              tab === t ? "bg-ink-800 text-sky-300" : "text-slate-500 hover:text-slate-300"
            }`}
          >
            {t}
          </button>
        ))}
      </div>
      <div className="flex-1 overflow-y-auto p-2">
        {tab === "Bookings" && <Bookings onUseBooking={onUseBooking} />}
        {tab === "Flights" && <Flights />}
        {tab === "Rules" && <Rules />}
        {tab === "Claims" && <Claims />}
      </div>
    </div>
  );
}

function useFetch(fn, deps = []) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  useEffect(() => {
    let alive = true;
    fn()
      .then((d) => alive && setData(d))
      .catch((e) => alive && setErr(e.message));
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return [data, err];
}

const Loading = ({ err }) =>
  err ? (
    <p className="p-2 text-xs text-rose-400">{err}</p>
  ) : (
    <p className="p-2 text-xs text-slate-600">Loading…</p>
  );

function Bookings({ onUseBooking }) {
  const [data, err] = useFetch(listBookings);
  if (!data) return <Loading err={err} />;
  return (
    <div className="space-y-1.5">
      {data.bookings.map((b) => (
        <button
          key={b.booking_ref}
          onClick={() => onUseBooking?.(b)}
          className="block w-full rounded-lg border border-ink-800 bg-ink-900/60 p-2 text-left transition hover:border-sky-500/40"
        >
          <div className="flex items-center justify-between">
            <span className="font-mono text-xs text-sky-300">{b.booking_ref}</span>
            <span className="text-[10px] uppercase text-slate-500">{b.status}</span>
          </div>
          <p className="text-xs text-slate-300">{b.name}</p>
          {b.route && <p className="text-[11px] text-slate-500">{b.route}</p>}
        </button>
      ))}
    </div>
  );
}

function Flights() {
  const [data, err] = useFetch(() => listFlights({ limit: 40 }));
  if (!data) return <Loading err={err} />;
  return (
    <div className="space-y-1.5">
      {data.flights.map((f, i) => (
        <div key={i} className="rounded-lg border border-ink-800 bg-ink-900/60 p-2 text-xs">
          <div className="flex items-center justify-between">
            <span className="font-mono text-slate-200">{f.flight_no}</span>
            <span
              className={
                f.status === "cancelled"
                  ? "text-rose-400"
                  : f.status === "delayed"
                    ? "text-amber-400"
                    : "text-emerald-400"
              }
            >
              {f.status}
              {f.delay_minutes ? ` +${f.delay_minutes}m` : ""}
            </span>
          </div>
          <p className="text-slate-400">
            {f.origin}→{f.destination} · {f.airline}
          </p>
        </div>
      ))}
    </div>
  );
}

function Rules() {
  const [data, err] = useFetch(listRules);
  if (!data) return <Loading err={err} />;
  return (
    <div className="space-y-2">
      <h5 className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
        Compensation (DGCA)
      </h5>
      {data.compensation.map((r, i) => (
        <div key={i} className="rounded-lg border border-ink-800 bg-ink-900/60 p-2 text-xs">
          <p className="text-slate-300">{r.event_type}</p>
          <p className="text-slate-500">
            {r.car_ref}
            {r.cap_amount ? ` · cap ${r.currency} ${r.cap_amount}` : ""}
          </p>
        </div>
      ))}
    </div>
  );
}

function Claims() {
  const [data, err] = useFetch(() => listClaims(30));
  if (!data) return <Loading err={err} />;
  if (!data.claims.length)
    return <p className="p-2 text-xs text-slate-600">No claims yet.</p>;
  return (
    <div className="space-y-1.5">
      {data.claims.map((c) => (
        <div key={c.claim_ref} className="rounded-lg border border-ink-800 bg-ink-900/60 p-2 text-xs">
          <div className="flex items-center justify-between">
            <span className="font-mono text-sky-300">{c.claim_ref}</span>
            <span className="text-[10px] uppercase text-slate-500">{c.status}</span>
          </div>
          <p className="text-slate-400">
            {c.booking_ref} · {c.event_type} · {c.currency} {c.amount}
          </p>
        </div>
      ))}
    </div>
  );
}
