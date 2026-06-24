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
      setCaseData(next);
      // keep polling unless the case is paused for input or finished
      if (!isTerminal(next.status) && next.status !== "awaiting_input") {
        timerRef.current = setTimeout(poll, POLL_MS);
      }
    } catch (e) {
      if (aliveRef.current) setError(e.message);
    }
  }, []);

  const start = useCallback(
    async (message, provider) => {
      stopPolling();
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
        // status flips back to "open"; resume polling
        setCaseData((c) => (c ? { ...c, status: "open", pending: null } : c));
        poll();
      } catch (e) {
        setError(e.message);
      } finally {
        setBusy(false);
      }
    },
    [poll],
  );

  const reset = useCallback(() => {
    stopPolling();
    idRef.current = null;
    setCaseData(null);
    setError(null);
  }, [stopPolling]);

  return { caseData, error, busy, start, reply, reset };
}
