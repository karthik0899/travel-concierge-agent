// Prebuilt demo prompts from GET /demos (each has a valid PNR baked in).
export function DemoPicker({ demos, onPick, disabled }) {
  if (!demos?.length) return null;
  return (
    <div className="space-y-2">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
        Demo scenarios
      </p>
      <div className="flex flex-col gap-1.5">
        {demos.map((msg, i) => (
          <button
            key={i}
            onClick={() => onPick(msg)}
            disabled={disabled}
            className="group rounded-lg border border-ink-700 bg-ink-850 px-3 py-2 text-left text-xs text-slate-300 transition hover:border-sky-500/50 hover:bg-ink-800 disabled:opacity-50"
          >
            {msg}
          </button>
        ))}
      </div>
    </div>
  );
}
