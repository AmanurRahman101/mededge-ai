import { useCallback, useEffect, useRef, useState } from "react";
import { apiBase, confirmRun, getChart, post } from "./api";
import { PublicationChecks } from "./PublicationChecks";
import { PrescriptionWorkspace } from "./PrescriptionWorkspace";
import { MedicineLookup } from "./MedicineLookup";
import {
  navigate,
  registerNavigationGuard,
  recordReturnUrl,
} from "./navigation";
import { recordStatus } from "./ChartOverview";
import { PixelDocument, PixelPill, PixelVisit } from "./PixelIcons";
import { useRun } from "./useRun";
import { useApp } from "./store";
import "./Doctor.css";

type Summary = {
  id: string;
  revision: number;
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

export function Doctor({
  initialRunId = null,
}: {
  initialRunId?: string | null;
}) {
  const { run, events, error: runError } = useRun(initialRunId);
  const userId = useApp((state) => state.user?.id);
  const [recordTab, setRecordTab] = useState<"note" | "reading" | "source">(
    "reading",
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [summaryLoadState, setSummaryLoadState] = useState<
    "loading" | "ready" | "failed"
  >("loading");
  const [summaries, setSummaries] = useState<Summary[]>([]);
  const [draft, setDraft] = useState<Summary | null>(null);
  const savedDraft = useRef("");
  const [zoom, setZoom] = useState(100);
  const [acknowledged, setAcknowledged] = useState(false);
  const [imageMissing, setImageMissing] = useState(false);
  const [imageLoaded, setImageLoaded] = useState(false);
  const [imageAttempt, setImageAttempt] = useState(0);
  const loadSummaries = useCallback(async (id: string) => {
    setSummaryLoadState("loading");
    try {
      const data = await getChart<{ summaries: Summary[] }>(
        `/records/${encodeURIComponent(id)}/summaries`,
      );
      setSummaries(data.summaries);
      const nextDraft =
        data.summaries.find((entry) => entry.status === "draft") || null;
      savedDraft.current = nextDraft
        ? JSON.stringify([
            nextDraft.transcript,
            nextDraft.summary_en,
            nextDraft.summary_bn,
          ])
        : "";
      setDraft(nextDraft);
      if (data.summaries.length) setRecordTab("note");
      setAcknowledged(false);
      setSummaryLoadState("ready");
    } catch (error) {
      setSummaryLoadState("failed");
      throw error;
    }
  }, []);
  useEffect(() => {
    if (run?.input_mode === "visit_note") setRecordTab("note");
  }, [run?.run_id, run?.input_mode]);
  useEffect(() => {
    if (
      run &&
      !run.has_prescription_table &&
      !["voice_prescription", "manual_prescription"].includes(
        run.input_mode || "",
      ) &&
      ["reviewing", "approved", "exported"].includes(run.status)
    ) {
      void loadSummaries(run.run_id).catch((caught) =>
        setError(textError(caught)),
      );
    }
  }, [run?.run_id, run?.status, loadSummaries]);

  const draftDirty =
    !!draft &&
    !!savedDraft.current &&
    JSON.stringify([draft.transcript, draft.summary_en, draft.summary_bn]) !==
      savedDraft.current;
  useEffect(() => {
    if (!draftDirty) return;
    const unregister = registerNavigationGuard(() =>
      window.confirm("You have unsaved changes. Leave without saving?"),
    );
    const beforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", beforeUnload);
    return () => {
      unregister();
      window.removeEventListener("beforeunload", beforeUnload);
    };
  }, [draftDirty]);

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
          expected_revision: draft.revision,
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

  if (!run)
    return (
      <main className="workspace">
        <button
          className="back-link"
          type="button"
          onClick={() =>
            navigate(
              recordReturnUrl(
                new URLSearchParams(window.location.search).get("patient") ||
                  undefined,
              ),
            )
          }
        >
          ← Back to patient chart
        </button>
        <h1>Opening record…</h1>
        {(error || runError) && (
          <p className="banner pii" role="alert">
            {error || runError}
          </p>
        )}
      </main>
    );

  if (
    run.has_prescription_table ||
    run.input_mode === "voice_prescription" ||
    run.input_mode === "manual_prescription"
  )
    return <PrescriptionWorkspace run={run} />;
  const ready = ["reviewing", "approved", "exported"].includes(run.status);
  return (
    <main className="workspace record-workspace">
      <button
        className="back-link"
        type="button"
        onClick={() => navigate(recordReturnUrl(run.patient_id, run.visit_id))}
      >
        ← Back to patient chart
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
              {run.patient_name || run.pseudonym} ·{" "}
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
      {ready && run.input_mode !== "visit_note" && (
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
      {ready && recordTab !== "source" && (
        <div
          className={`doctor-review-layout${run.input_mode === "visit_note" ? " note-only-layout" : ""}`}
        >
          {run.input_mode !== "visit_note" && (
            <aside
              className="doctor-compare-source"
              aria-label="Source report for comparison"
            >
              <div className="doctor-source-heading">
                <h2>Source report</h2>
                <div className="doctor-zoom-controls">
                  <button
                    className="secondary"
                    type="button"
                    onClick={() => setZoom((z) => Math.max(50, z - 25))}
                    aria-label="Zoom out"
                  >
                    −
                  </button>
                  <button
                    className="secondary"
                    type="button"
                    onClick={() => setZoom(100)}
                  >
                    Fit width
                  </button>
                  <button
                    className="secondary"
                    type="button"
                    onClick={() => setZoom((z) => Math.min(250, z + 25))}
                    aria-label="Zoom in"
                  >
                    +
                  </button>
                  <span aria-live="polite">{zoom}%</span>
                </div>
              </div>
              <p className="module-help">
                Redacted preview. Compare the reading with the original report.
              </p>
              {imageMissing ? (
                <div className="banner review">
                  <p>The source preview is unavailable.</p>
                  <button
                    className="secondary"
                    type="button"
                    onClick={() => {
                      setImageMissing(false);
                      setImageAttempt((a) => a + 1);
                    }}
                  >
                    Retry preview
                  </button>
                </div>
              ) : (
                <div className="doctor-source-scroll">
                  <img
                    key={`compare-${run.run_id}-${imageAttempt}`}
                    src={`${apiBase}${run.redacted_url || run.overlay_url}`}
                    alt="Redacted report for comparison"
                    style={{ width: `${zoom}%`, maxWidth: "none" }}
                    onError={() => setImageMissing(true)}
                  />
                </div>
              )}
              <div className="doctor-source-files">
                {run.original_available && (
                  <a
                    href={`${apiBase}/api/runs/${encodeURIComponent(run.run_id)}/files/original`}
                  >
                    Download original image
                  </a>
                )}
                {run.audio_available && (
                  <>
                    <label htmlFor="comparison-audio">Doctor's recording</label>
                    <audio
                      id="comparison-audio"
                      controls
                      preload="metadata"
                      src={`${apiBase}/api/runs/${encodeURIComponent(run.run_id)}/files/audio`}
                    />
                  </>
                )}
              </div>
            </aside>
          )}
          <div className="doctor-review-content">
            {ready && recordTab === "reading" && (
              <section className="reading-module">
                <h2>Report reading</h2>
                <details className="medicine-reference-panel">
                  <summary>Look up a Bangladesh medicine</summary>
                  <MedicineLookup />
                </details>
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
                                      {r.value ??
                                        r.value_text ??
                                        "Not recorded"}
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
                {summaryLoadState === "loading" && (
                  <p role="status">Loading the saved note…</p>
                )}
                {summaryLoadState === "failed" && (
                  <div className="banner pii" role="alert">
                    The saved note could not be loaded.{" "}
                    <button
                      type="button"
                      className="secondary"
                      onClick={() =>
                        void loadSummaries(run.run_id).catch((caught) =>
                          setError(textError(caught)),
                        )
                      }
                    >
                      Try loading again
                    </button>
                  </div>
                )}
                {draft ? (
                  <>
                    <div className="module-heading">
                      <div>
                        <h2>
                          {run.input_mode === "visit_note"
                            ? "Write visit note"
                            : "Review your dictated note"}
                        </h2>
                        <p>
                          {run.input_mode === "visit_note"
                            ? "Write and review both language versions before publishing to the patient's history."
                            : "Correct the transcript and both language versions before publishing to the patient's history."}
                        </p>
                      </div>
                    </div>
                    <label className="auth-field">
                      {run.input_mode === "visit_note"
                        ? "Original note"
                        : "Voice transcript"}
                      <textarea
                        id="note-transcript"
                        rows={4}
                        disabled={busy}
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
                          {issues(draft.unresolved).length} items need your
                          attention
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
                          id="note-en"
                          rows={7}
                          disabled={busy}
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
                          id="note-bn"
                          lang="bn"
                          disabled={busy}
                          rows={7}
                          value={draft.summary_bn}
                          onChange={(e) => {
                            setAcknowledged(false);
                            setDraft({ ...draft, summary_bn: e.target.value });
                          }}
                        />
                      </label>
                    </div>
                    <PublicationChecks
                      items={[
                        ...(!draft.transcript.trim()
                          ? [
                              {
                                text: "Add the voice transcript",
                                target: "note-transcript",
                              },
                            ]
                          : []),
                        ...(!draft.summary_en.trim()
                          ? [
                              {
                                text: "Add the English version",
                                target: "note-en",
                              },
                            ]
                          : []),
                        ...(!draft.summary_bn.trim()
                          ? [
                              {
                                text: "Add the Bangla version",
                                target: "note-bn",
                              },
                            ]
                          : []),
                        ...(!acknowledged
                          ? [
                              {
                                text: "Review both versions and complete the final check",
                                target: "note-reviewed",
                              },
                            ]
                          : []),
                      ]}
                    />
                    <div className="publish-bar prescription-publish-bar">
                      <p className="draft-status" role="status">
                        {busy
                          ? "Saving…"
                          : draftDirty
                            ? "Unsaved changes"
                            : "Saved"}
                      </p>
                      <label className="check">
                        <input
                          type="checkbox"
                          id="note-reviewed"
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
                  summaryLoadState === "ready" &&
                  !summaries.some((s) => s.status === "published") && (
                    <div className="empty-inline">
                      <h2>No doctor-published note</h2>
                      <p>
                        This record has no note available to publish. Return to
                        the patient chart to add a report and voice explanation.
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
                        {entry.author_id === userId && (
                          <button
                            className="secondary"
                            disabled={busy || !!draft}
                            onClick={() => void amend(entry.id)}
                          >
                            Add correction
                          </button>
                        )}
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
          </div>
        </div>
      )}
    </main>
  );
}
