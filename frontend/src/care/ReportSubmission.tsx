import { useEffect, useRef, useState, type FormEvent } from "react";
import { createRun, getChart, getSampleDictation } from "../api";
import { prepareImage } from "../image";
import { navigate, registerNavigationGuard } from "../navigation";
import { useRecorder } from "../useRecorder";
import type { Visit } from "./types";
import { useApp } from "../store";

export function ReportSubmission({ visit }: { visit: Visit }) {
  const sharedDemo = useApp((state) => state.user?.id === "demo-doctor");
  const recorder = useRecorder();
  const [image, setImage] = useState<File | null>(null);
  const [savedReport, setSavedReport] = useState("");
  const [reports, setReports] = useState<
    { run_id: string; title: string; source_available: boolean }[] | null
  >(null);
  const [busy, setBusy] = useState(false);
  const [preparing, setPreparing] = useState(false);
  const [error, setError] = useState("");
  const [preview, setPreview] = useState("");
  const key = useRef(crypto.randomUUID());
  const submitted = useRef(false);
  const dirty = !!(
    image ||
    savedReport ||
    recorder.audio ||
    recorder.recording
  );
  useEffect(() => {
    if (!dirty) return;
    const remove = registerNavigationGuard(
      () =>
        submitted.current ||
        window.confirm("Leave without submitting this report and recording?"),
    );
    const unload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", unload);
    return () => {
      remove();
      window.removeEventListener("beforeunload", unload);
    };
  }, [dirty]);
  useEffect(() => {
    if (!recorder.audio) {
      setPreview("");
      return;
    }
    const url = URL.createObjectURL(recorder.audio);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [recorder.audio]);
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!recorder.audio || (!image && !savedReport)) return;
    setBusy(true);
    setError("");
    const form = new FormData();
    form.append("patient_id", visit.patient_id);
    form.append("visit_id", visit.id);
    form.append("idempotency_key", key.current);
    form.append("audio", recorder.audio, "visit.wav");
    if (image) form.append("image", image);
    else form.append("source_run_id", savedReport);
    try {
      const result = await createRun(form);
      submitted.current = true;
      recorder.discard();
      navigate(`/doctor/records/${result.run_id}`);
    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : "The upload failed. Please retry.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <form className="care-report-form" onSubmit={(event) => void submit(event)}>
      <p className="care-help">
        The report and voice are saved in this visit and sent to Meta for
        processing. You’ll check privacy first, then edit the medication table
        and both language versions before publishing.
      </p>
      <div className="care-input-pair">
        <section>
          <h2>Report</h2>
          {sharedDemo ? (
            <p className="care-help">
              Shared demo: choose a fictional sample. File upload is
              unavailable.
            </p>
          ) : (
            <label>
              Choose an image
              <input
                type="file"
                accept="image/*"
                disabled={busy || preparing}
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (!file) return;
                  key.current = crypto.randomUUID();
                  setImage(null);
                  setSavedReport("");
                  setPreparing(true);
                  setError("");
                  void prepareImage(file)
                    .then(setImage)
                    .catch((error) => setError(error.message))
                    .finally(() => setPreparing(false));
                }}
              />
            </label>
          )}
          {preparing && <p role="status">Preparing image…</p>}
          {image && <p>{image.name}</p>}
          <button
            className="text-link"
            type="button"
            disabled={busy || preparing}
            onClick={() => {
              setError("");
              void getChart<{ records: NonNullable<typeof reports> }>(
                `/records?patient_id=${visit.patient_id}&include_source=true`,
              )
                .then((result) =>
                  setReports(
                    result.records.filter((row) => row.source_available),
                  ),
                )
                .catch((error) => setError(error.message));
            }}
          >
            {sharedDemo
              ? "Choose a fictional sample report"
              : "Use a saved report instead"}
          </button>
          {reports && (
            <label>
              Saved report
              <select
                value={savedReport}
                disabled={busy}
                onChange={(event) => {
                  setSavedReport(event.target.value);
                  setImage(null);
                  key.current = crypto.randomUUID();
                }}
              >
                <option value="">Choose a report</option>
                {reports.map((row) => (
                  <option key={row.run_id} value={row.run_id}>
                    {row.title}
                  </option>
                ))}
              </select>
            </label>
          )}
        </section>
        <section>
          <h2>Voice explanation</h2>
          <p className="care-help">
            Up to 3 minutes. Include medicine names, strengths, doses, timing
            and duration.
          </p>
          <div className="care-actions">
            <button
              type="button"
              className={recorder.recording ? "primary" : "secondary"}
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
            {recorder.audio && !recorder.recording && (
              <button
                className="text-link"
                type="button"
                disabled={busy}
                onClick={recorder.discard}
              >
                Discard
              </button>
            )}
          </div>
          {preview && (
            <audio
              controls
              src={preview}
              aria-label="Voice recording preview"
            />
          )}
          <details>
            <summary>Use a recording file</summary>
            <label>
              WAV recording
              <input
                type="file"
                accept="audio/wav,.wav"
                disabled={busy || recorder.recording}
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (file) {
                    key.current = crypto.randomUUID();
                    recorder.useBlob(file);
                  }
                }}
              />
            </label>
            <button
              className="text-link"
              type="button"
              disabled={busy || recorder.recording}
              onClick={() =>
                void getSampleDictation()
                  .then(recorder.useBlob)
                  .catch((error) => setError(error.message))
              }
            >
              Use fictional sample recording
            </button>
          </details>
        </section>
      </div>
      {(error || recorder.error) && (
        <p role="alert" className="care-error">
          {error || recorder.error}
        </p>
      )}
      <div className="care-submit">
        <button
          className="primary"
          disabled={
            busy ||
            preparing ||
            recorder.recording ||
            recorder.starting ||
            !recorder.audio ||
            (!image && !savedReport)
          }
        >
          {busy ? "Uploading…" : "Check privacy preview"}
        </button>
        <p className="care-help">Both the report and recording are required.</p>
      </div>
    </form>
  );
}
