// The fixed pipeline (backend: app/application/workflow). `skill` is what the
// API reports as current_step; `slice` is the key under case.slices it writes.
export const PIPELINE = [
  { skill: "identity", slice: "identity", label: "Identity", icon: "🪪" },
  { skill: "disruption", slice: "assessment", label: "Assessment", icon: "🔎" },
  { skill: "rebooking", slice: "rebooking", label: "Rebooking", icon: "✈️" },
  { skill: "accommodation", slice: "accommodation", label: "Accommodation", icon: "🏨" },
  { skill: "compensation", slice: "compensation", label: "Compensation", icon: "💰" },
  { skill: "claim", slice: "claim", label: "Claim", icon: "📝" },
  { skill: "summary", slice: "summary", label: "Summary", icon: "🧾" },
];

export const STATUS_META = {
  open: { label: "Working", cls: "bg-sky-500/15 text-sky-300 border-sky-500/30" },
  awaiting_input: {
    label: "Needs you",
    cls: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  },
  rebooked: { label: "Rebooked", cls: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30" },
  compensated: {
    label: "Compensated",
    cls: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  },
  closed: { label: "Closed", cls: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30" },
  failed: { label: "Failed", cls: "bg-rose-500/15 text-rose-300 border-rose-500/30" },
};

export const fmtMoney = (m) =>
  m && typeof m.amount === "number"
    ? `${m.currency ?? "INR"} ${m.amount.toLocaleString()}`
    : "—";
