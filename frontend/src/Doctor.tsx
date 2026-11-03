import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
} from "react";

import {
  apiBase,
  confirmRun,
  createRun,
  getChart,
  getSampleDictation,
  post,
} from "./api";
import { concatPcm, downsample, wavFromPcm16 } from "./audio";
import { navigate } from "./navigation";
import { useApp } from "./store";
import { prepareImage } from "./image";
import { ChartOverview, recordStatus } from "./ChartOverview";
import {
  PixelWorkspaceIcon,
  PixelDocument,
  PixelPill,
  PixelVisit,
  PixelShield,
} from "./PixelIcons";
import { useRun } from "./useRun";
import "./Doctor.css";

type Connection = {
  patient_id: string | null;
  request_id: string;
  status: string;
  name: string | null;
  email: string | null;
};
type RecordItem = {
  run_id: string;
  title: string;
  status: string;
  document_type: string | null;
  created_at: string;
  source_available: boolean;
  archived: boolean;
  medications: string[];
  tests: string[];
  lab_rows: {
    name: string;
    value: number | null;
    value_text: string | null;
    unit: string | null;
  }[];
  notes: {
    id: string;
    summary_en: string;
    summary_bn: string;
    author_name: string;
    published_at: string | null;
    amends_id: string | null;
  }[];
};
type Summary = {
  id: string;
  author_id: string;
  author_name?: string;
  transcript: string;
  summary_en: string;
  summary_bn: string;
  unresolved: string | string[];
  status: string;
  published_at: string | null;
  amends_id?: string | null;
};

function textError(error: unknown) {
  return error instanceof Error
    ? error.message
    : "Something went wrong. Please try again.";
}
function issues(value: string | string[]): string[] {
  if (Array.isArray(value)) return value;
  try {
    const parsed: unknown = JSON.parse(value);
    return Array.isArray(parsed)
      ? parsed.filter((v): v is string => typeof v === "string")
      : [];
  } catch {
    return value ? [value] : [];
  }
}

function useRecorder() {
  const [recording, setRecording] = useState(false);
  const [starting, setStarting] = useState(false);
  const [audio, setAudio] = useState<Blob | null>(null);
  const [error, setError] = useState("");
  const gear = useRef<{
    stream: MediaStream;
    context: AudioContext;
    node: AudioWorkletNode;
    source: MediaStreamAudioSourceNode;
    sink: GainNode;
    timer: number;
  } | null>(null);
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
    current.source.disconnect();
    current.node.disconnect();
    current.sink.disconnect();
    current.stream.getTracks().forEach((track) => track.stop());
    void current.context.close();
  }, []);
  const stop = useCallback(() => {
    if (!gear.current) return;
    dispose();
    setRecording(false);
    if (samples.current > 0) setAudio(wavFromPcm16(concatPcm(chunks.current)));
    else {
      setAudio(null);
      setError("No audio was captured. Check your microphone and try again.");
    }
    chunks.current = [];
    samples.current = 0;
  }, [dispose]);
  stopRef.current = stop;
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
      dispose();
    };
  }, [dispose]);
  async function start() {
    if (gear.current || startingRef.current) return;
    startingRef.current = true;
    setStarting(true);
    setError("");
    setAudio(null);
    chunks.current = [];
    samples.current = 0;
    let stream: MediaStream | undefined;
    let context: AudioContext | undefined;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (!alive.current) {
        stream.getTracks().forEach((track) => track.stop());
        return;
      }
      context = new AudioContext();
      await context.audioWorklet.addModule("/pcm16-worklet.js");
      if (!alive.current) {
        stream.getTracks().forEach((track) => track.stop());
        void context.close();
        return;
      }
      const source = context.createMediaStreamSource(stream);
      const node = new AudioWorkletNode(context, "pcm16");
      const sink = context.createGain();
      sink.gain.value = 0;
      source.connect(node);
      node.connect(sink);
      sink.connect(context.destination);
      const rate = context.sampleRate;
      node.port.onmessage = (message: MessageEvent<Float32Array>) => {
        const part = downsample(message.data, rate);
        const remaining = 180 * 24000 - samples.current;
        if (remaining <= 0) {
          stopRef.current();
          return;
        }
        const bounded = part.subarray(0, remaining);
        chunks.current.push(bounded);
        samples.current += bounded.length;
        if (samples.current >= 180 * 24000) stopRef.current();
      };
      const timer = window.setTimeout(() => stopRef.current(), 180_000);
      gear.current = { stream, context, node, source, sink, timer };
      setRecording(true);
    } catch (caught) {
      stream?.getTracks().forEach((track) => track.stop());
      if (context) void context.close();
      if (alive.current)
        setError(
          caught instanceof Error
            ? `Microphone unavailable: ${caught.message}`
            : "Microphone unavailable.",
        );
    } finally {
      startingRef.current = false;
      if (alive.current) setStarting(false);
    }
  }
  return {
    audio,
    recording,
    starting,
    error,
    start,
    stop,
    discard: () => {
      setAudio(null);
      setError("");
    },
    useBlob: (blob: Blob) => {
      setAudio(blob);
      setError("");
    },
  };
}

