import { useEffect, useState } from "react";
import { apiBase, getRun } from "./api";
import type { PipelineEvent, Run } from "./types";

const complete = new Set(["reviewing", "approved", "exported", "failed", "interrupted"]);

export function useRun(runId: string | null) {
  const [run, setRun] = useState<Run | null>(null);
  const [events, setEvents] = useState<PipelineEvent[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setRun(null); setEvents([]); setError(null);
    if (!runId) return;
    let stopped = false;
    let source: EventSource | null = null;
    async function refresh() {
      const next = await getRun(runId!);
      if (!stopped) setRun(next);
      return next;
    }
    void refresh().then((initial) => {
      if (stopped || complete.has(initial.status)) return;
      let attempts = 0;
      const connect = () => {
        source = new EventSource(`${apiBase}/api/runs/${runId}/events`);
        source.addEventListener("pipeline", (message) => {
          attempts = 0;
          const event = JSON.parse((message as MessageEvent<string>).data) as PipelineEvent;
          setEvents((current) => (current.some((item) => item.seq === event.seq) ? current : [...current, event]));
          if (event.kind === "error") setError(event.message);
          if (["completed", "error", "warning"].includes(event.kind)) {
            void refresh().catch(() => { if (!stopped) setError("Unable to refresh the record."); });
          }
        });
        source.addEventListener("end", () => {
          source?.close();
          void refresh().catch(() => { if (!stopped) setError("Unable to refresh the record."); });
        });
        source.onerror = () => {
          source?.close();
          void refresh().then((latest) => {
            if (stopped || complete.has(latest.status) || latest.status === "awaiting_confirmation") return;
            if (attempts < 4) { attempts += 1; setTimeout(() => { if (!stopped) connect(); }, 1000 * attempts); }
            else setError("Connection interrupted. Refresh this page to check progress.");
          }).catch(() => { if (!stopped) setError("Connection interrupted. Refresh this page to try again."); });
        };
      };
      connect();
    }).catch((caught) => {
      if (!stopped) setError(caught instanceof Error ? caught.message : "Unable to open record.");
    });
    return () => { stopped = true; source?.close(); };
  }, [runId]);

  return { run, setRun, events, error, setError };
}
