import { PublicationChecks } from "./PublicationChecks";
import { useEffect, useRef, useState, type FormEvent } from "react";
import {
  apiBase,
  createPrescription,
  getChart,
  getRun,
  getSampleDictation,
  post,
} from "./api";
import {
  navigate,
  registerNavigationGuard,
  recordReturnUrl,
} from "./navigation";
import { useRecorder } from "./useRecorder";
import { PrescriptionEditor, PrescriptionTable } from "./PrescriptionTable";
import type { ClinicalSummary, Run } from "./types";
import { useApp } from "./store";

export function NewPrescription({
  patientId,
  visitId,
  isDemo,
  onLockChange,
}: {
  patientId: string;
  visitId?: string;
  isDemo: boolean;
  onLockChange: (locked: boolean) => void;
}) {
  const recorder = useRecorder();
  const [mode, setMode] = useState<"voice" | "manual">("voice");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const key = useRef(crypto.randomUUID());
  const submitted = useRef(false);
  useEffect(() => {
    onLockChange(
      busy || recorder.recording || recorder.starting || !!recorder.audio,
    );
    return () => onLockChange(false);
  }, [
    busy,
    recorder.recording,
    recorder.starting,
    recorder.audio,
    onLockChange,
  ]);
  const [preview, setPreview] = useState("");
  useEffect(() => {
    if (!recorder.audio) {
      setPreview("");
      return;
    }
    const url = URL.createObjectURL(recorder.audio);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [recorder.audio]);
  useEffect(() => {
    if (!recorder.audio && !recorder.recording) return;
    const warn = () =>
      submitted.current ||
      window.confirm(
        "Discard the prescription recording you have not submitted?",
      );
    const leave = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = "";
    };
    const remove = registerNavigationGuard(warn);
    window.addEventListener("beforeunload", leave);
    return () => {
      remove();
      window.removeEventListener("beforeunload", leave);
    };
  }, [recorder.audio, recorder.recording]);
  function chooseMode(next: "voice" | "manual") {
    if (next === mode) return;
    if (
      recorder.audio &&
      !window.confirm("Discard the unsubmitted recording and write manually?")
    )
      return;
    recorder.discard();
    setMode(next);
    key.current = crypto.randomUUID();
  }
  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    const data = new FormData();
    data.append("mode", mode);
    data.append("idempotency_key", key.current);
    if (visitId) data.append("visit_id", visitId);
    if (mode === "voice" && recorder.audio)
      data.append("audio", recorder.audio, "prescription.wav");
    try {
      const result = await createPrescription(patientId, data);
      submitted.current = true;
      recorder.discard();
      navigate(`/doctor/records/${result.run_id}`);
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Could not create the prescription.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <form className="new-prescription" onSubmit={submit}>
      <h2>New prescription</h2>
      <div className="segmented" aria-label="Prescription entry method">
        <button
          type="button"
          disabled={recorder.recording || recorder.starting || busy}
          aria-pressed={mode === "voice"}
          onClick={() => chooseMode("voice")}
        >
          Dictate a prescription
        </button>
        <button
          type="button"
          disabled={recorder.recording || recorder.starting || busy}
          aria-pressed={mode === "manual"}
          onClick={() => chooseMode("manual")}
        >
          Write manually
        </button>
      </div>
      {visitId && (
        <section
          className="prescription-image-option"
          aria-labelledby="prescription-image-heading"
        >
          <div>
            <h3 id="prescription-image-heading">Have a handwritten prescription?</h3>
            <p className="module-help">
              Upload a photo, add a voice explanation, or use both. We’ll prepare an
              editable draft for your review.
            </p>
          </div>
          <button
            className="secondary"
            type="button"
            disabled={
              busy || recorder.recording || recorder.starting || !!recorder.audio
            }
            onClick={() => navigate(`/doctor/visits/${visitId}/prescription-image`)}
          >
            Upload handwritten prescription
          </button>
        </section>
      )}
      {mode === "voice" ? (
        <>
          <p>
            Say each medicine’s name, strength, amount, morning/noon/night
            timing, instructions and duration. You can edit everything before
            publishing.
          </p>
          <p className="module-help">
            Up to 3 minutes. Meta transcribes and structures the recording; the
            original recording is saved in the patient’s chart.
          </p>
          <div className="action-group">
            <button
              className="secondary"
              type="button"
              disabled={busy || recorder.starting}
              onClick={() => {
                key.current = crypto.randomUUID();
                if (recorder.recording) recorder.stop();
                else void recorder.start();
              }}
            >
              {recorder.starting
                ? "Opening microphone…"
                : recorder.recording
                  ? "Stop recording"
                  : recorder.audio
                    ? "Record again"
                    : "Start recording"}
            </button>
            {recorder.audio && (
              <button
                className="text-link"
                type="button"
                disabled={busy}
                onClick={recorder.discard}
              >
                Discard recording
              </button>
            )}
          </div>
          {preview && (
            <audio
              controls
              src={preview}
              aria-label="Prescription recording preview"
            />
          )}
          <label>
            Or upload a recording (WAV)
            <input
              type="file"
              accept="audio/wav,.wav"
              disabled={busy || recorder.recording}
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) {
                  key.current = crypto.randomUUID();
                  recorder.useBlob(file);
                }
              }}
            />
          </label>
          {isDemo && (
            <button
              className="text-link"
              type="button"
              onClick={() =>
                void getSampleDictation()
                  .then(recorder.useBlob)
                  .catch((e) => setError(e.message))
              }
            >
              Use fictional sample recording
            </button>
          )}
        </>
      ) : (
        <p>
          Enter the medicines and instructions yourself. You can save a draft
          before publishing.
        </p>
      )}
      {(error || recorder.error) && (
        <p role="alert" className="banner pii">
          {error || recorder.error}
        </p>
      )}
      <button
        className="primary"
        disabled={
          busy ||
          recorder.recording ||
          recorder.starting ||
          (mode === "voice" && !recorder.audio)
        }
      >
        {busy
          ? "Creating…"
          : mode === "voice"
            ? "Create prescription draft"
            : "Start manual prescription"}
      </button>
    </form>
  );
}

