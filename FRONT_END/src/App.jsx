import { useEffect, useState } from "react";
import { getDemos, getProviders, isTerminal } from "./api.js";
import { useCase } from "./useCase.js";
import { StatusBadge } from "./components/Badge.jsx";
import { Composer } from "./components/Composer.jsx";
import { ProviderToggle } from "./components/ProviderToggle.jsx";
import { DemoPicker } from "./components/DemoPicker.jsx";
import { PendingPrompt } from "./components/PendingPrompt.jsx";
import { Timeline } from "./components/Timeline.jsx";
import { AuditLog } from "./components/AuditLog.jsx";
import { Results } from "./components/Results.jsx";
import { SidePanels } from "./components/SidePanels.jsx";

export default function App() {
  const { caseData, error, busy, start, reply, reset } = useCase();
  const [provider, setProvider] = useState("");
  const [providerInfo, setProviderInfo] = useState(null);
  const [demos, setDemos] = useState([]);

  useEffect(() => {
    getProviders()
      .then((p) => {
        setProviderInfo(p);
        setProvider(p.default);
      })
      .catch(() => {});
    getDemos()
      .then((d) => setDemos(d.messages ?? []))
      .catch(() => {});
  }, []);

  const hasCase = !!caseData;
  const awaiting = caseData?.status === "awaiting_input";
  const running = caseData?.status === "open";
  const done = caseData && isTerminal(caseData.status);

  return (
    <div className="mx-auto flex h-full max-w-[1400px] flex-col px-4 py-3">
      {/* Header */}
      <header className="mb-3 flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <span className="text-xl">🧳</span>
          <div>
            <h1 className="text-sm font-semibold text-slate-100">
              Travel Concierge Agent
            </h1>
            <p className="text-[11px] text-slate-500">
              Multi-agent flight disruption recovery
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {caseData && <StatusBadge status={caseData.status} />}
          <ProviderToggle
            value={provider}
            options={providerInfo?.available ?? ["cortex", "claude"]}
            defaultProvider={providerInfo?.default}
            onChange={setProvider}
            disabled={running}
          />
        </div>
      </header>

      {error && (
        <div className="mb-3 rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-300">
          {error}
        </div>
      )}

      {/* 3-column workspace */}
      <div className="grid min-h-0 flex-1 grid-cols-1 gap-3 lg:grid-cols-[1.1fr_1fr_300px]">
        {/* Left — conversation */}
        <section className="flex min-h-0 flex-col rounded-2xl border border-ink-800 bg-ink-900/40 p-4">
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-400">
            Conversation
          </h2>

          <div className="min-h-0 flex-1 space-y-3 overflow-y-auto pr-1">
            {!hasCase && (
              <DemoPicker
                demos={demos}
                onPick={(msg) => start(msg, provider)}
                disabled={busy}
              />
            )}

            {hasCase && (
              <>
                {/* the customer's opening message */}
                <div className="ml-6 rounded-2xl rounded-tr-sm border border-sky-500/20 bg-sky-500/10 px-3 py-2 text-sm text-slate-100">
                  {caseData.report?.raw_text ?? caseData.message}
                </div>
                <div className="flex flex-wrap gap-2 text-[11px] text-slate-500">
                  <span className="rounded bg-ink-800 px-1.5 py-0.5">
                    {caseData.booking_ref ?? caseData.report?.booking_ref ?? "—"}
                  </span>
                  <span className="rounded bg-ink-800 px-1.5 py-0.5">
                    {caseData.disruption_type ??
                      caseData.report?.disruption_type ??
                      "—"}
                  </span>
                  <span className="rounded bg-ink-800 px-1.5 py-0.5 font-mono">
                    {caseData.case_id?.slice(0, 8)}
                  </span>
                </div>

                {running && (
                  <p className="text-xs text-sky-300/80">
                    <span className="mr-1 animate-pulse">●</span>
                    Working{caseData.current_step ? ` · ${caseData.current_step}` : ""}…
                  </p>
                )}

                {awaiting && (
                  <PendingPrompt
                    pending={caseData.pending}
                    onReply={reply}
                    disabled={busy}
                  />
                )}

                {done && (
                  <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 px-3 py-2 text-sm text-emerald-200">
                    {caseData.slices?.summary?.narrative ??
                      `Case ${caseData.status}.`}
                  </div>
                )}
              </>
            )}
          </div>

          {/* Composer / new-case */}
          <div className="mt-3 border-t border-ink-800 pt-3">
            {hasCase && !awaiting ? (
              <button
                onClick={reset}
                className="w-full rounded-xl border border-ink-700 bg-ink-850 py-2.5 text-sm font-medium text-slate-300 transition hover:border-sky-500/40 hover:text-sky-300"
              >
                + New case
              </button>
            ) : !hasCase ? (
              <Composer onSend={(msg) => start(msg, provider)} disabled={busy} />
            ) : null}
          </div>
        </section>

        {/* Middle — pipeline + results */}
        <section className="flex min-h-0 flex-col gap-3">
          <div className="rounded-2xl border border-ink-800 bg-ink-900/40 p-4">
            <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-400">
              Pipeline
            </h2>
            {hasCase ? (
              <Timeline caseData={caseData} />
            ) : (
              <p className="py-2 text-center text-xs text-slate-600">
                Start a case to watch the agents run.
              </p>
            )}
          </div>

          <div className="grid min-h-0 flex-1 grid-rows-2 gap-3">
            <div className="min-h-0 overflow-y-auto rounded-2xl border border-ink-800 bg-ink-900/40 p-4">
              <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-400">
                Results
              </h2>
              <Results caseData={caseData} />
            </div>
            <div className="min-h-0 overflow-y-auto rounded-2xl border border-ink-800 bg-ink-900/40 p-4">
              <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-400">
                Activity
              </h2>
              <AuditLog entries={caseData?.audit_log} />
            </div>
          </div>
        </section>

        {/* Right — reference data */}
        <aside className="hidden min-h-0 rounded-2xl border border-ink-800 bg-ink-900/40 lg:flex lg:flex-col">
          <div className="px-3 pt-3">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-400">
              Reference
            </h2>
          </div>
          <div className="mt-2 min-h-0 flex-1">
            <SidePanels
              onUseBooking={(b) => {
                if (!hasCase || done)
                  start(
                    `My flight on booking ${b.booking_ref} was disrupted — please help.`,
                    provider,
                  );
              }}
            />
          </div>
        </aside>
      </div>
    </div>
  );
}
