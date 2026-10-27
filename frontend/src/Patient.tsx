import { useEffect, useState } from "react";
import QRCode from "qrcode";

import { apiBase, confirmRun, createRun, listCases, shareRun } from "./api";
import { useApp } from "./store";
import type { SampleCase } from "./types";
import { useRun } from "./useRun";

export function Patient() {
  const setScreen = useApp((state) => state.setScreen);
  const [runId, setRunId] = useState<string | null>(null);
  const [cases, setCases] = useState<SampleCase[]>([]);
  const [showSamples, setShowSamples] = useState(false);
  const [busy, setBusy] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const [code, setCode] = useState<string | null>(null);
  const [qr, setQr] = useState<string>("");
  const { run, events, error } = useRun(runId);

  useEffect(() => {
    void listCases()
      .then(setCases)
      .catch(() => setCases([]));
  }, []);

  useEffect(() => {
    if (!code) return;
    void QRCode.toString(code, { type: "svg", margin: 1, width: 180 }).then(setQr);
  }, [code]);

  async function start(form: FormData) {
    setBusy(true);
    setLocalError(null);
    setCode(null);
    try {
      const created = await createRun(form);
      setRunId(created.run_id);
    } catch (caught) {
      setLocalError(caught instanceof Error ? caught.message : "The upload failed");
    } finally {
      setBusy(false);
    }
  }

  async function onFile(file: File | undefined) {
    if (!file) return;
    const form = new FormData();
    form.append("image", file);
    await start(form);
  }

  async function onSample(id: string) {
    const form = new FormData();
    form.append("case_id", id);
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

  async function onShare() {
    if (!runId) return;
    setBusy(true);
    try {
      setCode(await shareRun(runId));
    } catch (caught) {
      setLocalError(caught instanceof Error ? caught.message : "Sharing failed");
    } finally {
      setBusy(false);
    }
  }

  const waiting = run?.status === "awaiting_confirmation";
  const ready = run?.status === "reviewing" || run?.status === "approved" || run?.status === "exported";
  const message = localError || error;

  return (
    <main className="stage">
      <button className="secondary" type="button" onClick={() => setScreen("start")}>
        Back
      </button>
      <h1 style={{ marginTop: 24 }}>Add a report</h1>
      <p className="lede">
        The name and phone lines are hidden on this machine. A language model sees the page only after you confirm the overlay.
      </p>

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
          {showSamples &&
            cases.map((item) => (
              <button key={item.id} className="secondary" type="button" disabled={busy} onClick={() => void onSample(item.id)}>
                {item.title}
              </button>
            ))}
        </div>
      )}

      {message && <p className="banner pii">{message}</p>}

      {run && waiting && (
        <div className="stack">
          <p className="lede">Red marks what will stay hidden. Green marks the table that will be read.</p>
          <div className="sheet">
            <img src={`${apiBase}${run.overlay_url}`} alt="Report with hidden regions marked in red" />
          </div>
          <button className="primary" type="button" disabled={busy} onClick={() => void onConfirm()}>
            This looks right
          </button>
        </div>
      )}

      {run && !waiting && !ready && <p className="lede">{events.at(-1)?.message ?? "Working through the page."}</p>}

      {run && ready && run.extraction && (
        <div className="stack">
          {run.replay && (
            <p className="banner review">Recorded reading of a fictional sample. No model was called for the values.</p>
          )}
          {run.extractor_model && <p className="lede">Read by {run.extractor_model}</p>}
          <p className="lede">Session {run.pseudonym}. Values are copied as printed.</p>
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
          <button className="primary" type="button" disabled={busy} onClick={() => void onShare()}>
            Share with a doctor
          </button>
          {code && (
            <div className="stack">
              <p className="code">{code}</p>
              <p className="lede">The code expires in 24 hours.</p>
              {qr && <div className="sheet" style={{ width: 196, padding: 8 }} dangerouslySetInnerHTML={{ __html: qr }} />}
            </div>
          )}
        </div>
      )}
    </main>
  );
}
