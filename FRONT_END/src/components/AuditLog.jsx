// The ordered trace of tool calls (case.audit_log). Each entry: { step, tool, args, result, at }.
function summarize(result) {
  if (result == null) return "";
  if (typeof result === "string") return result;
  // pull a few human-friendly signals out of common result shapes
  const r = result;
  if (r.verified === false || r.found === false) return r.reason ?? "not found";
  if (r.booked) return `booked ${r.new_segment_id ?? r.confirmation ?? ""}`.trim();
  if (r.claim_ref) return `claim ${r.claim_ref}`;
  if (typeof r.amount === "number") return `${r.currency ?? "INR"} ${r.amount}`;
  const keys = Object.keys(r).slice(0, 3);
  return keys.map((k) => `${k}=${JSON.stringify(r[k])}`).join(", ");
}

export function AuditLog({ entries }) {
  if (!entries?.length) {
    return (
      <p className="px-1 py-4 text-center text-xs text-dim">
        No actions yet — the agent's tool calls will appear here.
      </p>
    );
  }
  return (
    <ol className="space-y-1.5">
      {entries.map((e, i) => (
        <li
          key={i}
          className="rounded-lg border border-line bg-card px-3 py-2 text-xs"
        >
          <div className="flex items-center justify-between gap-2">
            <span className="font-mono text-accent">{e.tool}</span>
            <span className="text-[10px] uppercase tracking-wide text-dim">
              {e.step}
            </span>
          </div>
          <p className="mt-0.5 truncate text-muted" title={summarize(e.result)}>
            {summarize(e.result) || "—"}
          </p>
        </li>
      ))}
    </ol>
  );
}