export function Doctor({
  initialRunId = null,
}: {
  initialRunId?: string | null;
}) {
  const isDemo = useApp((state) => state.user?.id) === "demo-doctor";
  const [chartTab, setChartTab] = useState<"overview" | "history" | "add">(
    "overview",
  );
  const [recordTab, setRecordTab] = useState<"note" | "reading" | "source">(
    "reading",
  );
  const [showConnect, setShowConnect] = useState(false);
  const [patientSearch, setPatientSearch] = useState("");
  const [recordsLoading, setRecordsLoading] = useState(false);
  const [connectionsLoaded, setConnectionsLoaded] = useState(false);
  const [imagePreparing, setImagePreparing] = useState(false);
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
  const { run, events, error: runError } = useRun(initialRunId);
  const selectedPatient = connections.find(
    (c) => c.patient_id === patientId && c.status === "approved",
  );

  useEffect(() => {
    setImageMissing(false);
    setImageLoaded(false);
    setImageAttempt(0);
  }, [initialRunId]);

  const loadConnections = useCallback(async () => {
    const data = await getChart<{ connections: Connection[] }>("/connections");
    setConnections(data.connections);
    setConnectionsLoaded(true);
  }, []);
  const loadRecords = useCallback(async (id: string, page: number) => {
    const requestId = ++recordsRequest.current;
    setRecordsLoading(true);
    const data = await getChart<{ records: RecordItem[]; has_more: boolean }>(
      `/patients/${encodeURIComponent(id)}/overview?offset=${page}&limit=20&include_source=${chartTab === "add"}`,
    );
    if (requestId === recordsRequest.current) {
      setRecords(data.records);
      setMore(data.has_more);
      setRecordsLoading(false);
    }
  }, [chartTab]);
  const loadSummaries = useCallback(async (id: string) => {
    const data = await getChart<{ summaries: Summary[] }>(
      `/records/${encodeURIComponent(id)}/summaries`,
    );
    setSummaries(data.summaries);
    setDraft(data.summaries.find((entry) => entry.status === "draft") || null);
    setAcknowledged(false);
  }, []);
  useEffect(() => {
    void loadConnections().catch((caught) => setError(textError(caught)));
  }, [loadConnections]);
  useEffect(() => {
    if (patientId && chartTab !== "overview")
      void loadRecords(patientId, offset).catch((caught) => {
        setRecordsLoading(false);
        setError(textError(caught));
      });
    else {
      recordsRequest.current++;
      setRecords([]);
      setMore(false);
    }
  }, [patientId, offset, chartTab, loadRecords]);
  useEffect(() => {
    if (run && ["reviewing", "approved", "exported"].includes(run.status)) {
      void loadSummaries(run.run_id).catch((caught) =>
        setError(textError(caught)),
      );
    }
  }, [run?.run_id, run?.status, loadSummaries]);

  useEffect(() => {
    if (run && ["reviewing", "approved", "exported"].includes(run.status)) {
      setRecordTab("note");
      setNotice("");
    }
  }, [run?.run_id, run?.status]);

  async function requestAccess(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await post("/api/chart/requests", { code: code.trim().toUpperCase() });
      setCode("");
      setNotice(
        "Request sent. The patient must approve access before you can open their chart.",
      );
      await loadConnections();
    } catch (caught) {
      setError(textError(caught));
    } finally {
      setBusy(false);
    }
  }
  async function disconnect(id: string) {
    if (
      !window.confirm(
        "Disconnect from this patient? You will lose access to their chart.",
      )
    )
      return;
    setBusy(true);
    setError("");
    try {
      await post(`/api/chart/connections/${encodeURIComponent(id)}/revoke`);
      setPatientId("");
      await loadConnections();
      setNotice("Patient disconnected.");
    } catch (caught) {
      setError(textError(caught));
    } finally {
      setBusy(false);
    }
  }
  function togglePatient(id: string) {
    if (
      (image || sourceRunId || recorder.audio) &&
      !window.confirm(
        "Discard the report and recording you have not submitted?",
      )
    )
      return;
    recordsRequest.current++;
    setRecords([]);
    setMore(false);
    setImage(null);
    setSourceRunId("");
    recorder.discard();
    key.current = crypto.randomUUID();
    setPatientId(id);
    setChartTab("overview");
    setOffset(0);
    setError("");
  }
  async function cancelRequest(id: string) {
    setBusy(true);
    setError("");
    try {
      await post(`/api/chart/requests/${encodeURIComponent(id)}/cancel`);
      await loadConnections();
      setNotice("Request cancelled.");
    } catch (caught) {
      setError(textError(caught));
    } finally {
      setBusy(false);
    }
  }
  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setNotice("");
    if (!selectedPatient || (!image && !sourceRunId) || !recorder.audio) {
      setError(
        "Choose a connected patient, add a report image, and record your explanation.",
      );
      return;
    }
    const form = new FormData();
    form.append("patient_id", patientId);
    if (image) form.append("image", image);
    else form.append("source_run_id", sourceRunId);
    form.append("audio", recorder.audio, "explanation.wav");
    form.append("idempotency_key", key.current);
    setBusy(true);
    try {
      const created = await createRun(form);
      key.current = crypto.randomUUID();
      navigate(`/doctor/records/${created.run_id}`);
    } catch (caught) {
      setError(textError(caught));
    } finally {
      setBusy(false);
    }
  }
  async function confirm() {
    if (!run) return;
    setBusy(true);
    setError("");
    try {
      await confirmRun(run.run_id);
      setNotice("Redaction confirmed. Preparing the draft…");
    } catch (caught) {
      setError(textError(caught));
    } finally {
      setBusy(false);
    }
  }
  async function save(publish: boolean) {
    if (!run || !draft) return;
    if (publish && !acknowledged) {
      setError("Confirm you have reviewed the transcript and both versions.");
      return;
    }
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await post(
        `/api/chart/records/${encodeURIComponent(run.run_id)}/summaries/${encodeURIComponent(draft.id)}?publish=${publish}`,
        {
          transcript: draft.transcript,
          summary_en: draft.summary_en,
          summary_bn: draft.summary_bn,
          acknowledge_unresolved: acknowledged,
          reviewed_both_languages: acknowledged,
        },
      );
      await loadSummaries(run.run_id);
      setNotice(
        publish ? "Note published to the patient’s chart." : "Draft saved.",
      );
    } catch (caught) {
      setError(textError(caught));
    } finally {
      setBusy(false);
    }
  }
  async function amend(summaryId: string) {
    if (!run) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await post(
        `/api/chart/records/${encodeURIComponent(run.run_id)}/summaries/${encodeURIComponent(summaryId)}/amend`,
      );
      await loadSummaries(run.run_id);
      setNotice(
        "Amendment draft created. Review both versions before publishing.",
      );
    } catch (caught) {
      setError(textError(caught));
    } finally {
      setBusy(false);
    }
  }

  if (!run && initialRunId)
    return (
      <main className="workspace">
        <button
          className="back-link"
          type="button"
          onClick={() => navigate("/doctor")}
        >
          ← Back to patients
        </button>
        <h1>Opening record…</h1>
        {(error || runError) && (
          <p className="banner pii" role="alert">
            {error || runError}
          </p>
        )}
      </main>
    );

  if (!run)
    return (
      <main className="workspace doctor-workspace">
        <header className="workspace-heading">
          <div className="workspace-title">
            <PixelWorkspaceIcon workspace="doctor" size={42} />
            <div>
              <h1>Doctor workspace</h1>
              <p>Your patients, records and notes.</p>
            </div>
          </div>
          <button
            type="button"
            className="primary"
            onClick={() => setShowConnect((open) => !open)}
            aria-expanded={showConnect}
          >
            {showConnect ? "Close connection form" : "Connect a patient"}
          </button>
        </header>
        {(error || recorder.error) && (
          <p className="banner pii" role="alert">
            {error || recorder.error}
          </p>
        )}
        {notice && (
          <p className="banner review" role="status">
            {notice}
          </p>
        )}
        {showConnect && (
          <section className="connect-module">
            <div>
              <h2>Request patient access</h2>
              <p>
                Enter the patient's code. Access begins after they approve.
                Doctor accounts are self-declared.
              </p>
            </div>
            <form onSubmit={(event) => void requestAccess(event)}>
              <label htmlFor="patient-code">Patient code</label>
              <div className="row-actions">
                <input
                  id="patient-code"
                  value={code}
                  onChange={(e) => setCode(e.target.value.toUpperCase())}
                  maxLength={6}
                  autoComplete="off"
                  placeholder="ABC234"
                />
                <button
                  className="primary"
                  disabled={busy || code.trim().length !== 6}
                >
                  Request access
                </button>
              </div>
            </form>
          </section>
        )}
        <div className="workspace-grid">
          <aside className="patient-sidebar">
            <div className="module-heading">
              <h2>My patients</h2>
              <button
                type="button"
                className="text-link"
                onClick={() =>
                  void loadConnections().catch((caught) =>
                    setError(textError(caught)),
                  )
                }
              >
                Refresh
              </button>
            </div>
            <label className="search-label">
              Find a patient
              <input
                type="search"
                value={patientSearch}
                onChange={(e) => setPatientSearch(e.target.value)}
                placeholder="Name or email"
              />
            </label>
            {!connectionsLoaded && <p role="status">Loading patients…</p>}
            {connectionsLoaded &&
              !connections.some((c) => c.status === "approved") && (
                <p className="empty-inline">
                  No connected patients. Use a patient's code to request access.
                </p>
              )}
            <div className="patient-directory">
              {connections
                .filter(
                  (c) =>
                    c.status === "approved" &&
                    c.patient_id &&
                    `${c.name} ${c.email}`
                      .toLowerCase()
                      .includes(patientSearch.toLowerCase()),
                )
                .map((c) => (
                  <button
                    type="button"
                    className="patient-choice"
                    key={c.patient_id}
                    aria-current={
                      patientId === c.patient_id ? "true" : undefined
                    }
                    disabled={busy || recorder.recording || recorder.starting}
                    onClick={() => togglePatient(c.patient_id!)}
                  >
                    <PixelWorkspaceIcon workspace="patient" size={28} />
                    <span>
                      <strong>{c.name || "Patient"}</strong>
                      <small>{c.email}</small>
                    </span>
                  </button>
                ))}
            </div>
            {connections.some((c) => c.status === "pending") && (
              <section className="pending-connections">
                <h3>Awaiting approval</h3>
                {connections
                  .filter((c) => c.status === "pending")
                  .map((c) => (
                    <div key={c.request_id}>
                      <p>Patient connection requested</p>
                      <button
                        className="text-link"
                        type="button"
                        disabled={busy}
                        onClick={() => void cancelRequest(c.request_id)}
                      >
                        Cancel request
                      </button>
                    </div>
                  ))}
              </section>
            )}
          </aside>
          <section className="chart-workspace">
            {!selectedPatient ? (
              <div className="workspace-empty">
                <PixelWorkspaceIcon workspace="patient" size={72} />
                <h2>Select a patient</h2>
                <p>
                  Choose a connected patient to view their full summary, browse
                  reports, or add a note.
                </p>
              </div>
            ) : (
              <>
                <div className="selected-patient">
                  <div className="workspace-title">
                    <PixelWorkspaceIcon workspace="patient" size={36} />
                    <div>
                      <h2>{selectedPatient.name}</h2>
                      <p>
                        <PixelShield size={14} /> Patient-approved chart access
                      </p>
                    </div>
                  </div>
                </div>
                <nav className="module-tabs" aria-label="Patient workspace">
                  <button
                    type="button"
                    aria-current={chartTab === "overview" ? "page" : undefined}
                    onClick={() => setChartTab("overview")}
                  >
                    <PixelVisit /> Summary
                  </button>
                  <button
                    type="button"
                    aria-current={chartTab === "history" ? "page" : undefined}
                    onClick={() => setChartTab("history")}
                  >
                    <PixelDocument /> History
                  </button>
                  <button
                    type="button"
                    aria-current={chartTab === "add" ? "page" : undefined}
                    onClick={() => setChartTab("add")}
                  >
                    <PixelPill /> Add report & note
                  </button>
                </nav>
                {chartTab === "overview" && (
                  <ChartOverview
                    key={patientId}
                    patientId={patientId}
                    role="doctor"
                  />
                )}
                {chartTab === "history" && (
                  <section className="history-module">
                    <div className="module-heading">
                      <div>
                        <h2>Reports & notes</h2>
                        <p>
                          Open a report to review the source and published
                          notes.
                        </p>
                      </div>
                      <button
                        className="secondary"
                        disabled={recordsLoading}
                        type="button"
                        onClick={() =>
                          void loadRecords(patientId, offset).catch(
                            (caught) => {
                              setRecordsLoading(false);
                              setError(textError(caught));
                            },
                          )
                        }
                      >
                        Refresh
                      </button>
                    </div>
                    {recordsLoading ? (
                      <p role="status">Loading reports…</p>
                    ) : records.length ? (
                      <div className="history-list">
                        {records.map((record) => (
                          <button
                            className="history-row"
                            type="button"
                            key={record.run_id}
                            onClick={() =>
                              navigate(`/doctor/records/${record.run_id}`)
                            }
                          >
                            <PixelDocument size={25} />
                            <span>
                              <strong>{record.title}</strong>
                              <small>
                                {new Date(
                                  record.created_at,
                                ).toLocaleDateString()}{" "}
                                ·{" "}
                                {record.document_type?.replaceAll("_", " ") ||
                                  "Report"}
                                {record.archived ? " · Archived" : ""}
                              </small>
                            </span>
                            <span className="status-label">
                              {record.notes.length
                                ? "Published note"
                                : recordStatus(record.status)}
                            </span>
                          </button>
                        ))}
                      </div>
                    ) : (
                      <p className="empty-inline">
                        No saved reports on this page.
                      </p>
                    )}
                    <div className="chart-pages row-actions">
                      <button
                        className="secondary"
                        disabled={!offset || recordsLoading}
                        onClick={() => setOffset(Math.max(0, offset - 20))}
                      >
                        Previous
                      </button>
                      <span>Page {Math.floor(offset / 20) + 1}</span>
                      <button
                        className="secondary"
                        disabled={!more || recordsLoading}
                        onClick={() => setOffset(offset + 20)}
                      >
                        Next
                      </button>
                    </div>
                    <details className="access-settings">
                      <summary>Patient access settings</summary>
                      <p>Disconnecting ends your access to this chart.</p>
                      <button
                        className="secondary"
                        disabled={busy}
                        type="button"
                        onClick={() => void disconnect(patientId)}
                      >
                        Disconnect patient
                      </button>
                    </details>
                  </section>
                )}
                {chartTab === "add" && (
                  <section className="submission-module" key={patientId}>
                    <h2>Add a report & dictated note</h2>
                    <p className="module-help">
                      The report and recording stay in the patient's chart until
                      deletion. They are sent to Meta for processing. Review
                      privacy first, then check the reading and both note
                      versions.
                    </p>
                    <form
                      className="stack"
                      onSubmit={(event) => void submit(event)}
                    >
                      <div className="submission-inputs">
                        <section>
                          <h3>
                            <PixelDocument /> Report image
                          </h3>
                          <label className="auth-field">
                            Choose an image
                            <input
                              type="file"
                              accept="image/*"
                              disabled={busy || imagePreparing}
                              onChange={(event) => {
                                const picked = event.target.files?.[0];
                                setSourceRunId("");
                                key.current = crypto.randomUUID();
                                setImage(null);
                                if (!picked) return;
                                setImagePreparing(true);
                                void prepareImage(picked)
                                  .then(setImage)
                                  .catch((caught) =>
                                    setError(textError(caught)),
                                  )
                                  .finally(() => setImagePreparing(false));
                              }}
                            />
                          </label>
                          {imagePreparing && (
                            <p role="status">Preparing the image…</p>
                          )}
                          {records.some((r) => r.source_available) && (
                            <label className="auth-field">
                              Or reuse a saved report
                              <select
                                value={sourceRunId}
                                disabled={!!image || imagePreparing || busy}
                                onChange={(e) => {
                                  setSourceRunId(e.target.value);
                                  key.current = crypto.randomUUID();
                                }}
                              >
                                <option value="">Choose a report</option>
                                {records
                                  .filter((r) => r.source_available)
                                  .map((r) => (
                                    <option key={r.run_id} value={r.run_id}>
                                      {r.title} ·{" "}
                                      {new Date(
                                        r.created_at,
                                      ).toLocaleDateString()}
                                    </option>
                                  ))}
                              </select>
                            </label>
                          )}
                        </section>
                        <section>
                          <h3>
                            <PixelVisit /> Voice explanation
                          </h3>
                          <p>
                            Up to 3 minutes. Speak only the information you
                            intend to add to the chart.
                          </p>
                          <div className="row-actions">
                            {recorder.recording ? (
                              <button
                                type="button"
                                className="primary"
                                onClick={recorder.stop}
                              >
                                Stop recording
                              </button>
                            ) : (
                              <button
                                type="button"
                                className="secondary"
                                disabled={busy || recorder.starting}
                                onClick={() => {
                                  key.current = crypto.randomUUID();
                                  void recorder.start();
                                }}
                              >
                                {recorder.starting
                                  ? "Opening microphone…"
                                  : recorder.audio
                                    ? "Record again"
                                    : "Start recording"}
                              </button>
                            )}
                            {recorder.audio && !recorder.recording && (
                              <button
                                type="button"
                                className="text-link"
                                onClick={recorder.discard}
                              >
                                Discard
                              </button>
                            )}
                          </div>
                          {isDemo && !recorder.recording && (
                            <button
                              className="text-link"
                              type="button"
                              onClick={() =>
                                void getSampleDictation()
                                  .then(recorder.useBlob)
                                  .catch((caught) =>
                                    setError(textError(caught)),
                                  )
                              }
                            >
                              Use fictional sample recording
                            </button>
                          )}
                          <p role="status">
                            {recorder.recording
                              ? "Recording…"
                              : recorder.audio
                                ? "Recording ready"
                                : "No recording yet"}
                          </p>
                        </section>
                      </div>
                      <div className="submission-footer">
                        <p>Next: check the privacy preview.</p>
                        <button
                          className="primary"
                          type="submit"
                          disabled={
                            busy ||
                            imagePreparing ||
                            recorder.recording ||
                            recorder.starting ||
                            (!image && !sourceRunId) ||
                            !recorder.audio
                          }
                        >
                          {busy ? "Uploading…" : "Continue to privacy review"}
                        </button>
                      </div>
                    </form>
                  </section>
                )}
              </>
            )}
          </section>
        </div>
      </main>
    );

  const ready = ["reviewing", "approved", "exported"].includes(run.status);
  return (
    <main className="workspace record-workspace">
      <button
        className="back-link"
        type="button"
        onClick={() => navigate("/doctor")}
      >
        ← Back to patients
      </button>
      <header className="workspace-heading">
        <div className="workspace-title">
          <PixelDocument size={36} />
          <div>
            <h1>
              {draft
                ? "Review & publish note"
                : summaries.length
                  ? "Patient record"
                  : "Review report"}
            </h1>
            <p>
              {run.pseudonym} ·{" "}
              <span className="status-label">
                {summaries.some((s) => s.status === "published")
                  ? "Published note"
                  : recordStatus(run.status)}
              </span>
            </p>
          </div>
        </div>
        {!ready && (
          <button
            className="secondary"
            type="button"
            onClick={() => window.location.reload()}
          >
            Check progress
          </button>
        )}
      </header>
      {(error || runError) && (
        <p className="banner pii" role="alert">
          {error || runError}
        </p>
      )}
      {notice && (
        <p className="banner review" role="status">
          {notice}
        </p>
      )}
      {run.used_fallback && (
        <p className="module-help">
          A fallback prepared this reading. Compare every detail with the
          report.
        </p>
      )}
      {run.status === "processing" && (
        <p className="banner review" role="status">
          {events.at(-1)?.message || "Processing the report and recording…"}{" "}
          Your draft will appear here for review. After you select Verify and
          publish, the note appears in the patient's record and chart history.
        </p>
      )}
      {(run.status === "failed" || run.status === "interrupted") && (
        <p className="banner pii" role="alert">
          Processing did not finish. Return to the patient chart to submit
          another report.
        </p>
      )}
      {ready && (
        <nav className="module-tabs" aria-label="Record sections">
          <button
            type="button"
            aria-current={recordTab === "note" ? "page" : undefined}
            onClick={() => setRecordTab("note")}
          >
            <PixelVisit /> Doctor's note
          </button>
          <button
            type="button"
            aria-current={recordTab === "reading" ? "page" : undefined}
            onClick={() => setRecordTab("reading")}
          >
            <PixelPill /> Report reading
          </button>
          <button
            type="button"
            aria-current={recordTab === "source" ? "page" : undefined}
            onClick={() => setRecordTab("source")}
          >
            <PixelDocument /> Image & recording
          </button>
        </nav>
      )}
      {(!ready || recordTab === "source") && (
        <section className="source-module">
          <div className="source-image">
            <h2>
              {run.status === "awaiting_confirmation"
                ? "Check the privacy preview"
                : "Report image"}
            </h2>
            {run.status === "queued" ? (
              <p role="status">Preparing the redaction preview…</p>
            ) : imageMissing ? (
              <div className="banner review">
                <p>The preview could not be loaded.</p>
                <button
                  type="button"
                  className="secondary"
                  onClick={() => {
                    setImageLoaded(false);
                    setImageMissing(false);
                    setImageAttempt((a) => a + 1);
                  }}
                >
                  Retry preview
                </button>
              </div>
            ) : (
              <div className="sheet">
                <img
                  key={`${run.run_id}-${imageAttempt}`}
                  src={`${apiBase}${run.overlay_url}`}
                  alt="Report with private regions marked in red"
                  onLoad={() => setImageLoaded(true)}
                  onError={() => {
                    setImageLoaded(false);
                    setImageMissing(true);
                  }}
                />
              </div>
            )}
          </div>
          <aside className="source-actions">
            {run.status === "awaiting_confirmation" ? (
              <>
                <h2>Before processing</h2>
                <p>
                  Red marks hidden details. Check that names, phone numbers and
                  other identifiers are covered. Green marks the area to be
                  read.
                </p>
                <button
                  className="primary"
                  disabled={busy || !imageLoaded || imageMissing}
                  onClick={() => void confirm()}
                >
                  Confirm privacy & continue
                </button>
              </>
            ) : (
              <>
                <h2>Saved source files</h2>
                {run.original_available && (
                  <p>
                    <a
                      href={`${apiBase}/api/runs/${encodeURIComponent(run.run_id)}/files/original`}
                    >
                      Download original image
                    </a>
                  </p>
                )}
                {run.audio_available && (
                  <>
                    <label htmlFor="doctor-audio">Doctor's recording</label>
                    <audio
                      id="doctor-audio"
                      controls
                      preload="metadata"
                      src={`${apiBase}/api/runs/${encodeURIComponent(run.run_id)}/files/audio`}
                    />
                  </>
                )}
                {!run.original_available && !run.audio_available && (
                  <p>Original files are not available for this record.</p>
                )}
              </>
            )}
          </aside>
        </section>
      )}
      {ready && recordTab === "reading" && (
        <section className="reading-module">
          <h2>Report reading</h2>
          <p className="module-help">
            Provisional AI extraction. Check it against the image; unclear
            handwriting may be missing.
          </p>
          {run.extraction &&
          (run.extraction.rows.length ||
            run.extraction.medications.length ||
            run.extraction.advised_tests.length) ? (
            <>
              <div className="clinical-reading-grid">
                <section>
                  <h3>Medicines as written</h3>
                  {run.extraction.medications.length ? (
                    <ul className="reading-list">
                      {run.extraction.medications.map((m, i) => (
                        <li key={i}>{m.raw_text}</li>
                      ))}
                    </ul>
                  ) : (
                    <p>No medicines could be extracted.</p>
                  )}
                </section>
                <section>
                  <h3>Test results</h3>
                  {run.extraction.rows.length ? (
                    <div className="table-scroll">
                      <table>
                        <thead>
                          <tr>
                            <th>As written</th>
                            <th>Value</th>
                            <th>Unit</th>
                          </tr>
                        </thead>
                        <tbody>
                          {run.extraction.rows.map((r, i) => (
                            <tr key={i}>
                              <td>{r.raw_name}</td>
                              <td>
                                {r.value ?? r.value_text ?? "Not recorded"}
                              </td>
                              <td>{r.unit || "—"}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <p>No test results extracted.</p>
                  )}
                  <h3>Tests as written</h3>
                  <ul>
                    {run.extraction.advised_tests.map((t, i) => (
                      <li key={i}>{t.raw_name}</li>
                    ))}
                  </ul>
                </section>
              </div>
            </>
          ) : (
            <div className="empty-inline">
              No readable medicines or results were extracted. Review the
              original image and the dictated note.
            </div>
          )}
        </section>
      )}
      {ready && recordTab === "note" && (
        <section className="note-module">
          {draft ? (
            <>
              <div className="module-heading">
                <div>
                  <h2>Review your dictated note</h2>
                  <p>
                    Correct the transcript and both language versions before
                    publishing to the patient's history.
                  </p>
                </div>
              </div>
              <label className="auth-field">
                Voice transcript
                <textarea
                  rows={4}
                  value={draft.transcript}
                  onChange={(e) => {
                    setAcknowledged(false);
                    setDraft({ ...draft, transcript: e.target.value });
                  }}
                />
              </label>
              {issues(draft.unresolved).length > 0 && (
                <details className="review-issues">
                  <summary>
                    {issues(draft.unresolved).length} items need your attention
                  </summary>
                  <ul>
                    {issues(draft.unresolved).map((item, i) => (
                      <li key={i}>{item}</li>
                    ))}
                  </ul>
                </details>
              )}
              <div className="note-languages">
                <label className="auth-field">
                  English version
                  <textarea
                    rows={7}
                    value={draft.summary_en}
                    onChange={(e) => {
                      setAcknowledged(false);
                      setDraft({ ...draft, summary_en: e.target.value });
                    }}
                  />
                </label>
                <label className="auth-field">
                  বাংলা সংস্করণ
                  <textarea
                    lang="bn"
                    rows={7}
                    value={draft.summary_bn}
                    onChange={(e) => {
                      setAcknowledged(false);
                      setDraft({ ...draft, summary_bn: e.target.value });
                    }}
                  />
                </label>
              </div>
              <div className="publish-bar">
                <label className="check">
                  <input
                    type="checkbox"
                    checked={acknowledged}
                    onChange={(e) => setAcknowledged(e.target.checked)}
                  />
                  I reviewed the transcript, both versions and unresolved
                  details.
                </label>
                <div className="row-actions">
                  <button
                    className="secondary"
                    disabled={busy}
                    onClick={() => void save(false)}
                  >
                    Save draft
                  </button>
                  <button
                    className="primary"
                    disabled={
                      busy ||
                      !acknowledged ||
                      !draft.transcript.trim() ||
                      !draft.summary_en.trim() ||
                      !draft.summary_bn.trim()
                    }
                    onClick={() => void save(true)}
                  >
                    {busy ? "Saving…" : "Verify and publish"}
                  </button>
                </div>
              </div>
            </>
          ) : (
            !summaries.some((s) => s.status === "published") && (
              <div className="empty-inline">
                <h2>No doctor-published note</h2>
                <p>
                  This record has no note available to publish. Return to the
                  patient chart to add a report and voice explanation.
                </p>
              </div>
            )
          )}
          {summaries
            .filter(
              (entry) =>
                entry.status === "published" &&
                !summaries.some(
                  (other) =>
                    other.status === "published" &&
                    other.amends_id === entry.id,
                ),
            )
            .map((entry) => (
              <article className="published-note" key={entry.id}>
                <div className="module-heading">
                  <div>
                    <h2>Published note</h2>
                    <p>
                      {entry.author_name || "Doctor"} ·{" "}
                      {entry.published_at
                        ? new Date(entry.published_at).toLocaleString()
                        : "Published"}
                    </p>
                  </div>
                  <button
                    className="secondary"
                    disabled={busy || !!draft}
                    onClick={() => void amend(entry.id)}
                  >
                    Add correction
                  </button>
                </div>
                <div className="note-languages">
                  <div>
                    <h3>English</h3>
                    <p className="doctor-summary">{entry.summary_en}</p>
                  </div>
                  <div lang="bn">
                    <h3>বাংলা</h3>
                    <p className="doctor-summary">{entry.summary_bn}</p>
                  </div>
                </div>
              </article>
            ))}
        </section>
      )}
    </main>
  );
}
