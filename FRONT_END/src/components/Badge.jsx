import { STATUS_META } from "../steps.js";

export function StatusBadge({ status }) {
  const meta = STATUS_META[status] ?? {
    label: status ?? "—",
    cls: "bg-strong text-fg border-strong",
  };
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium ${meta.cls}`}
    >
      {status === "open" && (
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-current" />
      )}
      {meta.label}
    </span>
  );
}
