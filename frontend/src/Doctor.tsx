import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";

import { apiBase, approveRun, confirmRun, createRun, getChart, post } from "./api";
import { concatPcm, downsample, wavFromPcm16 } from "./audio";
import { navigate } from "./navigation";
import { useRun } from "./useRun";
import "./Doctor.css";

type Connection = { patient_id: string | null; request_id: string; status: string; name: string | null; email: string | null };
type RecordItem = { run_id: string; title: string; status: string; document_type: string | null; created_at: string; source_available: boolean; archived: boolean; medications: string[]; tests: string[]; lab_rows: { name: string; value: number | null; value_text: string | null; unit: string | null }[]; notes: { id: string; summary_en: string; summary_bn: string; author_name: string; published_at: string | null; amends_id: string | null }[] };
type Summary = { id: string; author_id: string; author_name?: string; transcript: string; summary_en: string; summary_bn: string; unresolved: string | string[]; status: string; published_at: string | null; amends_id?: string | null };

function textError(error: unknown) { return error instanceof Error ? error.message : "Something went wrong. Please try again."; }
function issues(value: string | string[]): string[] {
  if (Array.isArray(value)) return value;
  try { const parsed: unknown = JSON.parse(value); return Array.isArray(parsed) ? parsed.filter((v): v is string => typeof v === "string") : []; }
  catch { return value ? [value] : []; }
}

function useRecorder() {
  const [recording, setRecording] = useState(false);
  const [starting, setStarting] = useState(false);
  const [audio, setAudio] = useState<Blob | null>(null);
  const [error, setError] = useState("");
  const gear = useRef<{ stream: MediaStream; context: AudioContext; node: AudioWorkletNode; source: MediaStreamAudioSourceNode; sink: GainNode; timer: number } | null>(null);
  const alive = useRef(true);
  const chunks = useRef<Int16Array[]>([]);
  const samples = useRef(0);
  const startingRef = useRef(false);
  const stopRef = useRef<() => void>(() => {});
  const dispose = useCallback(() => {
    const current = gear.current;
    if (!current) return;
    gear.current = null;
    window.clearTimeout(current.timer);
    current.node.port.onmessage = null;
    current.source.disconnect(); current.node.disconnect(); current.sink.disconnect();
    current.stream.getTracks().forEach((track) => track.stop());
    void current.context.close();
  }, []);
  const stop = useCallback(() => {
    if (!gear.current) return;
    dispose(); setRecording(false);
    if (samples.current > 0) setAudio(wavFromPcm16(concatPcm(chunks.current)));
    else { setAudio(null); setError("No audio was captured. Check your microphone and try again."); }
    chunks.current = []; samples.current = 0;
  }, [dispose]);
  stopRef.current = stop;
  useEffect(() => { alive.current = true; return () => { alive.current = false; dispose(); }; }, [dispose]);
  async function start() {
    if (gear.current || startingRef.current) return;
    startingRef.current = true; setStarting(true);
    setError(""); setAudio(null); chunks.current = []; samples.current = 0;
    let stream: MediaStream | undefined;
    let context: AudioContext | undefined;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (!alive.current) { stream.getTracks().forEach((track) => track.stop()); return; }
      context = new AudioContext();
      await context.audioWorklet.addModule("/pcm16-worklet.js");
      if (!alive.current) { stream.getTracks().forEach((track) => track.stop()); void context.close(); return; }
      const source = context.createMediaStreamSource(stream);
      const node = new AudioWorkletNode(context, "pcm16");
      const sink = context.createGain(); sink.gain.value = 0;
      source.connect(node); node.connect(sink); sink.connect(context.destination);
      const rate = context.sampleRate;
      node.port.onmessage = (message: MessageEvent<Float32Array>) => {
        const part = downsample(message.data, rate);
        const remaining = 180 * 24000 - samples.current;
        if (remaining <= 0) { stopRef.current(); return; }
        const bounded = part.subarray(0, remaining);
        chunks.current.push(bounded); samples.current += bounded.length;
        if (samples.current >= 180 * 24000) stopRef.current();
      };
      const timer = window.setTimeout(() => stopRef.current(), 180_000);
      gear.current = { stream, context, node, source, sink, timer }; setRecording(true);
    } catch (caught) {
      stream?.getTracks().forEach((track) => track.stop());
      if (context) void context.close();
      if (alive.current) setError(caught instanceof Error ? `Microphone unavailable: ${caught.message}` : "Microphone unavailable.");
    } finally {
      startingRef.current = false;
      if (alive.current) setStarting(false);
    }
  }
  return { audio, recording, starting, error, start, stop, discard: () => { setAudio(null); setError(""); } };
}

