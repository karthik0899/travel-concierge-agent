import { useState } from "react";

// The message box. Used to start a new case (PNR must be in the text).
export function Composer({ onSend, disabled, placeholder }) {
  const [text, setText] = useState("");

  const send = () => {
    const t = text.trim();
    if (!t || disabled) return;
    onSend(t);
    setText("");
  };

  return (
    <div className="flex items-end gap-2">
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            send();
          }
        }}
        rows={2}
        disabled={disabled}
        placeholder={placeholder ?? "Describe the disruption… include the PNR, e.g. “…booking PNR001…”"}
        className="min-h-[52px] flex-1 resize-none rounded-xl border border-strong bg-elevated px-4 py-3 text-sm text-fg placeholder:text-dim focus:border-sky-500/60 focus:outline-none disabled:opacity-50"
      />
      <button
        onClick={send}
        disabled={disabled || !text.trim()}
        className="h-[52px] rounded-xl bg-sky-600 px-5 text-sm font-semibold text-white transition hover:bg-sky-500 disabled:cursor-not-allowed disabled:opacity-40"
      >
        Send
      </button>
    </div>
  );
}
