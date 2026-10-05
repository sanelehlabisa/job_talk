import { useEffect, useRef } from "react";

// One request after typing pauses. Failed values wait for an edit or explicit retry.
export function useAutoSave(value, enabled, busy, onSave) {
  const signature = value ? JSON.stringify(value) : "";
  const previous = useRef("");
  const attempted = useRef(null);
  const timer = useRef(null);
  const save = useRef(onSave);
  save.current = onSave;
  function flush() {
    clearTimeout(timer.current);
    if (!enabled || busy) return;
    attempted.current = signature;
    return save.current(value);
  }
  useEffect(() => {
    if (previous.current !== signature) attempted.current = null;
    previous.current = signature;
    if (enabled && !busy && attempted.current !== signature) {
      timer.current = setTimeout(flush, 1000);
    }
    return () => clearTimeout(timer.current);
  }, [signature, enabled, busy]);
  return flush;
}
