import { useEffect, useState } from "react";
import { apiBase, confirmRun, createRun, getChart, listCases } from "./api";
import { useApp } from "./store";
import type { ClinicalSummary, SampleCase } from "./types";
import { useRun } from "./useRun";
import { navigate } from "./navigation";
import { prepareImage } from "./image";
import { FhirView, TracePanel } from "./Trace";

export function Patient({ initialRunId = null }: { initialRunId?: string | null }) {
  const setScreen = useApp((state) => state.setScreen);
  const [runId, setRunId] = useState<string | null>(initialRunId);
  const [cases, setCases] = useState<SampleCase[]>([]);
  const [showSamples, setShowSamples] = useState(false);
  const [injectFault, setInjectFault] = useState(false);
  const [busy, setBusy] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const [summaries, setSummaries] = useState<ClinicalSummary[]>([]);
  const [summaryError, setSummaryError] = useState("");
  const [imageUnavailable, setImageUnavailable] = useState(false);
  const { run, events, error } = useRun(runId);

  useEffect(() => {
    void listCases()
      .then(setCases)
      .catch(() => setCases([]));
  }, []);

  useEffect(() => {
    if (!runId) return;
    let active = true;
    void getChart<{ summaries: ClinicalSummary[] }>(`/records/${encodeURIComponent(runId)}/summaries`)
      .then((result) => { if (active) { setSummaries(result.summaries); setSummaryError(""); } })
      .catch(() => { if (active) setSummaryError("Could not load your doctor’s notes. Refresh to try again."); });
    return () => { active = false; };
  }, [runId, run?.status]);

  async function start(form: FormData) {
    if (busy) return;
    setBusy(true);
    setLocalError(null);
    try {
      const created = await createRun(form);
      setRunId(created.run_id);
      navigate(`/patient/records/${created.run_id}`);
    } catch (caught) {
      setLocalError(caught instanceof Error ? caught.message : "The upload failed");
    } finally {
      setBusy(false);
    }
  }

  async function onFile(file: File | undefined) {
    if (!file || busy) return;
    setBusy(true);
    const form = new FormData();
    form.append("image", await prepareImage(file));
    setBusy(false);
    await start(form);
  }

  async function onSample(id: string) {
    const form = new FormData();
    form.append("case_id", id);
    if (injectFault) form.append("inject_fault", "true");
    await start(form);
  }

  async function onConfirm() {
    if (!runId) return;
    setBusy(true);
    try {
      await confirmRun(runId);
    } catch (caught) {
      setLocalError(caught instanceof Error ? caught.message : "Confirmation failed");
    } finally {
      setBusy(false);
    }
  }

  const waiting = run?.status === "awaiting_confirmation";
  const ready = run?.status === "reviewing" || run?.status === "approved" || run?.status === "exported";
  const message = localError || error;

  return (
    <main className="stage">
      <button className="secondary" type="button" onClick={() => initialRunId ? navigate("/patient") : setScreen("patient")}>
        Back to my records
      </button>
      <h1 style={{ marginTop: 24 }}>{runId ? "Your report" : "Add a report"}</h1>
      {!runId && <p className="lede">
        Your image is sent to Meta to locate page regions. Review the redaction preview before the redacted page is sent for reading.
      </p>}

      {!runId && (
        <div className="stack">
          <label className="primary">
            Choose a photo
            <input
              className="file-input"
              type="file"
              accept="image/*"
              capture="environment"
              onChange={(event) => void onFile(event.target.files?.[0])}
            />
          </label>
          <button className="secondary" type="button" onClick={() => setShowSamples((open) => !open)}>
            Use a fictional sample
          </button>
          {showSamples && (
            <label className="check">
              <input type="checkbox" checked={injectFault} onChange={(event) => setInjectFault(event.target.checked)} />
              Inject a fault to show the agent repairing its own bundle
            </label>
          )}
          {showSamples &&
            cases.map((item) => (
              <button key={item.id} className="secondary" type="button" disabled={busy} onClick={() => void onSample(item.id)}>
                {item.title}
              </button>
            ))}
        </div>
      )}

      {message && <p className="banner pii">{message}</p>}
      {summaryError && <p className="banner pii" role="alert">{summaryError}</p>}

      {run && waiting && (
        <div className="stack">
          <p className="lede">Green marks the area that will be read; red marks what will stay hidden. Check that every name, phone number, and other private detail is covered in red; go back if anything is visible.</p>
          <div className="sheet">
            <img src={`${apiBase}${run.overlay_url}`} alt="Report with hidden regions marked in red" />
          </div>
          <button className="primary" type="button" disabled={busy} onClick={() => void onConfirm()}>
            This looks right
          </button>
        </div>
      )}

      {run && !waiting && !ready && <><p className="lede" role="status">{events.at(-1)?.message ?? "Working through the page."}</p><TracePanel run={run} live={events} /></>}

      {run && ready && run.extraction && (
        <div className="stack">
          <section className="source-preview"><h2>Source preview</h2>
            {imageUnavailable ? <p className="lede">Source image unavailable. Your saved reading remains below.</p> : <img src={`${apiBase}${run.redacted_url}`} alt="Redacted source report" onError={() => setImageUnavailable(true)} />}
          </section>
          {run.replay && (
            <p className="banner review">Recorded reading of a fictional sample. No model was called for the values.</p>
          )}
          {run.extractor_model && <p className="lede">Read by {run.extractor_model}</p>}
          <p className="lede">Session {run.pseudonym}. {run.replay ? "Fictional recorded reading." : "AI-extracted reading; review against the source."}</p>
          <table>
            <thead>
              <tr>
                <th>Printed name</th>
                <th>Value</th>
                <th>Unit</th>
                <th>Range</th>
              </tr>
            </thead>
            <tbody>
              {run.extraction.rows.map((row) => (
                <tr key={row.raw_name}>
                  <td>{row.raw_name}</td>
                  <td>{row.value ?? row.value_text ?? ""}</td>
                  <td>{row.unit ?? ""}</td>
                  <td>
                    {row.ref_low ?? ""}–{row.ref_high ?? ""}
                  </td>
                </tr>
              ))}
              {run.extraction.medications.map((item) => (
                <tr key={item.raw_text}>
                  <td colSpan={4}>{item.raw_text}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {run.extraction.advised_tests.length > 0 && (
            <section aria-label="Advised tests">
              <h2>Tests as written</h2>
              <ul>{run.extraction.advised_tests.map((test, index) => <li key={`${test.raw_name}-${index}`}>{test.raw_name}</li>)}</ul>
            </section>
          )}
          {!run.replay && <p className="banner review">AI readings can miss or misread details. Check the original with a clinician before using this result.</p>}
          <TracePanel run={run} live={events} />
          <FhirView bundle={run.bundle} />
          {summaries.filter(item => item.status === "published").map(item => <article className="published-note" key={item.id}>
            <p className="chart-eyebrow">DOCTOR’S DICTATED NOTE</p><h2>{item.amends_id ? "Updated note from your doctor" : "Your doctor’s dictated note"}</h2>
            <p className="lede">{item.author_name || "Doctor"} · {new Date(item.published_at || item.created_at).toLocaleDateString()} · Doctor account is self-declared · Spoken by the doctor, transcribed and translated by Muse Voice and Muse Spark, reviewed and published by the doctor</p>
            <h3>English version</h3><p className="note-text">{item.summary_en}</p><h3 lang="bn">বাংলা সংস্করণ</h3><p className="note-text" lang="bn">{item.summary_bn}</p>
            <button className="secondary" type="button" onClick={() => window.print()}>Print or save as PDF</button>
          </article>)}
          <button className="primary" type="button" disabled={busy} onClick={() => navigate("/patient")}>
            Manage doctor access
          </button>
        </div>
      )}
    </main>
  );
}
