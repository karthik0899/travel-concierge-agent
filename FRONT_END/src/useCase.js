import { useCallback, useEffect, useRef, useState } from "react";
import { getCase, isTerminal, replyToCase, startCase } from "./api.js";

const POLL_MS = 1500;

// Drives one case through the loop:
//   start -> poll every 1.5s -> (awaiting_input -> reply) -> terminal
// Returns the live case object plus the controls the UI needs.
export function useCase() {
  const [caseData, setCaseData] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false); // a request is in flight
  const idRef = useRef(null);
  const timerRef = useRef(null);
  const aliveRef = useRef(true);
  const caseRef = useRef(null); // latest caseData, readable inside callbacks
  // When we reply, the backend resumes in a background task, so for a moment
  // GET still reports the OLD awaiting_input. This holds the updated_at at
  // reply time; while set, we treat an unchanged awaiting_input as stale and
  // keep polling instead of halting the loop.
  const resumeMarkerRef = useRef(null);

  useEffect(() => {
    caseRef.current = caseData;
  }, [caseData]);

  useEffect(() => {
    aliveRef.current = true;
    return () => {
      aliveRef.current = false;
      clearTimeout(timerRef.current);
    };
  }, []);

  const stopPolling = useCallback(() => clearTimeout(timerRef.current), []);

  const poll = useCallback(async () => {
    if (!idRef.current || !aliveRef.current) return;
    try {
      const next = await getCase(idRef.current);
      if (!aliveRef.current) return;

      // Stale pause: we just replied but the background resume hasn't advanced
      // the case yet (same updated_at, still awaiting_input). Don't render it,
      // don't stop — keep polling until it moves.
      const stalePause =
        resumeMarkerRef.current !== null &&
        next.status === "awaiting_input" &&
        next.updated_at === resumeMarkerRef.current;

      if (!stalePause) {
        setCaseData(next);
        resumeMarkerRef.current = null; // case advanced; resume handoff is done
      }

      const settled =
        !stalePause &&
        (isTerminal(next.status) || next.status === "awaiting_input");
      if (!settled) {
        timerRef.current = setTimeout(poll, POLL_MS);
      }
    } catch (e) {
      if (aliveRef.current) setError(e.message);
    }
  }, []);

  const start = useCallback(
    async (message, provider) => {
      stopPolling();
      resumeMarkerRef.current = null;
      setError(null);
      setBusy(true);
      try {
        const started = await startCase(message, provider);
        idRef.current = started.case_id;
        setCaseData({ ...started, audit_log: [], slices: {} });
        poll();
      } catch (e) {
        setError(e.message);
      } finally {
        setBusy(false);
      }
    },
    [poll, stopPolling],
  );

  const reply = useCallback(
    async (message) => {
      if (!idRef.current) return;
      setBusy(true);
      try {
        await replyToCase(idRef.current, message);
        // Remember where we were so poll() can tell "still resuming" from a
        // genuinely new question. Optimistically show progress meanwhile.
        resumeMarkerRef.current = caseRef.current?.updated_at ?? "__resuming__";
        setCaseData((c) => (c ? { ...c, status: "open", pending: null } : c));
        stopPolling();
        poll();
      } catch (e) {
        setError(e.message);
      } finally {
        setBusy(false);
      }
    },
    [poll, stopPolling],
  );

  const reset = useCallback(() => {
    stopPolling();
    resumeMarkerRef.current = null;
    idRef.current = null;
    setCaseData(null);
    setError(null);
  }, [stopPolling]);

  return { caseData, error, busy, start, reply, reset };
}
