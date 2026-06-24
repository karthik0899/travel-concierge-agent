import { useState } from "react";

// Shown when status === "awaiting_input". case.pending = { question, options? }.
export function PendingPrompt({ pending, onReply, disabled }) {
  const [text, setText] = useState("");
  const options = pending?.options ?? [];

  const reply = (val) => {
    const t = (val ?? text).trim();
    if (!t || disabled) return;
    onReply(t);
    setText("");
  };

  return (
    <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-4">
      <p className="mb-3 text-sm font-medium text-amber-200">
        🤝 {pending?.question ?? "The agent needs your input."}
      </p>

      {options.length > 0 && (
        <div className="mb-3 flex flex-wrap gap-2">
          {options.map((opt, i) => (
            <button
              key={i}
              onClick={() => reply(opt)}
              disabled={disabled}
              className="rounded-lg border border-amber-500/40 bg-amber-500/10 px-3 py-1.5 text-xs font-medium text-amber-100 transition hover:bg-amber-500/20 disabled:opacity-50"
            >
              {opt}
            </button>
          ))}
        </div>
      )}

      <div className="flex items-end gap-2">
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && reply()}
          disabled={disabled}
          placeholder="Type your answer…"
          className="flex-1 rounded-lg border border-ink-700 bg-ink-900 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:border-amber-500/60 focus:outline-none disabled:opacity-50"
        />
        <button
          onClick={() => reply()}
          disabled={disabled || !text.trim()}
          className="rounded-lg bg-amber-500 px-4 py-2 text-sm font-semibold text-ink-950 transition hover:bg-amber-400 disabled:opacity-40"
        >
          Reply
        </button>
      </div>
    </div>
  );
}