export function Doctor({ initialRunId = null }: { initialRunId?: string | null }) {
  const [connections, setConnections] = useState<Connection[]>([]);
  const [patientId, setPatientId] = useState("");
  const [records, setRecords] = useState<RecordItem[]>([]);
  const [more, setMore] = useState(false);
  const [offset, setOffset] = useState(0);
  const [code, setCode] = useState("");
  const [image, setImage] = useState<File | null>(null);
  const [sourceRunId, setSourceRunId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [summaries, setSummaries] = useState<Summary[]>([]);
  const [draft, setDraft] = useState<Summary | null>(null);
  const [acknowledged, setAcknowledged] = useState(false);
  const [imageMissing, setImageMissing] = useState(false);
  const [imageLoaded, setImageLoaded] = useState(false);
  const [imageAttempt, setImageAttempt] = useState(0);
  const key = useRef(crypto.randomUUID());
  const recordsRequest = useRef(0);
  const recorder = useRecorder();
  const { run, events, error: runError, setRun } = useRun(initialRunId);
  const selectedPatient = connections.find((c) => c.patient_id === patientId && c.status === "approved");

  useEffect(() => { setImageMissing(false); setImageLoaded(false); setImageAttempt(0); }, [initialRunId]);

  const loadConnections = useCallback(async () => {
    const data = await getChart<{ connections: Connection[] }>("/connections"); setConnections(data.connections);
  }, []);
  const loadRecords = useCallback(async (id: string, page: number) => {
    const requestId = ++recordsRequest.current;
    const data = await getChart<{ records: RecordItem[]; has_more: boolean }>(`/patients/${encodeURIComponent(id)}/overview?offset=${page}&limit=20`);
    if (requestId === recordsRequest.current) { setRecords(data.records); setMore(data.has_more); }
  }, []);
  const loadSummaries = useCallback(async (id: string) => {
    const data = await getChart<{ summaries: Summary[] }>(`/records/${encodeURIComponent(id)}/summaries`);
    setSummaries(data.summaries); setDraft(data.summaries.find((entry) => entry.status === "draft") || null); setAcknowledged(false);
  }, []);
  useEffect(() => { void loadConnections().catch((caught) => setError(textError(caught))); }, [loadConnections]);
  useEffect(() => {
    if (patientId) void loadRecords(patientId, offset).catch((caught) => setError(textError(caught)));
    else { recordsRequest.current++; setRecords([]); setMore(false); }
  }, [patientId, offset, loadRecords]);
  useEffect(() => {
    if (run && ["reviewing", "approved", "exported"].includes(run.status)) {
      void loadSummaries(run.run_id).catch((caught) => setError(textError(caught)));
    }
  }, [run?.run_id, run?.status, loadSummaries]);

  async function requestAccess(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(""); setNotice("");
    try { await post("/api/chart/requests", { code: code.trim().toUpperCase() }); setCode(""); setNotice("Request sent. The patient must approve access before you can open their chart."); await loadConnections(); }
    catch (caught) { setError(textError(caught)); } finally { setBusy(false); }
  }
  async function disconnect(id: string) {
    if (!window.confirm("Disconnect from this patient? You will lose access to their chart.")) return;
    setBusy(true); setError("");
    try { await post(`/api/chart/connections/${encodeURIComponent(id)}/revoke`); setPatientId(""); await loadConnections(); setNotice("Patient disconnected."); }
    catch (caught) { setError(textError(caught)); } finally { setBusy(false); }
  }
  function togglePatient(id: string) {
    if ((image || sourceRunId || recorder.audio) && !window.confirm("Discard the report and recording you have not submitted?")) return;
    recordsRequest.current++; setRecords([]); setMore(false);
    setImage(null); setSourceRunId(""); recorder.discard(); key.current = crypto.randomUUID();
    setPatientId(patientId === id ? "" : id); setOffset(0); setError("");
  }
  async function cancelRequest(id: string) {
    setBusy(true); setError("");
    try { await post(`/api/chart/requests/${encodeURIComponent(id)}/cancel`); await loadConnections(); setNotice("Request cancelled."); }
    catch (caught) { setError(textError(caught)); } finally { setBusy(false); }
  }
  async function submit(event: FormEvent) {
    event.preventDefault(); setError(""); setNotice("");
    if (!selectedPatient || (!image && !sourceRunId) || !recorder.audio) { setError("Choose a connected patient, add a report image, and record your explanation."); return; }
    const form = new FormData();
    form.append("patient_id", patientId); if (image) form.append("image", image); else form.append("source_run_id", sourceRunId); form.append("audio", recorder.audio, "explanation.wav"); form.append("idempotency_key", key.current);
    setBusy(true);
    try { const created = await createRun(form); key.current = crypto.randomUUID(); navigate(`/doctor/records/${created.run_id}`); }
    catch (caught) { setError(textError(caught)); } finally { setBusy(false); }
  }
  async function confirm() {
    if (!run) return;
    setBusy(true); setError("");
    try { await confirmRun(run.run_id); setNotice("Redaction confirmed. Preparing the draft…"); }
    catch (caught) { setError(textError(caught)); } finally { setBusy(false); }
  }
  async function save(publish: boolean) {
    if (!run || !draft) return;
    if (publish && !acknowledged) { setError("Confirm you have reviewed the transcript and both summaries."); return; }
    setBusy(true); setError(""); setNotice("");
    try {
      await post(`/api/chart/records/${encodeURIComponent(run.run_id)}/summaries/${encodeURIComponent(draft.id)}?publish=${publish}`, { transcript: draft.transcript, summary_en: draft.summary_en, summary_bn: draft.summary_bn, acknowledge_unresolved: acknowledged, reviewed_both_languages: acknowledged });
      await loadSummaries(run.run_id); setNotice(publish ? "Summary published to the patient’s chart." : "Draft saved.");
    } catch (caught) { setError(textError(caught)); } finally { setBusy(false); }
  }
  async function approve() {
    if (!run) return;
    setBusy(true); setError("");
    try { const bundle = await approveRun(run.run_id, run); setRun({ ...run, status: "approved", bundle }); setNotice("FHIR bundle approved. You can download it below."); }
    catch (caught) { setError(textError(caught)); } finally { setBusy(false); }
  }
  async function amend(summaryId: string) {
    if (!run) return;
    setBusy(true); setError(""); setNotice("");
    try {
      await post(`/api/chart/records/${encodeURIComponent(run.run_id)}/summaries/${encodeURIComponent(summaryId)}/amend`);
      await loadSummaries(run.run_id);
      setNotice("Amendment draft created. Review both languages before publishing.");
    } catch (caught) { setError(textError(caught)); } finally { setBusy(false); }
  }
  function editLabValue(index: number, value: string) {
    if (!run?.extraction) return;
    const next = structuredClone(run);
    const row = next.extraction?.rows[index];
    if (!row) return;
    const parsed = value === "" ? null : Number(value);
    if (parsed !== null && !Number.isFinite(parsed)) return;
    row.value = parsed;
    setRun(next);
  }
  function download() {
    if (!run?.bundle || run.status !== "approved") return;
    const link = document.createElement("a"); link.href = `${apiBase}/api/chart/records/${encodeURIComponent(run.run_id)}/download`; link.click();
  }

  if (!run && initialRunId) return <main className="stage"><button className="secondary" type="button" onClick={() => navigate("/doctor")}>Back to patients</button><h1>Opening record</h1>{(error || runError) && <p className="banner pii" role="alert">{error || runError}</p>}</main>;

  if (!run) return <main className="stage doctor-chart">
    <p className="chart-eyebrow">DOCTOR WORKSPACE</p><h1>Care, connected.</h1><p className="lede">Access a patient’s chart after they approve your request. Your doctor account is self-declared.</p>
    {(error || recorder.error) && <p className="banner pii" role="alert">{error || recorder.error}</p>}{notice && <p className="banner review" role="status">{notice}</p>}
    <section className="doctor-section"><h2>Connect with a patient</h2><p className="lede">Enter their six-character code. They’ll review and approve your request.</p><form className="doctor-connect" onSubmit={(event) => void requestAccess(event)}><label htmlFor="patient-code">Patient code</label><div className="row-actions"><input id="patient-code" value={code} onChange={(e) => setCode(e.target.value.toUpperCase())} autoComplete="off" maxLength={6} placeholder="ABC234" /><button className="primary" disabled={busy || code.trim().length !== 6}>Request access</button></div></form></section>
    <section className="doctor-section"><div className="doctor-section-head"><div><h2>My patients</h2><p className="lede">Available while patient consent is active.</p></div><button className="secondary" onClick={() => void loadConnections().catch((caught) => setError(textError(caught)))}>Refresh</button></div>
      {connections.filter((c) => c.status === "pending").map((c) => <div className="banner review" key={c.request_id}><p>A connection request is awaiting patient approval.</p><button type="button" className="secondary" disabled={busy} onClick={() => void cancelRequest(c.request_id)}>Cancel request</button></div>)}
      {connections.filter((c) => c.status === "approved").length === 0 && <p className="lede">No connected patients yet. Request access using a patient’s code.</p>}
      <div className="doctor-patient-list">{connections.filter((c) => c.status === "approved" && c.patient_id).map((c) => <button type="button" className="doctor-patient" aria-expanded={patientId === c.patient_id} aria-controls="selected-patient-chart" key={c.patient_id} disabled={recorder.recording || recorder.starting || busy} onClick={() => togglePatient(c.patient_id!)}><span><strong>{c.name}</strong><small>{c.email}</small></span><span>{patientId === c.patient_id ? "Close chart ↑" : "Open chart ↓"}</span></button>)}</div>
    </section>
    {selectedPatient && <div id="selected-patient-chart"><section className="doctor-section"><div className="doctor-section-head"><div><h2>{selectedPatient.name}’s chart</h2><p className="lede">Patient-approved access · This timeline reflects saved records, not a complete medical history.</p></div><div className="row-actions"><button className="secondary" type="button" onClick={() => void loadRecords(patientId, offset).catch((caught) => setError(textError(caught)))}>Refresh chart</button><button className="secondary" type="button" disabled={busy} onClick={() => void disconnect(patientId)}>Disconnect</button></div></div>{records.length === 0 ? <p className="lede">There are no records on this page.</p> : <div className="doctor-timeline"><p className="lede">Saved history, including archived records. Doctor-published notes may contain diagnoses; provisional AI readings can be incomplete or inaccurate. Review the original record before making decisions.</p>{records.map((record) => <article className="doctor-timeline-item" key={record.run_id}><div className="doctor-section-head"><div><h3>{record.title}</h3><p className="lede">{new Date(record.created_at).toLocaleDateString()} · {record.document_type?.replaceAll("_", " ") || "Report"} · {record.status.replaceAll("_", " ")}{record.archived ? " · Archived" : ""}</p></div><button type="button" className="secondary" onClick={() => navigate(`/doctor/records/${record.run_id}`)}>Open record</button></div>{record.notes.length > 0 ? record.notes.map((note) => <div className="doctor-note" key={note.id}><strong>{note.amends_id ? "Published amendment" : "Doctor-published note"}</strong><p className="lede">{note.author_name} · {note.published_at ? new Date(note.published_at).toLocaleString() : "Published"}</p><p className="doctor-summary">{note.summary_en}</p><details><summary>বাংলা সারাংশ</summary><p className="doctor-summary" lang="bn">{note.summary_bn}</p></details></div>) : <p className="lede">No published doctor note for this record.</p>}{(record.medications.length > 0 || record.tests.length > 0 || record.lab_rows.length > 0) && <details><summary>Provisional extracted medications, tests and results</summary>{record.lab_rows.length > 0 && <><h3>Results as extracted</h3><ul>{record.lab_rows.map((row, i) => <li key={i}>{row.name}: {row.value ?? row.value_text ?? "Not recorded"} {row.unit || ""}</li>)}</ul></>}{record.medications.length > 0 && <><h3>Medications as extracted</h3><ul>{record.medications.map((value, i) => <li key={i}>{value}</li>)}</ul></>}{record.tests.length > 0 && <><h3>Advised tests as extracted</h3><ul>{record.tests.map((value, i) => <li key={i}>{value}</li>)}</ul></>}</details>}</article>)}</div>}<div className="row-actions">{offset > 0 && <button type="button" className="secondary" onClick={() => setOffset(Math.max(0, offset - 20))}>Previous</button>}{more && <button type="button" className="secondary" onClick={() => setOffset(offset + 20)}>Next</button>}</div></section>
      <section className="doctor-section" key={patientId}><h2>Add a report and explanation</h2><p className="lede">The image and recording are sent to Meta for processing. Review the redaction and both language summaries before publishing.</p><form className="stack" onSubmit={(event) => void submit(event)}><label className="auth-field">Upload report image<input type="file" accept="image/*" onChange={(event) => { setImage(event.target.files?.[0] || null); setSourceRunId(""); key.current = crypto.randomUUID(); }} /></label>{records.some((r) => r.source_available) && <label className="auth-field">Or use an available report<select value={sourceRunId} disabled={!!image} onChange={(event) => { setSourceRunId(event.target.value); key.current = crypto.randomUUID(); }}><option value="">Choose a report</option>{records.filter((r) => r.source_available).map((r) => <option key={r.run_id} value={r.run_id}>{r.title} · {new Date(r.created_at).toLocaleDateString()}</option>)}</select></label>}<div><p>Voice explanation · up to 3 minutes</p><div className="row-actions">{!recorder.recording ? <button type="button" className="secondary" disabled={busy || recorder.starting} onClick={() => { key.current = crypto.randomUUID(); void recorder.start(); }}>{recorder.starting ? "Opening microphone…" : recorder.audio ? "Record again" : "Start recording"}</button> : <button type="button" className="secondary" onClick={recorder.stop}>Stop recording</button>}{recorder.audio && !recorder.recording && <button type="button" className="secondary" onClick={() => { recorder.discard(); key.current = crypto.randomUUID(); }}>Discard recording</button>}</div><p className="lede" aria-live="polite">{recorder.recording ? "Recording…" : recorder.audio ? "Recording ready." : "No recording yet."}</p></div><button className="primary" type="submit" disabled={busy || recorder.recording || recorder.starting || (!image && !sourceRunId) || !recorder.audio}>{busy ? "Submitting…" : "Continue to redaction"}</button></form></section></div>}
  </main>;

  const ready = ["reviewing", "approved", "exported"].includes(run.status);
  return <main className="doctor-chart doctor-record">
    <button className="back-link" type="button" onClick={() => navigate("/doctor")}>← Back to patients</button>
    <div className="doctor-record-head"><div><p className="chart-eyebrow">RECORD REVIEW</p><h1>Review the reading.</h1><p className="lede">{run.pseudonym} · {run.status.replaceAll("_", " ")}</p></div><button className="secondary" type="button" onClick={() => window.location.reload()}>Refresh status</button></div>
    {(error || runError) && <p className="banner pii" role="alert">{error || runError}</p>}{notice && <p className="banner review" role="status">{notice}</p>}
    {run.status === "processing" && <p className="banner review" role="status">Processing the report and recording. When the draft is ready, review the transcript and both summaries on this page, then select Verify and publish. The published note appears in the patient's record and chart history.</p>}
    {(run.status === "failed" || run.status === "interrupted") && <p className="banner pii" role="alert">Processing did not finish. Go back to the patient chart and submit the report and recording again.</p>}
    <div className="doctor-review-grid"><section><h2>Source report</h2>{run.status === "queued" ? <p className="lede" role="status">Preparing the redaction preview…</p> : imageMissing ? <div className="banner review"><p>Could not load the source preview. It may no longer be available in temporary storage, or the connection may have failed.</p><button type="button" className="secondary" onClick={() => { setImageLoaded(false); setImageMissing(false); setImageAttempt((attempt) => attempt + 1); }}>Retry preview</button></div> : <div className="sheet"><img key={`${run.run_id}-${imageAttempt}`} src={`${apiBase}${run.overlay_url}`} alt="Report with hidden regions marked in red" onLoad={() => setImageLoaded(true)} onError={() => { setImageLoaded(false); setImageMissing(true); }} /></div>}{run.status === "awaiting_confirmation" && <div className="stack"><p className="lede">Check that every private detail is covered in red before the report is read.</p><button className="primary" disabled={busy || !imageLoaded || imageMissing} onClick={() => void confirm()}>Confirm redaction</button></div>}</section>
      <section><h2>Extracted reading</h2><p className="lede">Compare every detail with the source; the AI can miss or misread handwriting.</p>{run.extraction ? <><table><thead><tr><th>As written</th><th>Value</th></tr></thead><tbody>{run.extraction.rows.map((row, i) => <tr key={i}><td>{row.raw_name}</td><td>{row.value !== null || !row.value_text ? <input aria-label={`${row.raw_name} value`} type="number" step="any" value={row.value ?? ""} disabled={run.status === "approved" || run.status === "exported"} onChange={(e) => editLabValue(i, e.target.value)} /> : row.value_text} {row.unit ?? ""}</td></tr>)}{run.extraction.medications.map((item, i) => <tr key={i}><td colSpan={2}>{item.raw_text}</td></tr>)}</tbody></table>{run.extraction.advised_tests.length > 0 && <><h3>Tests as written</h3><ul>{run.extraction.advised_tests.map((test, i) => <li key={i}>{test.raw_name}</li>)}</ul><p className="lede">The approved export includes them as draft requests.</p></>}</> : <p className="lede">{events.at(-1)?.message || "The reading will appear here when it is ready."}</p>}{ready && run.encounter && <div className="row-actions"><button type="button" className="secondary" disabled={busy || run.status === "approved"} onClick={() => void approve()}>Approve FHIR</button>{run.status === "approved" && run.bundle && <button type="button" className="secondary" onClick={download}>Download approved FHIR</button>}</div>}</section></div>
    {draft && <section className="doctor-section"><p className="chart-eyebrow">DOCTOR REVIEW</p><h2>Review both languages</h2><p className="lede">The patient will see this only after you verify and publish it. Check the transcript, names, numbers, doses and clinical statements against the original.</p><label className="auth-field">Voice transcript<textarea value={draft.transcript} onChange={(e) => { setAcknowledged(false); setDraft({ ...draft, transcript: e.target.value }); }} rows={5} /></label>{issues(draft.unresolved).length > 0 && <div className="banner review"><strong>Items to resolve</strong><ul>{issues(draft.unresolved).map((item, i) => <li key={i}>{item}</li>)}</ul></div>}<div className="doctor-review-grid"><label className="auth-field">English summary<textarea value={draft.summary_en} onChange={(e) => { setAcknowledged(false); setDraft({ ...draft, summary_en: e.target.value }); }} rows={9} /></label><label className="auth-field">বাংলা সারাংশ<textarea lang="bn" value={draft.summary_bn} onChange={(e) => { setAcknowledged(false); setDraft({ ...draft, summary_bn: e.target.value }); }} rows={9} /></label></div><label className="check"><input type="checkbox" checked={acknowledged} onChange={(e) => setAcknowledged(e.target.checked)} />I reviewed the transcript, both summaries, and any unresolved details.</label><div className="row-actions"><button type="button" className="secondary" disabled={busy} onClick={() => void save(false)}>Save draft</button><button type="button" className="primary" disabled={busy || !acknowledged || !draft.summary_en.trim() || !draft.summary_bn.trim() || !draft.transcript.trim()} onClick={() => void save(true)}>Verify and publish</button></div></section>}
    {summaries.filter((entry) => entry.status === "published").map((entry) => <section className="doctor-section" key={entry.id}><h2>{entry.amends_id ? "Published amendment" : "Published summary"}</h2><p className="lede">Doctor reviewed · {entry.published_at ? new Date(entry.published_at).toLocaleString() : "Published"}</p><div className="doctor-review-grid"><div><h3>English</h3><p className="doctor-summary">{entry.summary_en}</p></div><div lang="bn"><h3>বাংলা</h3><p className="doctor-summary">{entry.summary_bn}</p></div></div><button type="button" className="secondary" disabled={busy || !!draft} onClick={() => void amend(entry.id)}>Create amendment</button></section>)}
  </main>;
}
