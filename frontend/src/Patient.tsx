import { usePatientLanguage, PatientLanguageControl } from "./patientLanguage";
import { useEffect, useState } from "react";
import { apiBase, confirmRun, createRun, getChart, listCases } from "./api";
import { useApp } from "./store";
import type { ClinicalSummary, SampleCase } from "./types";
import { useRun } from "./useRun";
import { navigate } from "./navigation";
import { prepareImage } from "./image";
import { PrescriptionTable } from "./PrescriptionTable";
import { recordStatus } from "./ChartOverview";
import {
  PixelDocument,
  PixelPill,
  PixelVisit,
  PixelWorkspaceIcon,
} from "./PixelIcons";

export function Patient({
  initialRunId = null,
}: {
  initialRunId?: string | null;
}) {
  const { t, message, locale, language } = usePatientLanguage();
  const patientName = useApp((state) => state.user?.full_name);
  const isDemo = useApp((state) => state.user?.id) === "demo-patient";
  const [runId, setRunId] = useState<string | null>(initialRunId);
  const [tab, setTab] = useState<"notes" | "reading" | "source">("reading");
  const [cases, setCases] = useState<SampleCase[]>([]);
  const [busy, setBusy] = useState(false);
  const [localError, setLocalError] = useState("");
  const [summaries, setSummaries] = useState<ClinicalSummary[]>([]);
  const [summaryError, setSummaryError] = useState("");
  const [imageUnavailable, setImageUnavailable] = useState(false);
  const [imageLoaded, setImageLoaded] = useState(false);
  const [imageAttempt, setImageAttempt] = useState(0);
  const { run, events, error } = useRun(runId);
  const waiting = run?.status === "awaiting_confirmation";
  const ready =
    !!run && ["reviewing", "approved", "exported"].includes(run.status);

  useEffect(() => {
    if (isDemo && !runId)
      void listCases()
        .then(setCases)
        .catch(() => setCases([]));
  }, [isDemo, runId]);
  useEffect(() => {
    if (!runId || !ready) return;
    let active = true;
    void getChart<{ summaries: ClinicalSummary[] }>(
      `/records/${encodeURIComponent(runId)}/summaries`,
    )
      .then((result) => {
        if (active) {
          setSummaries(result.summaries);
          setSummaryError("");
          if (result.summaries.some((s) => s.status === "published"))
            setTab("notes");
        }
      })
      .catch(() => {
        if (active)
          setSummaryError(
            "Could not load your doctor's notes. Refresh to try again.",
          );
      });
    return () => {
      active = false;
    };
  }, [runId, ready]);

  async function start(form: FormData) {
    setBusy(true);
    setLocalError("");
    try {
      const visitId = new URLSearchParams(window.location.search).get("visit");
      if (visitId) form.append("visit_id", visitId);
      const created = await createRun(form);
      setRunId(created.run_id);
      navigate(`/patient/records/${created.run_id}`);
    } catch (caught) {
      setLocalError(
        caught instanceof Error
          ? caught.message
          : t("The upload failed. Please try again."),
      );
    } finally {
      setBusy(false);
    }
  }
  async function onFile(file: File | undefined) {
    if (!file || busy) return;
    setBusy(true);
    setLocalError("");
    try {
      const form = new FormData();
      form.append("image", await prepareImage(file));
      await start(form);
    } catch (caught) {
      setLocalError(
        caught instanceof Error
          ? caught.message
          : t("This image could not be prepared. Choose another photo."),
      );
    } finally {
      setBusy(false);
    }
  }
  async function onConfirm() {
    if (!runId || busy) return;
    setBusy(true);
    setLocalError("");
    try {
      await confirmRun(runId);
    } catch (caught) {
      setLocalError(
        caught instanceof Error ? caught.message : "Confirmation failed",
      );
    } finally {
      setBusy(false);
    }
  }
  const published = summaries.filter(
    (n) =>
      n.status === "published" &&
      !summaries.some(
        (other) => other.status === "published" && other.amends_id === n.id,
      ),
  );
  return (
    <main className="workspace record-workspace">
      <div className="record-navigation">
      <button
        className="back-link"
        type="button"
        onClick={() => navigate(run?.visit_id ? `/patient/visits/${run.visit_id}` : "/patient/files")}
      >
        ← {t("My records")}
      </button>
      <PatientLanguageControl />
      </div>
      <header className="workspace-heading">
        <div className="workspace-title">
          <PixelWorkspaceIcon workspace="patient" size={40} />
          <div>
            <h1>{runId ? t("Your report") : t("Add a report")}</h1>
            <p>
              {run
                ? published.length
                  ? t("Doctor note published")
                  : message(recordStatus(run.status))
                : t("Upload a clear photo of your prescription or report.")}
            </p>
          </div>
        </div>
        {runId && (
          <button
            className="secondary"
            type="button"
            onClick={() => window.location.reload()}
          >{t("Refresh status")}</button>
        )}
      </header>
      {(localError || error) && (
        <p className="banner pii" role="alert">
          {message(localError || error)}
        </p>
      )}
      {summaryError && (
        <p className="banner pii" role="alert">
          {message(summaryError)}
        </p>
      )}
      {!runId && (
        <section className="upload-module">
          <PixelDocument size={42} />
          <h2>{t("Keep your report in one place")}</h2>
          <p>{t("A sharp, well-lit photo gives the best reading. Include the whole page.")}</p>
          <label className="upload-picker">{t("Report image")}<input
              className="file-input"
              aria-label={t("Report image")}
              type="file"
              accept="image/*"
              disabled={busy}
              onChange={(e) => void onFile(e.target.files?.[0])}
            />
            <span className="secondary file-picker-button">{t("Choose a photo")}</span>
          </label>
          <p className="module-help">{t("Your image is stored until you delete the record. Meta prepares a privacy preview first. You will review it before the redacted page is read.")}</p>
          {busy && <p role="status">{t("Preparing and uploading your report…")}</p>}
          {isDemo && (
            <details>
              <summary>{t("Explore fictional samples")}</summary>
              <div className="row-actions">
                {cases.map((item) => (
                  <button
                    key={item.id}
                    className="secondary"
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
            </details>
          )}
        </section>
      )}
      {runId && !run && !error && <p role="status">{t("Opening your report…")}</p>}
      {run && !ready && !waiting && (
        <p
          className={`banner ${["failed", "interrupted"].includes(run.status) ? "pii" : "review"}`}
          role="status"
        >
          {["failed", "interrupted"].includes(run.status)
            ? t("Processing did not finish. Return to My records and add the report again.")
            : (language === "en" ? events.at(-1)?.message : "") || t("Preparing your report. You can return to My records and reopen it later.")}
        </p>
      )}
      {ready && (
        <nav className="module-tabs" aria-label="Record sections">
          <button
            type="button"
            aria-current={tab === "notes" ? "page" : undefined}
            onClick={() => setTab("notes")}
          >
            <PixelVisit />{t("Doctor's notes")}</button>
          <button
            type="button"
            aria-current={tab === "reading" ? "page" : undefined}
            onClick={() => setTab("reading")}
          >
            <PixelPill />{t("Report reading")}</button>
          <button
            type="button"
            aria-current={tab === "source" ? "page" : undefined}
            onClick={() => setTab("source")}
          >
            <PixelDocument />{t("Image & recording")}</button>
        </nav>
      )}
      {run && (waiting || (ready && tab === "source")) && (
        <section className="source-module">
          <div className="source-image">
            <h2>
              {waiting ? t("Check the privacy preview") : t("Saved report image")}
            </h2>
            {imageUnavailable ? (
              <div className="banner review">
                <p>{t("The source preview is unavailable. Saved readings and notes are still available.")}</p>
                <button
                  className="secondary"
                  onClick={() => {
                    setImageUnavailable(false);
                    setImageLoaded(false);
                    setImageAttempt((i) => i + 1);
                  }}
                >{t("Retry image")}</button>
              </div>
            ) : (
              <div className="sheet">
                <img
                  key={imageAttempt}
                  src={`${apiBase}${waiting ? run.overlay_url : run.redacted_url}`}
                  alt={
                    waiting
                      ? t("Report with private regions marked in red")
                      : t("Redacted report")
                  }
                  onLoad={() => setImageLoaded(true)}
                  onError={() => {
                    setImageUnavailable(true);
                    setImageLoaded(false);
                  }}
                />
              </div>
            )}
          </div>
          <aside className="source-actions">
            {waiting ? (
              <>
                <h2>{t("Before processing")}</h2>
                <p>{t("Red marks hidden details. Make sure names, phone numbers and other identifiers are covered. Green marks the area to be read.")}</p>
                <button
                  className="primary"
                  disabled={busy || !imageLoaded || imageUnavailable}
                  onClick={() => void onConfirm()}
                >{t("Confirm privacy & continue")}</button>
              </>
            ) : (
              <>
                <h2>{t("Original files")}</h2>
                {run.original_available && (
                  <p>
                    <a
                      href={`${apiBase}/api/runs/${encodeURIComponent(run.run_id)}/files/original`}
                    >{t("Download original image")}</a>
                  </p>
                )}
                {run.audio_available && (
                  <>
                    <label htmlFor="patient-audio">{t("Doctor's recording")}</label>
                    <audio
                      id="patient-audio"
                      controls
                      preload="metadata"
                      src={`${apiBase}/api/runs/${encodeURIComponent(run.run_id)}/files/audio`}
                    />
                  </>
                )}
                {!run.original_available && !run.audio_available && (
                  <p>{t("No original files available for this record.")}</p>
                )}
              </>
            )}
          </aside>
        </section>
      )}
      {run && ready && tab === "reading" && (
        <section className="reading-module">
          <h2>{t("Report reading")}</h2>
          <p className="module-help">
            {run.replay
              ? t("Recorded reading of a fictional sample.")
              : t("Provisional AI reading. Handwriting may be misread or missing; check the source with your doctor.")}
          </p>
          {run.extraction ? (
            <div className="clinical-reading-grid">
              <section>
                <h3>{t("Medicines as written")}</h3>
                {run.extraction.medications.length ? (
                  <ul className="reading-list">
                    {run.extraction.medications.map((m, i) => (
                      <li key={i}>{m.raw_text}</li>
                    ))}
                  </ul>
                ) : (
                  <p>{t("No medicines extracted.")}</p>
                )}
              </section>
              <section>
                <h3>{t("Test results")}</h3>
                {run.extraction.rows.length ? (
                  <div className="table-scroll">
                    <table>
                      <thead>
                        <tr>
                          <th>{t("Name")}</th>
                          <th>{t("Value")}</th>
                          <th>{t("Unit")}</th>
                          <th>{t("Range")}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {run.extraction.rows.map((r, i) => (
                          <tr key={i}>
                            <td>{r.raw_name}</td>
                            <td>{r.value ?? r.value_text ?? t("Not recorded")}</td>
                            <td>{r.unit || "—"}</td>
                            <td>
                              {r.ref_low ?? ""}–{r.ref_high ?? ""}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p>{t("No test results extracted.")}</p>
                )}
                <h3>{t("Tests as written")}</h3>
                <ul>
                  {run.extraction.advised_tests.map((t, i) => (
                    <li key={i}>{t.raw_name}</li>
                  ))}
                </ul>
              </section>
            </div>
          ) : (
            <p>{t("No reading available. Check the original report.")}</p>
          )}
        </section>
      )}
      {ready && tab === "notes" && (
        <section className="note-module">
          <div className="module-heading">
            <div>
              <h2>{t("Your doctor's notes")}</h2>
              <p>{t("Reviewed and published by your connected doctor.")}</p>
            </div>
            {published.length > 0 && (
              <button className="secondary" onClick={() => window.print()}>{t("Print or save as PDF")}</button>
            )}
          </div>
          {published.length ? (
            published.map((note) => (
              <article className="published-note" key={note.id}>
                {note.prescription?.length ? <p>{t("Patient")}: {patientName}</p> : null}
                <PrescriptionTable medicines={note.prescription || []} />
                <p className="source-caption">
                  {note.author_name || t("Doctor")} ·{" "}
                  {new Date(
                    note.published_at || note.created_at,
                  ).toLocaleDateString(locale)}
                  {note.amends_id ? ` · ${t("Updated note")}` : ""}
                </p>
                <div className="note-languages">
                  <div>
                    <h3>English</h3>
                    <p className="doctor-summary">{note.summary_en}</p>
                  </div>
                  <div lang="bn">
                    <h3>বাংলা</h3>
                    <p className="doctor-summary">{note.summary_bn}</p>
                  </div>
                </div>
              </article>
            ))
          ) : (
            <div className="empty-inline">
              <p>{t("No published note yet. Your image reading remains provisional until reviewed by a doctor.")}</p>
              <button
                className="secondary"
                onClick={() => navigate("/patient?tab=doctors")}
              >{t("Manage doctor access")}</button>
            </div>
          )}
        </section>
      )}
    </main>
  );
}
