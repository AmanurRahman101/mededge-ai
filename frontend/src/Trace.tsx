import type { PipelineEvent, Run } from "./types";

const STAGE: Record<string, string> = {
  system: "Session",
  segment: "SAM 3.1",
  redact: "Redaction",
  extract: "Muse Spark",
  transcribe: "Muse Voice",
  structure: "Muse Spark",
  agent: "Agent",
  verify: "Verifier",
};

function label(event: PipelineEvent) {
  return event.stage === "agent" && event.kind.startsWith("tool") ? "Tool" : STAGE[event.stage] ?? event.stage;
}

export function TracePanel({ run, live }: { run: Run; live: PipelineEvent[] }) {
  const events = run.trace && run.trace.length > 0 ? run.trace : live;
  if (events.length === 0) return null;
  const faulted = run.inject_fault && events.some((e) => e.kind === "tool_result" && e.message.includes("rejected"));
  return (
    <details className="trace-panel" open>
      <summary>How this record was made</summary>
      {run.used_fallback && <p className="banner review">The agent could not finish, so this bundle was assembled by the built-in fallback and passed the same checks.</p>}
      {faulted && <p className="banner review">A fault was injected on purpose. The verifier rejected the bundle and the agent repaired it.</p>}
      <ol className="trace-list" aria-label="Pipeline steps">
        {events.map((event) => (
          <li key={event.seq} data-kind={event.kind}>
            <span className="trace-stage">{label(event)}</span>
            <span className="trace-message">{event.message}</span>
            {(event.model || event.latency_ms) && (
              <small>{[event.model, event.latency_ms ? `${event.latency_ms} ms` : ""].filter(Boolean).join(" · ")}</small>
            )}
          </li>
        ))}
      </ol>
    </details>
  );
}

type Resource = { resourceType?: string; code?: { coding?: { system?: string }[] }; valueQuantity?: { system?: string }; medicationCodeableConcept?: { coding?: { system?: string }[] } };

export function FhirView({ bundle }: { bundle: Run["bundle"] }) {
  if (!bundle) return null;
  const entries = ((bundle as { entry?: { resource?: Resource }[] }).entry ?? []).map((item) => item.resource ?? {});
  const loinc = entries.filter((r) => r.code?.coding?.some((c) => c.system === "http://loinc.org")).length;
  const ucum = entries.filter((r) => r.valueQuantity?.system === "http://unitsofmeasure.org").length;
  const rx = entries.filter((r) => r.medicationCodeableConcept?.coding?.some((c) => c.system?.includes("rxnorm"))).length;
  return (
    <details className="fhir-view">
      <summary>FHIR bundle</summary>
      <p className="badges">
        <span className="badge ok">{entries.length} resources</span>
        <span className="badge ok">{loinc} LOINC</span>
        <span className="badge ok">{ucum} UCUM</span>
        <span className="badge ok">{rx} RxNorm</span>
      </p>
      <pre className="json" tabIndex={0}>{JSON.stringify(bundle, null, 2)}</pre>
    </details>
  );
}
