import { useEffect, useState } from "react";

import { apiBase, getRun } from "./api";
import type { PipelineEvent, Run } from "./types";

export function useRun(runId: string | null) {
  const [run, setRun] = useState<Run | null>(null);
  const [events, setEvents] = useState<PipelineEvent[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!runId) return;
    let stopped = false;
    const source = new EventSource(`${apiBase}/api/runs/${runId}/events`);
    const onPipeline = (message: Event) => {
      const event = JSON.parse((message as MessageEvent<string>).data) as PipelineEvent;
      setEvents((current) => [...current, event]);
      if (event.kind === "error") setError(event.message);
      if (event.kind === "completed" || event.kind === "error" || event.kind === "warning") {
        void getRun(runId).then((next) => {
          if (!stopped) setRun(next);
        });
      }
    };
    source.addEventListener("pipeline", onPipeline);
    source.addEventListener("end", () => {
      void getRun(runId).then((next) => {
        if (!stopped) setRun(next);
      });
      source.close();
    });
    source.onerror = () => {
      if (source.readyState === EventSource.CLOSED) source.close();
    };
    return () => {
      stopped = true;
      source.close();
    };
  }, [runId]);

  return { run, setRun, events, error, setError };
}
