import { PIPELINE } from "../steps.js";
import { isTerminal } from "../api.js";

// Horizontal pipeline tracker. A step is "done" once its slice exists, "active"
// when it's the current_step, "skipped" if we've moved past it without a slice.
export function Timeline({ caseData }) {
  if (!caseData) return null;
  const slices = caseData.slices ?? {};
  const current = caseData.current_step;
  const finished = isTerminal(caseData.status) || current == null;
  const currentIdx = PIPELINE.findIndex((s) => s.skill === current);

  const stateOf = (step, idx) => {
    if (slices[step.slice]) return "done";
    if (step.skill === current) return "active";
    if (currentIdx > -1 && idx < currentIdx) return "skipped";
    if (finished) return "skipped";
    return "pending";
  };

  const dot = {
    done: "bg-emerald-500 border-emerald-400 text-ink-950",
    active: "bg-sky-500 border-sky-400 text-white animate-pulse",
    skipped: "bg-ink-800 border-ink-700 text-slate-600",
    pending: "bg-ink-850 border-ink-700 text-slate-500",
  };

  return (
    <div className="flex items-center gap-1 overflow-x-auto pb-1">
      {PIPELINE.map((step, idx) => {
        const st = stateOf(step, idx);
        return (
          <div key={step.skill} className="flex items-center">
            <div className="flex flex-col items-center gap-1">
              <div
                className={`flex h-8 w-8 items-center justify-center rounded-full border text-sm ${dot[st]}`}
                title={st}
              >
                {st === "done" ? "✓" : step.icon}
              </div>
              <span
                className={`whitespace-nowrap text-[10px] ${
                  st === "active" ? "text-sky-300" : "text-slate-500"
                }`}
              >
                {step.label}
              </span>
            </div>
            {idx < PIPELINE.length - 1 && (
              <div
                className={`mx-1 mb-4 h-px w-6 ${
                  stateOf(PIPELINE[idx + 1], idx + 1) !== "pending"
                    ? "bg-emerald-500/40"
                    : "bg-ink-700"
                }`}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
