import { useCallback, useEffect, useRef, useState } from "react";
import { getChart, post } from "./api";
import { navigate } from "./navigation";
import {
  PixelDocument,
  PixelPill,
  PixelFlask,
  PixelVisit,
  PixelVitals,
} from "./PixelIcons";

type Note = {
  id: string;
  summary_en: string;
  summary_bn: string;
  author_name: string;
  published_at: string | null;
};
type Entry = {
  run_id: string;
  title: string;
  created_at: string;
  status: string;
  archived: boolean;
  medications: string[];
  tests: string[];
  results: {
    raw_name?: string;
    value?: number | null;
    value_text?: string | null;
    unit?: string | null;
  }[];
  notes: Note[];
};
type Snapshot = {
  records: Entry[];
  record_count: number;
  published_note_count: number;
};
type Digest = {
  status: string;
  updated_at: string | null;
  items: {
    category: string;
    text_en: string;
    text_bn: string;
    source_ids: string[];
  }[];
};
export function recordStatus(status: string) {
  return (
    (
      {
        queued: "Preparing preview",
        awaiting_confirmation: "Check privacy",
        processing: "Processing",
        reviewing: "Ready to review",
        approved: "Reviewed",
        exported: "Reviewed",
        failed: "Needs retry",
        interrupted: "Interrupted",
      } as Record<string, string>
    )[status] || status.replaceAll("_", " ")
  );
}
export function ChartOverview({
  patientId,
  role,
}: {
  patientId: string;
  role: "doctor" | "patient";
}) {
  const [data, setData] = useState<Snapshot | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [digest, setDigest] = useState<Digest | null>(null);
  const [digestLoading, setDigestLoading] = useState(false);
  const [language, setLanguage] = useState<"en" | "bn">("en");
  const sequence = useRef(0);
  const refresh = useCallback(
    async (retry = false) => {
      const id = ++sequence.current;
      setLoading(true);
      setError("");
      setDigest(null);
      try {
        const snapshot = await getChart<Snapshot>(
          `/patients/${encodeURIComponent(patientId)}/summary`,
        );
        if (id !== sequence.current) return;
        setData(snapshot);
        if (snapshot.published_note_count) {
          setDigestLoading(true);
          void post<Digest>(
            `/api/chart/patients/${encodeURIComponent(patientId)}/summary${retry ? "?retry=true" : ""}`,
          )
            .then((result) => {
              if (id === sequence.current)
                setDigest(
                  result.items.every((item) =>
                    item.source_ids.every((sourceId) =>
                      snapshot.records.some((record) =>
                        record.notes.some((note) => note.id === sourceId),
                      ),
                    ),
                  )
                    ? result
                    : { status: "changed", items: [], updated_at: null },
                );
            })
            .catch(() => {
              if (id === sequence.current)
                setDigest({ status: "failed", items: [], updated_at: null });
            })
            .finally(() => {
              if (id === sequence.current) setDigestLoading(false);
            });
        } else setDigestLoading(false);
      } catch (caught) {
        if (id === sequence.current) {
          setData(null);
          setError(
            caught instanceof Error
              ? caught.message
              : "Could not load the patient overview.",
          );
        }
      } finally {
        if (id === sequence.current) setLoading(false);
      }
    },
    [patientId],
  );
  useEffect(() => {
    setData(null);
    void refresh();
    const focus = () => {
      void refresh();
    };
    window.addEventListener("focus", focus);
    return () => {
      sequence.current++;
      window.removeEventListener("focus", focus);
    };
  }, [refresh]);
  const source = (entry: Entry) => (
    <button
      className="text-link"
      type="button"
      onClick={() => navigate(`/${role}/records/${entry.run_id}`)}
    >
      {entry.title} · {new Date(entry.created_at).toLocaleDateString()}
    </button>
  );
  return (
    <section className="patient-overview" aria-label="Patient summary">
      <div className="module-heading">
        <div>
          <h2>Patient summary</h2>
          <p>
            All saved history, including archived reports. Updated from the
            latest saved entries.
          </p>
        </div>
        <button
          className="secondary"
          type="button"
          disabled={loading}
          onClick={() => void refresh()}
        >
          {loading ? "Updating…" : "Refresh"}
        </button>
      </div>
      {error && (
        <p className="banner pii" role="alert">
          {error}
        </p>
      )}
      {loading && !data && <p role="status">Loading the full history…</p>}
      {data && (
        <>
          <p className="overview-caption">
            {data.record_count} {data.record_count === 1 ? "report" : "reports"}{" "}
            · {data.published_note_count} published{" "}
            {data.published_note_count === 1 ? "note" : "notes"}. This covers
            records saved in MedEdge.
          </p>
          <section className="verified-digest">
            <div className="module-heading">
              <div>
                <h3>
                  <PixelVisit size={22} /> Verified history at a glance
                </h3>
                <p className="module-help">
                  Automatically summarized from doctor-published notes. Links
                  identify the source of each item.
                </p>
              </div>
              <div className="segmented" aria-label="Summary language">
                <button
                  type="button"
                  aria-pressed={language === "en"}
                  onClick={() => setLanguage("en")}
                >
                  English
                </button>
                <button
                  type="button"
                  aria-pressed={language === "bn"}
                  onClick={() => setLanguage("bn")}
                >
                  বাংলা
                </button>
              </div>
            </div>
            {digestLoading && (
              <p role="status">
                Updating the patient-wide summary… Saved notes remain available
                below.
              </p>
            )}
            {!data.published_note_count && (
              <p className="empty-inline">
                No doctor-verified notes yet. A summary will appear after a
                doctor publishes a note.
              </p>
            )}
            {digest?.status === "ready" && digest.items.length > 0 && (
              <div className="digest-sections">
                {["assessment", "medicines", "tests", "care"].map(
                  (category) => {
                    const items = digest.items.filter(
                      (i) => i.category === category,
                    );
                    return (
                      items.length > 0 && (
                        <section key={category}>
                          <h4>
                            {
                              (
                                {
                                  assessment: "Conditions & assessments",
                                  medicines: "Medication history",
                                  tests: "Tests & findings",
                                  care: "Care & follow-up",
                                } as Record<string, string>
                              )[category]
                            }
                          </h4>
                          <ul>
                            {items.map((item, i) => (
                              <li key={i}>
                                <p lang={language}>
                                  {language === "en"
                                    ? item.text_en
                                    : item.text_bn}
                                </p>
                                <div className="source-links">
                                  {item.source_ids.map((id) => {
                                    const entry = data.records.find((r) =>
                                      r.notes.some((n) => n.id === id),
                                    );
                                    return entry ? (
                                      <span key={id}>{source(entry)}</span>
                                    ) : null;
                                  })}
                                </div>
                              </li>
                            ))}
                          </ul>
                        </section>
                      )
                    );
                  },
                )}
              </div>
            )}
            {digest &&
              (digest.status !== "ready" || !digest.items.length) &&
              data.published_note_count > 0 && (
                <p className="empty-inline">
                  The combined summary is unavailable. Open the published source
                  notes below to read the verified history.
                </p>
              )}
            {digest?.status === "failed" && (
              <button
                className="secondary"
                type="button"
                disabled={digestLoading}
                onClick={() => void refresh(true)}
              >
                Retry automatic summary
              </button>
            )}
            {digest?.updated_at && digest.status === "ready" && (
              <p className="overview-caption">
                Updated {new Date(digest.updated_at).toLocaleString()}
              </p>
            )}
          </section>
          <details className="overview-clinical">
            <summary>
              Read published source notes ({data.published_note_count})
            </summary>
            <div className="module-heading">
              <h3>
                <PixelVisit size={22} /> Assessment & care history
              </h3>
              <div className="segmented" aria-label="Note language">
                <button
                  type="button"
                  aria-pressed={language === "en"}
                  onClick={() => setLanguage("en")}
                >
                  English
                </button>
                <button
                  type="button"
                  aria-pressed={language === "bn"}
                  onClick={() => setLanguage("bn")}
                >
                  বাংলা
                </button>
              </div>
            </div>
            <p className="module-help">
              Doctor-published notes, including diagnoses and assessments
              documented there. The latest published version of each note is
              shown.
            </p>
            {data.published_note_count === 0 ? (
              <p className="empty-inline">
                No doctor-published assessment yet. Unreviewed readings are
                listed below.
              </p>
            ) : (
              data.records.flatMap((entry) =>
                entry.notes.map((note) => (
                  <article className="overview-note" key={note.id}>
                    <div className="source-caption">
                      <strong>{note.author_name}</strong>
                      <span>
                        {note.published_at
                          ? new Date(note.published_at).toLocaleDateString()
                          : "Published"}
                      </span>
                      {source(entry)}
                    </div>
                    <p lang={language} className="doctor-summary">
                      {language === "en" ? note.summary_en : note.summary_bn}
                    </p>
                  </article>
                )),
              )
            )}
          </details>
          <details className="overview-provisional">
            <summary>Unreviewed image readings</summary>
            <div className="overview-readings">
              <section>
                <h3>
                  <PixelPill size={22} /> Medicines mentioned
                </h3>
                <p className="module-help">
                  As extracted from dated reports; these may be inaccurate or no
                  longer current.
                </p>
                {data.records.some((r) => r.medications.length) ? (
                  data.records
                    .filter((r) => r.medications.length)
                    .map((entry) => (
                      <div className="overview-reading" key={entry.run_id}>
                        {source(entry)}
                        <ul>
                          {entry.medications.map((m, i) => (
                            <li key={i}>{m}</li>
                          ))}
                        </ul>
                      </div>
                    ))
                ) : (
                  <p className="empty-inline">No medicines extracted.</p>
                )}
              </section>
              <section>
                <h3>
                  <PixelFlask size={22} /> Tests & results
                </h3>
                <p className="module-help">
                  Provisional readings and tests advised in saved reports.
                </p>
                {data.records.some(
                  (r) => r.tests.length || r.results.length,
                ) ? (
                  data.records
                    .filter((r) => r.tests.length || r.results.length)
                    .map((entry) => (
                      <div className="overview-reading" key={entry.run_id}>
                        {source(entry)}
                        <ul>
                          {entry.tests.map((t, i) => (
                            <li key={`t${i}`}>{t} · Advised</li>
                          ))}
                          {entry.results.map((r, i) => (
                            <li key={`r${i}`}>
                              <PixelVitals size={14} /> {r.raw_name}:{" "}
                              {r.value ?? r.value_text ?? "Not recorded"}{" "}
                              {r.unit || ""}
                            </li>
                          ))}
                        </ul>
                      </div>
                    ))
                ) : (
                  <p className="empty-inline">No tests or results extracted.</p>
                )}
              </section>
            </div>
          </details>
          <details className="overview-history">
            <summary>Browse source reports ({data.record_count})</summary>
            <h3>
              <PixelDocument size={22} /> Reports at a glance
            </h3>
            {data.records.length ? (
              data.records.map((entry) => (
                <div className="overview-report" key={entry.run_id}>
                  {source(entry)}
                  <span className="status-label">
                    {recordStatus(entry.status)}
                    {entry.archived ? " · Archived" : ""}
                  </span>
                </div>
              ))
            ) : (
              <p className="empty-inline">No reports have been saved yet.</p>
            )}
          </details>
        </>
      )}
    </section>
  );
}