function snapshot(draft: ClinicalSummary | null) {
  return draft
    ? JSON.stringify([
        draft.transcript,
        draft.summary_en,
        draft.summary_bn,
        draft.prescription,
      ])
    : "";
}

export function PrescriptionWorkspace({ run: initial }: { run: Run }) {
  const userId = useApp((state) => state.user?.id);
  const [run, setRun] = useState(initial);
  const [mobileView, setMobileView] = useState<"source" | "review">("review");
  const [zoom, setZoom] = useState(1);
  const [scanFailed, setScanFailed] = useState(false);
  const [summaries, setSummaries] = useState<ClinicalSummary[]>([]);
  const [draft, setDraft] = useState<ClinicalSummary | null>(null);
  const saved = useRef("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [reviewed, setReviewed] = useState(false);
  const [summariesLoading, setSummariesLoading] = useState(true);
  const [summariesError, setSummariesError] = useState("");
  const loadSequence = useRef(0);
  useEffect(() => setRun(initial), [initial]);
  async function load() {
    const sequence = ++loadSequence.current;
    setSummariesLoading(true);
    setSummariesError("");
    try {
      const result = await getChart<{ summaries: ClinicalSummary[] }>(
        `/records/${run.run_id}/summaries`,
      );
      if (sequence !== loadSequence.current) return;
      setSummaries(result.summaries);
      const next = result.summaries.find((s) => s.status === "draft") || null;
      saved.current = snapshot(next);
      setDraft(next);
      setReviewed(false);
    } catch (error) {
      if (sequence === loadSequence.current)
        setSummariesError(
          error instanceof Error
            ? error.message
            : "Could not load the saved prescription.",
        );
      throw error;
    } finally {
      if (sequence === loadSequence.current) setSummariesLoading(false);
    }
  }
  useEffect(() => {
    if (["reviewing", "approved", "exported"].includes(run.status))
      void load().catch((e) => setError(e.message));
  }, [run.run_id, run.status]);
  const dirty = snapshot(draft) !== saved.current;
  useEffect(() => {
    if (!dirty) return;
    const remove = registerNavigationGuard(() =>
      window.confirm("Leave without saving your prescription changes?"),
    );
    const leave = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", leave);
    return () => {
      remove();
      window.removeEventListener("beforeunload", leave);
    };
  }, [dirty]);
  async function save(publish: boolean) {
    if (!draft) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await post(
        `/api/chart/records/${run.run_id}/summaries/${draft.id}?publish=${publish}`,
        {
          transcript: draft.transcript,
          summary_en: draft.summary_en,
          summary_bn: draft.summary_bn,
          expected_revision: draft.revision,
          prescription: draft.prescription,
          reviewed_both_languages: reviewed,
          acknowledge_unresolved: reviewed,
        },
      );
      await load();
      setNotice(
        publish
          ? "Prescription published to the patient’s chart."
          : "Prescription draft saved.",
      );
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Could not save the prescription.",
      );
    } finally {
      setBusy(false);
    }
  }
  const published = summaries.filter(
    (s) =>
      s.status === "published" &&
      !summaries.some((n) => n.status === "published" && n.amends_id === s.id),
  );
  const ready = ["reviewing", "approved", "exported"].includes(run.status);
  const requiresMedicine = [
    "voice_prescription",
    "manual_prescription",
  ].includes(run.input_mode || "");
  const unchecked =
    draft?.prescription?.filter((m) => !m.confirmed || !m.name.trim()) || [];
  const remaining = draft
    ? [
        ...(requiresMedicine && !draft.prescription?.length
          ? [
              {
                text: "Add at least one medicine",
                target: "prescription-medicines",
              },
            ]
          : []),
        ...unchecked.map((m) => ({
          text: `${m.name.trim() || "Unnamed medicine"}: check name, strength and instructions`,
          target: `medicine-${m.id}`,
        })),
        ...(!draft.transcript.trim() && !(run.input_mode === "image" && !run.audio_available)
          ? [
              {
                text: "Enter the doctor’s note",
                target: "prescription-transcript",
              },
            ]
          : []),
        ...(!draft.summary_en.trim()
          ? [{ text: "Add the English assessment", target: "assessment-en" }]
          : []),
        ...(!draft.summary_bn.trim()
          ? [{ text: "Add the Bangla assessment", target: "assessment-bn" }]
          : []),
        ...(!reviewed
          ? [
              {
                text: "Review both languages and complete the final check",
                target: "prescription-reviewed",
              },
            ]
          : []),
      ]
    : [];
  return (
    <main className={`workspace prescription-workspace rx-view-${mobileView}`}>
      <button
        className="back-link"
        type="button"
        onClick={() => navigate(recordReturnUrl(run.patient_id, run.visit_id))}
      >
        Back to patient chart
      </button>
      <div className="module-heading">
        <h1>Prescription</h1>
        <button
          className="secondary"
          type="button"
          disabled={busy}
          onClick={async () => {
            if (dirty && !window.confirm("Reload and discard unsaved changes?"))
              return;
            try {
              setRun(await getRun(run.run_id));
              await load();
            } catch (e) {
              setError(e instanceof Error ? e.message : "Could not refresh.");
            }
          }}
        >
          Refresh status
        </button>
      </div>
      <p className="prescription-patient">
        For {run.patient_name || run.pseudonym}
      </p>
      {error && (
        <p role="alert" className="banner pii">
          {error}
        </p>
      )}
      {notice && (
        <p role="status" className="banner">
          {notice}
        </p>
      )}
      {!ready && (
        <section>
          <h2>
            {run.status === "failed" || run.status === "interrupted"
              ? "Prescription needs another try"
              : "Preparing the prescription…"}
          </h2>
          <p>
            The recording is saved. Reopening this page does not repeat
            processing.
          </p>
          {run.trace.filter((event) => event.kind === "error").at(-1)
            ?.message && (
            <p role="alert">
              {
                run.trace.filter((event) => event.kind === "error").at(-1)
                  ?.message
              }
            </p>
          )}
          {["failed", "interrupted"].includes(run.status) && (
            <button
              className="secondary"
              type="button"
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                setError("");
                try {
                  await post(
                    `/api/chart/records/${run.run_id}/prescription/retry`,
                  );
                  window.location.reload();
                } catch (e) {
                  setError(e instanceof Error ? e.message : "Could not retry.");
                  setBusy(false);
                }
              }}
            >
              Retry processing
            </button>
          )}
        </section>
      )}
      {run.audio_available && (
        <section className="prescription-audio">
          <h2>Original dictation</h2>
          <audio
            controls
            preload="metadata"
            aria-label="Original prescription dictation"
            src={`${apiBase}/api/runs/${run.run_id}/files/audio`}
          />
        </section>
      )}
      {ready && summariesLoading && (
        <p role="status">Loading the saved prescription…</p>
      )}
      {ready && summariesError && (
        <div className="banner pii" role="alert">
          <p>{summariesError}</p>
          <button
            type="button"
            className="secondary"
            onClick={() => void load().catch(() => {})}
          >
            Try loading again
          </button>
        </div>
      )}
      {run.input_mode === "image" && run.redacted_url && (
        <>
          <div
            className="rx-mobile-views segmented"
            aria-label="Prescription view"
          >
            <button
              type="button"
              aria-pressed={mobileView === "source"}
              onClick={() => setMobileView("source")}
            >
              Source
            </button>
            <button
              type="button"
              aria-pressed={mobileView === "review"}
              onClick={() => setMobileView("review")}
            >
              Review
            </button>
          </div>
        </>
      )}
      <div className="rx-review-grid">
        {run.input_mode === "image" && run.redacted_url && (
          <section className="prescription-scan">
            <h2>Prescription image</h2>
            <div className="action-group">
              <button
                type="button"
                className="secondary"
                onClick={() => setZoom(1)}
              >
                Fit width
              </button>
              <button
                type="button"
                className="secondary"
                disabled={zoom >= 3}
                onClick={() => setZoom((value) => Math.min(3, value + 0.5))}
              >
                Zoom in
              </button>
              <a
                href={`${apiBase}${run.redacted_url}`}
                target="_blank"
                rel="noreferrer"
              >
                Full size ↗
              </a>
            </div>
            {scanFailed ? (
              <p role="status">
                Source image unavailable. Your saved reading is still here.
              </p>
            ) : (
              <div className="rx-scan-scroll">
                <img
                  style={{ width: `${zoom * 100}%` }}
                  onError={() => setScanFailed(true)}
                  src={`${apiBase}${run.redacted_url}`}
                  alt="Prescription image with private details hidden"
                />
              </div>
            )}
          </section>
        )}
        {draft && (
          <fieldset
            className="prescription-draft-fields"
            aria-label="Prescription draft"
            disabled={busy}
          >
            <details className="dictation-transcript">
              <summary>
                {run.input_mode === "voice_prescription"
                  ? "Read or correct the transcript"
                  : "Doctor’s additional note"}
              </summary>
              <label>
                Doctor’s words
                <textarea
                  id="prescription-transcript"
                  value={draft.transcript}
                  maxLength={20000}
                  onChange={(e) => {
                    setDraft({
                      ...draft,
                      transcript: e.target.value,
                      prescription: draft.prescription?.map((m) => ({
                        ...m,
                        confirmed: false,
                      })),
                    });
                    setReviewed(false);
                  }}
                />
              </label>
              <p className="module-help">
                Changing this text does not rerun the AI. Update the medicine
                rows below to match your corrections.
              </p>
            </details>
            {draft.unresolved && draft.unresolved !== "[]" && (
              <details className="review-issues">
                <summary>Check unclear details from dictation</summary>
                <p>
                  {typeof draft.unresolved === "string"
                    ? (() => {
                        try {
                          return JSON.parse(draft.unresolved).join("\n");
                        } catch {
                          return draft.unresolved;
                        }
                      })()
                    : draft.unresolved.join("\n")}
                </p>
              </details>
            )}
            <PrescriptionEditor
              medicines={draft.prescription || []}
              onChange={(rows) => {
                setDraft({ ...draft, prescription: rows });
                setReviewed(false);
              }}
            />
            <section className="prescription-assessment">
              <h2>Assessment and follow-up</h2>
              <div className="bilingual-editor">
                <label>
                  English
                  <textarea
                    id="assessment-en"
                    value={draft.summary_en}
                    maxLength={12000}
                    onChange={(e) => {
                      setDraft({ ...draft, summary_en: e.target.value });
                      setReviewed(false);
                    }}
                  />
                </label>
                <label>
                  বাংলা
                  <textarea
                    id="assessment-bn"
                    lang="bn"
                    value={draft.summary_bn}
                    maxLength={12000}
                    onChange={(e) => {
                      setDraft({ ...draft, summary_bn: e.target.value });
                      setReviewed(false);
                    }}
                  />
                </label>
              </div>
            </section>
            <PublicationChecks items={remaining} />
            <div className="publish-bar prescription-publish-bar">
              <p className="draft-status" role="status">
                {busy ? "Saving…" : dirty ? "Unsaved changes" : "Saved"}
              </p>
              <label className="check">
                <input
                  id="prescription-reviewed"
                  type="checkbox"
                  checked={reviewed}
                  onChange={(e) => setReviewed(e.target.checked)}
                />
                I checked every medicine, both language versions and any unclear
                details.
              </label>
              <div className="action-group">
                <button
                  className="secondary"
                  type="button"
                  disabled={busy || !dirty}
                  onClick={() => void save(false)}
                >
                  Save draft
                </button>
                <button
                  className="primary"
                  type="button"
                  disabled={
                    busy ||
                    !reviewed ||
                    (requiresMedicine && !draft.prescription?.length) ||
                    draft.prescription?.some(
                      (m) => !m.confirmed || !m.name.trim(),
                    ) ||
                    !draft.summary_en.trim() ||
                    !draft.summary_bn.trim() ||
                    (!draft.transcript.trim() && !(run.input_mode === "image" && !run.audio_available))
                  }
                  onClick={() => void save(true)}
                >
                  {busy ? "Saving…" : "Verify and publish prescription"}
                </button>
              </div>
            </div>
          </fieldset>
        )}
      </div>
      {ready &&
        !summariesLoading &&
        !summariesError &&
        !draft &&
        !published.length && (
          <p className="empty-inline">
            The author has not published this prescription yet.
          </p>
        )}
      {published.map((note) => (
        <article className="published-note" key={note.id}>
          <h2>Published prescription</h2>
          <p>Patient: {run.patient_name || run.pseudonym}</p>
          <p>
            {note.author_name} ·{" "}
            {note.published_at && new Date(note.published_at).toLocaleString()}
          </p>
          <PrescriptionTable medicines={note.prescription || []} />
          <div className="bilingual-editor">
            <section>
              <h3>English</h3>
              <p>{note.summary_en}</p>
            </section>
            <section lang="bn">
              <h3>বাংলা</h3>
              <p>{note.summary_bn}</p>
            </section>
          </div>
          <div className="action-group">
            <button
              className="secondary"
              type="button"
              onClick={() => window.print()}
            >
              Print prescription
            </button>
            {note.author_id === userId && (
              <button
                className="secondary"
                type="button"
                disabled={busy || !!draft}
                onClick={async () => {
                  setBusy(true);
                  try {
                    await post(
                      `/api/chart/records/${run.run_id}/summaries/${note.id}/amend`,
                    );
                    await load();
                  } catch (e) {
                    setError(
                      e instanceof Error
                        ? e.message
                        : "Could not create amendment.",
                    );
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                Create amendment
              </button>
            )}
          </div>
        </article>
      ))}
    </main>
  );
}
