import { Microphone, Stop } from "@phosphor-icons/react";
import { useEffect, useRef, useState, type FormEvent } from "react";

import { apiBase, approveRun, confirmRun, createRun, dictate, exportRun, listCases, openShare } from "./api";
import { concatPcm, downsample, wavFromPcm16 } from "./audio";
import { useApp } from "./store";
import type { Run, SampleCase } from "./types";
import { useRun } from "./useRun";

function loincFor(run: Run, name: string): string | null {
  const entries = (run.bundle?.entry as { resource?: Record<string, unknown> }[] | undefined) ?? [];
  for (const entry of entries) {
    const resource = entry.resource;
    if (!resource || resource.resourceType !== "Observation") continue;
    const code = resource.code as { text?: string; coding?: { code?: string }[] } | undefined;
    if (code?.text?.toLowerCase() !== name.toLowerCase()) continue;
    return code.coding?.[0]?.code ?? null;
  }
  return null;
}

export function Doctor() {
  const setScreen = useApp((state) => state.setScreen);
  const [runId, setRunId] = useState<string | null>(null);
  const [shared, setShared] = useState<Run | null>(null);
  const [code, setCode] = useState("");
  const [cases, setCases] = useState<SampleCase[]>([]);
  const [inject, setInject] = useState(false);
  const [busy, setBusy] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const [tab, setTab] = useState<"values" | "fhir">("values");
  const [traceOpen, setTraceOpen] = useState(false);
  const [caption, setCaption] = useState("");
  const [recording, setRecording] = useState(false);
  const chunks = useRef<Int16Array[]>([]);
  const socket = useRef<WebSocket | null>(null);
  const audioGear = useRef<{ context: AudioContext; stream: MediaStream } | null>(null);
  const { run: live, setRun, events, error } = useRun(runId);
  const run = live ?? shared;

  useEffect(() => {
    void listCases()
      .then(setCases)
      .catch(() => setCases([]));
  }, []);

  async function start(form: FormData) {
    setBusy(true);
    setLocalError(null);
    setShared(null);
    try {
      if (inject) form.append("inject_fault", "true");
      const created = await createRun(form);
      setRunId(created.run_id);
    } catch (caught) {
      setLocalError(caught instanceof Error ? caught.message : "Could not open the report");
    } finally {
      setBusy(false);
    }
  }

  async function onOpenCode(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setLocalError(null);
    setRunId(null);
    try {
      setShared(await openShare(code.trim()));
    } catch (caught) {
      setLocalError(caught instanceof Error ? caught.message : "That code did not open");
    } finally {
      setBusy(false);
    }
  }

  async function onConfirm() {
    if (!run) return;
    setBusy(true); setLocalError(null);
    try { await confirmRun(run.run_id); }
    catch (caught) { setLocalError(caught instanceof Error ? caught.message : "Confirmation failed"); }
    finally { setBusy(false); }
  }

  function editRow(index: number, value: string) {
    if (!run?.extraction) return;
    const next = structuredClone(run);
    const row = next.extraction?.rows[index];
    if (!row || !next.extraction) return;
    row.value = value === "" ? null : Number(value);
    if (live) setRun(next);
    else setShared(next);
  }

  function editNote(note: string) {
    if (!run?.encounter) return;
    const next = structuredClone(run);
    if (!next.encounter) return;
    next.encounter.note = note;
    if (live) setRun(next);
    else setShared(next);
  }

  async function onApprove() {
    if (!run) return;
    setBusy(true);
    setLocalError(null);
    try {
      const bundle = await approveRun(run.run_id, run);
      const approved = { ...run, status: "approved", bundle };
      if (live) setRun(approved);
      else setShared(approved);
      try {
        await exportRun(run.run_id);
        const exported = { ...approved, status: "exported" };
        if (live) setRun(exported);
        else setShared(exported);
      } catch (caught) {
        const message = caught instanceof Error ? caught.message : "Export failed";
        setLocalError(`Approved locally. The FHIR server refused the export: ${message}`);
        const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: "application/fhir+json" });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = `${run.pseudonym}.json`;
        link.click();
        URL.revokeObjectURL(url);
      }
    } catch (caught) {
      setLocalError(caught instanceof Error ? caught.message : "Approval failed");
    } finally {
      setBusy(false);
    }
  }

  async function toggleRecord() {
    if (!run) return;
    if (recording) {
      setRecording(false);
      if (socket.current?.readyState === WebSocket.OPEN) socket.current.send(JSON.stringify({ type: "endStream" }));
      socket.current?.close();
      audioGear.current?.stream.getTracks().forEach((track) => track.stop());
      void audioGear.current?.context.close();
      audioGear.current = null;
      const wav = wavFromPcm16(concatPcm(chunks.current));
      setBusy(true);
      try {
        const updated = await dictate(run.run_id, wav);
        if (live) setRun(updated);
        else setShared(updated);
      } catch (caught) {
        setLocalError(caught instanceof Error ? caught.message : "The visit note was not saved");
      } finally {
        setBusy(false);
      }
      return;
    }
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const context = new AudioContext();
    audioGear.current = { context, stream };
    await context.audioWorklet.addModule("/pcm16-worklet.js");
    const source = context.createMediaStreamSource(stream);
    const node = new AudioWorkletNode(context, "pcm16");
    chunks.current = [];
    node.port.onmessage = (message: MessageEvent<Float32Array>) => {
      const pcm = downsample(message.data, context.sampleRate);
      chunks.current.push(pcm);
      if (socket.current?.readyState === WebSocket.OPEN) socket.current.send(pcm.buffer);
    };
    source.connect(node);
    const protocol = location.protocol === "https:" ? "wss" : "ws";
    const host = apiBase ? new URL(apiBase).host : location.host;
    const ws = new WebSocket(`${protocol}://${host}/api/voice/stream`);
    ws.binaryType = "arraybuffer";
    ws.onmessage = (message) => {
      if (typeof message.data !== "string") return;
      try {
        const body = JSON.parse(message.data) as { transcript?: string; text?: string };
        const text = body.transcript || body.text;
        if (text) setCaption(text);
      } catch {
        setCaption(message.data);
      }
    };
    socket.current = ws;
    setRecording(true);
  }

  const message = localError || error;
  const ready = run && (run.status === "reviewing" || run.status === "approved" || run.status === "exported");

  if (!run) {
    return (
      <main className="stage">
        <button className="secondary" type="button" onClick={() => setScreen("start")}>
          Back
        </button>
        <h1 style={{ marginTop: 24 }}>Open a record</h1>
        <p className="lede">Use the six-character code from the patient, or add a report yourself.</p>
        <form className="stack" onSubmit={(event) => void onOpenCode(event)}>
          <input
            aria-label="Patient code"
            value={code}
            onChange={(event) => setCode(event.target.value.toUpperCase())}
            maxLength={6}
            placeholder="ABC234"
            style={{
              fontFamily: '"Geist Mono", ui-monospace, monospace',
              letterSpacing: "0.14em",
              fontSize: 28,
              background: "transparent",
              border: 0,
              borderBottom: "1px solid var(--line)",
              padding: "8px 0",
            }}
          />
          <button className="primary" type="submit" disabled={busy || code.trim().length < 6}>
            Open code
          </button>
        </form>
        <div className="stack" style={{ marginTop: 28 }}>
          <label className="secondary">
            Upload a report
            <input
              className="file-input"
              type="file"
              accept="image/*"
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (!file) return;
                const form = new FormData();
                form.append("image", file);
                void start(form);
              }}
            />
          </label>
          <label className="check">
            <input type="checkbox" checked={inject} onChange={(event) => setInject(event.target.checked)} />
            Inject a fault. The first check fails on purpose, and the label stays visible.
          </label>
          {cases.map((item) => (
            <button
              key={item.id}
              className="secondary"
              type="button"
              disabled={busy}
              onClick={() => {
                const form = new FormData();
                form.append("case_id", item.id);
                void start(form);
              }}
            >
              {item.title}
            </button>
          ))}
        </div>
        {message && <p className="banner pii">{message}</p>}
      </main>
    );
  }

  return (
    <main className="workbench">
      <section className="pane">
        <h2>Source</h2>
        <div className="sheet">
          <img src={`${apiBase}${run.overlay_url}`} alt="Source page with hidden regions marked" />
        </div>
        {run.status === "awaiting_confirmation" && <div className="stack" style={{ marginTop: 16 }}><p className="lede">Red marks what will stay hidden. Confirm the overlay before the page is read.</p><button className="primary" type="button" disabled={busy} onClick={() => void onConfirm()}>Confirm redaction</button></div>}
        <div className="row-actions">
          <button className="secondary" type="button" onClick={() => setScreen("start")}>
            Close
          </button>
          <button className="secondary drawer-toggle" type="button" onClick={() => setTraceOpen((open) => !open)}>
            Trace
          </button>
          {ready && (
            <button className="secondary" type="button" onClick={() => void toggleRecord()} disabled={busy}>
              {recording ? <Stop size={16} /> : <Microphone size={16} />}
              {recording ? "Stop and save" : "Dictate visit note"}
            </button>
          )}
        </div>
        {(caption || run.transcript) && <p className="lede">{caption || run.transcript}</p>}
      </section>
      <section className={`pane trace-pane${traceOpen ? " open" : ""}`}>
        <h2>Trace</h2>
        {events.length === 0 && <p className="lede">Stages appear here as they finish.</p>}
        <ol className="trace">
          {events.map((event) => (
            <li key={event.seq}>
              <span>{event.message}</span>
              <small>
                {event.stage}
                {event.model ? ` · ${event.model}` : ""}
              </small>
            </li>
          ))}
        </ol>
      </section>
      <section className="pane">
        <h2>Result</h2>
        <div className="tabs">
          <button className="tab" type="button" aria-selected={tab === "values"} onClick={() => setTab("values")}>
            Values
          </button>
          <button className="tab" type="button" aria-selected={tab === "fhir"} onClick={() => setTab("fhir")}>
            FHIR JSON
          </button>
        </div>
        {run.replay && <p className="banner review">Recorded reading. No model produced these values.</p>}
        {run.used_fallback && !run.replay && <p className="banner review">Assembled by fallback.</p>}
        {run.extractor_model && <p className="lede">Read by {run.extractor_model}</p>}
        {run.inject_fault && <p className="banner review">Inject a fault was on for this run.</p>}
        {message && <p className="banner pii">{message}</p>}
        {tab === "values" && run.extraction && (
          <table>
            <thead>
              <tr>
                <th>Printed name</th>
                <th>Value</th>
                <th>Code</th>
              </tr>
            </thead>
            <tbody>
              {run.extraction.rows.map((row, index) => {
                const codeForRow = loincFor(run, row.raw_name);
                return (
                  <tr key={row.raw_name}>
                    <td>{row.raw_name}</td>
                    <td>
                      <input
                        aria-label={`${row.raw_name} value`}
                        value={row.value ?? ""}
                        onChange={(event) => editRow(index, event.target.value)}
                      />
                    </td>
                    <td>{codeForRow ? <span className="badge ok">{codeForRow}</span> : row.unit}</td>
                  </tr>
                );
              })}
              {run.extraction.medications.map((item) => (
                <tr key={item.raw_text}>
                  <td colSpan={2}>{item.raw_text}</td>
                  <td>
                    <span className="badge review">as written</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {tab === "values" && run.extraction && run.extraction.advised_tests.length > 0 && (
          <section aria-label="Advised tests">
            <h3>Tests as written</h3>
            <ul>{run.extraction.advised_tests.map((test, index) => <li key={`${test.raw_name}-${index}`}>{test.raw_name}</li>)}</ul>
            <p className="lede">Review these transcriptions against the original. The approved export includes them as draft requests.</p>
          </section>
        )}
        {tab === "values" && run.encounter && (
          <label className="stack" style={{ marginTop: 16 }}>
            Visit note
            <textarea
              value={run.encounter.note}
              onChange={(event) => editNote(event.target.value)}
              rows={3}
              style={{ background: "transparent", border: "1px solid var(--line)", borderRadius: 12, padding: 10 }}
            />
          </label>
        )}
        {tab === "fhir" && <pre className="json">{JSON.stringify(run.bundle, null, 2)}</pre>}
        {ready && (
          <div className="row-actions">
            <button className="primary" type="button" disabled={busy} onClick={() => void onApprove()}>
              {run.status === "exported" ? "Exported" : "Approve and export"}
            </button>
            {run.status === "exported" && <span className="badge ok">Verified</span>}
          </div>
        )}
        {!ready && <p className="lede">{events.at(-1)?.message ?? run.status}</p>}
      </section>
    </main>
  );
}
