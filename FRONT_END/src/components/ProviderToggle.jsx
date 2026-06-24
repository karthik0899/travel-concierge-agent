// cortex vs claude. `default` highlights the server's configured default.
export function ProviderToggle({ value, options = ["cortex", "claude"], defaultProvider, onChange, disabled }) {
  return (
    <div className="inline-flex rounded-lg border border-strong bg-elevated p-0.5">
      {options.map((p) => (
        <button
          key={p}
          onClick={() => onChange(p)}
          disabled={disabled}
          className={`rounded-md px-3 py-1 text-xs font-medium capitalize transition disabled:opacity-50 ${
            value === p ? "bg-sky-600 text-white" : "text-muted hover:text-fg"
          }`}
          title={p === defaultProvider ? "server default" : undefined}
        >
          {p}
          {p === defaultProvider ? " ★" : ""}
        </button>
      ))}
    </div>
  );
}
