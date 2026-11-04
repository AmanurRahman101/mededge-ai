import { useRef, useState } from "react";
import { getChart, post, remove } from "../api";
import { PatientChart } from "../Chart";
import { CurrentMedicines } from "../CurrentMedicines";
import { navigate } from "../navigation";
import { usePatientLanguage } from "../patientLanguage";
import {
  PixelDocument,
  PixelPill,
  PixelVisit,
  PixelWorkspaceIcon,
} from "../PixelIcons";
import { NewPrescription } from "../PrescriptionWorkspace";
import { useApp } from "../store";
import { CareShell, useCareText, useLocation } from "./CareShell";
import { HealthSummary } from "./HealthSummary";
import { ReportSubmission } from "./ReportSubmission";
import type { Visit } from "./types";
import { useResource } from "./useResource";
import "./care.css";

type Connection = {
  patient_id: string | null;
  name: string;
  email: string;
  status: string;
  patient_summary?: string;
  latest_note_preview?: string;
  request_id: string;
};
function ErrorState({ error, retry }: { error: string; retry: () => void }) {
  const { message } = usePatientLanguage();
  const { text } = useCareText();
  return (
    <div className="care-error" role="alert">
      <p>{message(error)}</p>
      <button type="button" className="secondary" onClick={retry}>
        {text("Try again", "আবার চেষ্টা করুন")}
      </button>
    </div>
  );
}
export function VisitRows({ visits }: { visits: Visit[] }) {
  const role = useApp((state) => state.user?.role);
  const { text, locale } = useCareText();
  return (
    <div className="care-visit-list">
      {visits.map((visit) => (
        <button
          type="button"
          className="care-list-row"
          key={visit.id}
          onClick={() => navigate(`/${role}/visits/${visit.id}`)}
        >
          <span className="care-row-icon">
            <PixelVisit size={24} />
          </span>
          <span className="care-row-copy">
            <strong>
              {visit.title === "Consultation"
                ? text("Doctor visit", "ডাক্তার দেখানো")
                : visit.title}
            </strong>
            <span>
              {role === "patient" ? visit.doctor_name : visit.patient_name} ·{" "}
              {new Date(visit.created_at).toLocaleDateString(locale, {
                day: "numeric",
                month: "short",
                year: "numeric",
              })}
            </span>
          </span>
          <span className={`care-status ${visit.status}`}>
            {visit.status === "open"
              ? text("In progress", "চলছে")
              : text("Completed", "সম্পন্ন")}
          </span>
          <span aria-hidden="true">→</span>
        </button>
      ))}
    </div>
  );
}
function VisitsPage({
  patientId,
  home = false,
}: {
  patientId?: string;
  home?: boolean;
}) {
  const [offset, setOffset] = useState(0);
  const { data, error, loading, reload } = useResource<{
    visits: Visit[];
    has_more: boolean;
  }>(
    `/api/visits?${new URLSearchParams({ ...(patientId ? { patient_id: patientId } : {}), offset: String(offset), limit: home ? "3" : "20" })}`,
  );
  const { text } = useCareText();
  return (
    <section className="care-section">
      <div className="care-section-heading">
        <h2>
          {home
            ? text("Recent visits", "সাম্প্রতিক ডাক্তার দেখানো")
            : text("Visits", "ডাক্তার দেখানো")}
        </h2>
        <button
          type="button"
          className="text-link"
          disabled={loading}
          onClick={() => void reload()}
        >
          {text("Refresh", "আবার দেখুন")}
        </button>
      </div>
      {error ? (
        <ErrorState error={error} retry={() => void reload()} />
      ) : loading ? (
        <p role="status">{text("Loading visits…", "তথ্য আসছে…")}</p>
      ) : !data?.visits.length ? (
        <div className="care-empty">
          <PixelVisit size={36} />
          <h3>{text("No visits yet", "এখনো কোনো সাক্ষাৎ নেই")}</h3>
          <p>
            {text(
              "Visits appear here when your doctor starts a consultation.",
              "ডাক্তার নতুন সাক্ষাৎ শুরু করলে এখানে দেখা যাবে।",
            )}
          </p>
        </div>
      ) : (
        <VisitRows visits={data.visits} />
      )}
      {!home && (offset > 0 || data?.has_more) && (
        <div className="care-pagination">
          <button
            type="button"
            className="secondary"
            disabled={!offset || loading}
            onClick={() => setOffset((value) => Math.max(0, value - 20))}
          >
            {text("Previous", "আগের পাতা")}
          </button>
          <span>{offset / 20 + 1}</span>
          <button
            type="button"
            className="secondary"
            disabled={!data?.has_more || loading}
            onClick={() => setOffset((value) => value + 20)}
          >
            {text("Next", "পরের পাতা")}
          </button>
        </div>
      )}
    </section>
  );
}

function DoctorPatients() {
  const { data, loading, error, reload } = useResource<{
    connections: Connection[];
  }>("/api/chart/connections");
  const [search, setSearch] = useState("");
  const patients =
    data?.connections.filter(
      (c) =>
        c.status === "approved" &&
        `${c.name} ${c.email}`.toLowerCase().includes(search.toLowerCase()),
    ) || [];
  return (
    <CareShell
      title="Patients"
      subtitle="Choose a patient to view their health and visits."
      actions={
        <button
          className="primary"
          type="button"
          onClick={() => navigate("/doctor/connections")}
        >
          Connect patient
        </button>
      }
    >
      <label className="care-search">
        Find a patient
        <input
          type="search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Name or email"
        />
      </label>
      {error ? (
        <ErrorState error={error} retry={() => void reload()} />
      ) : loading ? (
        <p role="status">Loading patients…</p>
      ) : patients.length ? (
        <div className="care-patient-list">
          {patients.map((patient) => (
            <button
              className="care-patient-row"
              key={patient.patient_id}
              type="button"
              onClick={() => navigate(`/doctor/patients/${patient.patient_id}`)}
            >
              <PixelWorkspaceIcon workspace="patient" size={32} />
              <span>
                <strong>{patient.name}</strong>
                <span>
                  {patient.patient_summary ||
                    patient.latest_note_preview ||
                    "No reviewed history yet"}
                </span>
              </span>
              <span className="care-open-label">Open patient →</span>
            </button>
          ))}
        </div>
      ) : (
        <div className="care-empty">
          <PixelWorkspaceIcon workspace="patient" size={42} />
          <h2>
            {search ? "No matching patients" : "Your patients will appear here"}
          </h2>
          <p>
            {search
              ? "Try another name or clear your search."
              : "Request access with their code. They decide whether to share their chart."}
          </p>
        </div>
      )}
    </CareShell>
  );
}

function DoctorPatient({ patientId }: { patientId: string }) {
  const { data, loading, error, reload } = useResource<{
    connections: Connection[];
  }>("/api/chart/connections");
  const patient = data?.connections.find(
    (c) => c.patient_id === patientId && c.status === "approved",
  );
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState("");
  const key = useRef(crypto.randomUUID());
  const [earlier, setEarlier] = useState<
    { run_id: string; title: string; created_at: string }[] | null
  >(null);
  const [earlierError, setEarlierError] = useState("");
  async function start() {
    setBusy(true);
    setActionError("");
    try {
      const visit = await post<Visit>("/api/visits", {
        patient_id: patientId,
        title: "Consultation",
        idempotency_key: key.current,
      });
      navigate(`/doctor/visits/${visit.id}`);
    } catch (error) {
      setActionError(
        error instanceof Error ? error.message : "Could not start the visit.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <CareShell
      title={patient?.name || "Patient"}
      back={{ label: "All patients", path: "/doctor" }}
      actions={
        patient && (
          <button
            className="primary"
            type="button"
            disabled={busy}
            onClick={() => void start()}
          >
            {busy ? "Opening visit…" : "Start visit"}
          </button>
        )
      }
    >
      {loading ? (
        <p role="status">Opening patient…</p>
      ) : error || !patient ? (
        <ErrorState
          error={error || "This chart is unavailable. Return to your patients."}
          retry={() => void reload()}
        />
      ) : (
        <>
          {actionError && (
            <p className="care-error" role="alert">
              {actionError}
            </p>
          )}
          {(data?.connections.filter(
            (connection) => connection.status === "approved",
          ).length || 0) > 1 && (
            <label className="care-search">
              Switch patient
              <select
                value={patientId}
                onChange={(event) =>
                  navigate(`/doctor/patients/${event.target.value}`)
                }
              >
                {data?.connections
                  .filter((connection) => connection.status === "approved")
                  .map((connection) => (
                    <option
                      key={connection.patient_id}
                      value={connection.patient_id || ""}
                    >
                      {connection.name}
                    </option>
                  ))}
              </select>
            </label>
          )}
          <HealthSummary patientId={patientId} />
          <CurrentMedicines patientId={patientId} editable={false} />
          <VisitsPage patientId={patientId} />
          <details className="care-access-settings">
            <summary>Sharing settings</summary>
            <p>Disconnecting ends your access to this patient’s chart.</p>
            <button
              type="button"
              className="secondary"
              disabled={busy}
              onClick={() => {
                if (
                  window.confirm(
                    "Disconnect from this patient? Your published notes remain in their history.",
                  )
                ) {
                  setBusy(true);
                  void post(`/api/chart/connections/${patientId}/revoke`)
                    .then(() => navigate("/doctor"))
                    .catch((error) => setActionError(error.message))
                    .finally(() => setBusy(false));
                }
              }}
            >
              Disconnect patient
            </button>
          </details>
          <section className="care-section care-earlier">
            <div className="care-section-heading">
              <h2>Earlier records</h2>
              <button
                type="button"
                className="secondary"
                onClick={() => {
                  setEarlierError("");
                  void getChart<{ records: NonNullable<typeof earlier> }>(
                    `/records?patient_id=${patientId}&include_source=false&earlier=true`,
                  )
                    .then((result) => setEarlier(result.records))
                    .catch((error) => setEarlierError(error.message));
                }}
              >
                Browse earlier records
              </button>
            </div>
            <p className="care-help">
              Saved before visits were introduced. Dates and doctors have not
              been guessed.
            </p>
            {earlierError && <p role="alert">{earlierError}</p>}
            {earlier?.map((record) => (
              <button
                type="button"
                className="care-list-row"
                key={record.run_id}
                onClick={() => navigate(`/doctor/records/${record.run_id}`)}
              >
                <PixelDocument size={22} />
                <span>{record.title}</span>
                <span>
                  {new Date(record.created_at).toLocaleDateString("en-GB")}
                </span>
                <span aria-hidden="true">→</span>
              </button>
            ))}
            {earlier?.length === 0 && <p>No earlier records.</p>}
          </section>
        </>
      )}
    </CareShell>
  );
}

function DoctorConnections() {
  const { data, error, reload } = useResource<{ connections: Connection[] }>(
    "/api/chart/connections",
  );
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  return (
    <CareShell
      title="Connect a patient"
      subtitle="Ask the patient for their six-character sharing code."
    >
      <form
        className="care-connect"
        onSubmit={async (event) => {
          event.preventDefault();
          setBusy(true);
          setNotice("");
          try {
            await post("/api/chart/requests", { code });
            setCode("");
            setNotice(
              "Request sent. The patient must approve before you can open their chart.",
            );
            await reload();
          } catch (error) {
            setNotice(
              error instanceof Error ? error.message : "Please try again.",
            );
          } finally {
            setBusy(false);
          }
        }}
      >
        <label>
          Patient code
          <input
            autoComplete="off"
            value={code}
            maxLength={6}
            onChange={(event) => setCode(event.target.value.toUpperCase())}
            placeholder="ABC234"
          />
        </label>
        <button className="primary" disabled={busy || code.trim().length !== 6}>
          {busy ? "Sending…" : "Request access"}
        </button>
      </form>
      <p className="care-help">
        Patients see your account name and email. Doctor credentials are
        self-declared.
      </p>
      {notice && (
        <p role="status" className="care-notice">
          {notice}
        </p>
      )}
      {error && <ErrorState error={error} retry={() => void reload()} />}
      {data?.connections
        .filter((c) => c.status === "pending")
        .map((connection) => (
          <div className="care-list-row" key={connection.request_id}>
            <span>Waiting for patient approval</span>
            <button
              type="button"
              className="secondary"
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                try {
                  await post(
                    `/api/chart/requests/${connection.request_id}/cancel`,
                  );
                  await reload();
                } catch (error) {
                  setNotice(
                    error instanceof Error
                      ? error.message
                      : "Please try again.",
                  );
                } finally {
                  setBusy(false);
                }
              }}
            >
              Cancel request
            </button>
          </div>
        ))}
    </CareShell>
  );
}

function VisitDetail({ id }: { id: string }) {
  const {
    data: visit,
    loading,
    error,
    reload,
  } = useResource<Visit>(`/api/visits/${id}`);
  const user = useApp((state) => state.user)!;
  const { text, locale } = useCareText();
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState("");
  const key = useRef(crypto.randomUUID());
  const [addingReport, setAddingReport] = useState(false);
  const [reports, setReports] = useState<{ run_id: string; title: string }[]>(
    [],
  );
  const [selectedReport, setSelectedReport] = useState("");
  const doctor = user.role === "doctor";
  const back = {
    label: doctor ? "Patient" : text("Visits", "ডাক্তার দেখানো"),
    path:
      doctor && visit
        ? `/doctor/patients/${visit.patient_id}`
        : `/${user.role}/visits`,
  };
  async function action(operation: () => Promise<void>) {
    setBusy(true);
    setActionError("");
    try {
      await operation();
    } catch (error) {
      setActionError(
        error instanceof Error ? error.message : "Please try again.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <CareShell
      title={
        visit?.title === "Consultation"
          ? text("Doctor visit", "ডাক্তার দেখানো")
          : visit?.title || text("Visit", "সাক্ষাৎ")
      }
      subtitle={
        visit
          ? `${doctor ? visit.patient_name : visit.doctor_name} · ${new Date(visit.created_at).toLocaleDateString(locale, { day: "numeric", month: "short", year: "numeric" })}`
          : undefined
      }
      back={back}
    >
      {error ? (
        <ErrorState error={error} retry={() => void reload()} />
      ) : loading ? (
        <p role="status">{text("Opening visit…", "সাক্ষাৎ খোলা হচ্ছে…")}</p>
      ) : (
        visit && (
          <>
            <div className="care-visit-heading">
              <span className={`care-status ${visit.status}`}>
                {visit.status === "open"
                  ? text("In progress", "চলছে")
                  : text("Completed", "সম্পন্ন")}
              </span>
              <span>{visit.doctor_name}</span>
              {visit.doctor_id !== user.id && doctor && (
                <span>Shared history · Read only</span>
              )}
            </div>
            {!doctor && visit.status === "open" && (
              <button
                type="button"
                className="primary"
                onClick={() => navigate(`/patient/upload?visit=${id}`)}
              >
                {text(
                  "Add report to this visit",
                  "এই সাক্ষাতে রিপোর্ট যোগ করুন",
                )}
              </button>
            )}
            {actionError && (
              <p role="alert" className="care-error">
                {actionError}
              </p>
            )}
            {visit.can_edit && (
              <div className="care-visit-actions">
                <button
                  type="button"
                  className="primary"
                  disabled={busy}
                  onClick={() => navigate(`/doctor/visits/${id}/prescription`)}
                >
                  <PixelPill size={20} /> New prescription
                </button>
                <button
                  type="button"
                  className="secondary"
                  disabled={busy}
                  onClick={() => navigate(`/doctor/visits/${id}/report`)}
                >
                  <PixelDocument size={20} /> Report & voice
                </button>
                <button
                  type="button"
                  className="secondary"
                  disabled={busy}
                  onClick={() =>
                    void action(async () => {
                      const result = await post<{ run_id: string }>(
                        `/api/visits/${id}/notes`,
                        { idempotency_key: key.current },
                      );
                      navigate(`/doctor/records/${result.run_id}`);
                    })
                  }
                >
                  Write note
                </button>
              </div>
            )}
            <section className="care-section">
              <div className="care-section-heading">
                <h2>{text("In this visit", "এই সাক্ষাতের তথ্য")}</h2>
                <button
                  type="button"
                  className="text-link"
                  onClick={() => void reload()}
                >
                  {text("Refresh", "আবার দেখুন")}
                </button>
              </div>
              {!visit.records?.length ? (
                <div className="care-empty">
                  <PixelDocument size={36} />
                  <h3>{text("This visit is ready", "সাক্ষাৎ শুরু হয়েছে")}</h3>
                  <p>
                    {doctor
                      ? "Add a prescription, report or note. Everything for this consultation stays here."
                      : "Your doctor’s prescriptions, reports and notes will appear here."}
                  </p>
                </div>
              ) : (
                <div>
                  {visit.records.map((record) => (
                    <div className="care-artifact-row" key={record.run_id}>
                      <button
                        type="button"
                        className="care-list-row"
                        onClick={() =>
                          navigate(`/${user.role}/records/${record.run_id}`)
                        }
                      >
                        <span className="care-row-icon">
                          {record.input_mode.includes("prescription") ? (
                            <PixelPill size={24} />
                          ) : (
                            <PixelDocument size={24} />
                          )}
                        </span>
                        <span className="care-row-copy">
                          <strong>{record.title}</strong>
                          <span>
                            {record.reference
                              ? text(
                                  "Earlier report used in this visit",
                                  "এই সাক্ষাতে ব্যবহার করা আগের রিপোর্ট",
                                )
                              : record.has_published_note
                                ? text(
                                    "Reviewed by doctor",
                                    "ডাক্তার যাচাই করেছেন",
                                  )
                                : text(
                                    "Not published yet",
                                    "এখনো প্রকাশ করা হয়নি",
                                  )}
                          </span>
                        </span>
                        <span aria-hidden="true">→</span>
                      </button>
                      {visit.can_edit &&
                        !record.reference &&
                        !record.has_published_note &&
                        ![
                          "queued",
                          "processing",
                          "awaiting_confirmation",
                        ].includes(record.status) && (
                          <button
                            type="button"
                            className="text-link"
                            disabled={busy}
                            onClick={() => {
                              if (
                                window.confirm(
                                  "Discard this unpublished draft and its source files?",
                                )
                              )
                                void action(async () => {
                                  await remove(
                                    `/api/visits/${id}/drafts/${record.run_id}`,
                                  );
                                  await reload();
                                });
                            }}
                          >
                            Discard draft
                          </button>
                        )}
                    </div>
                  ))}
                </div>
              )}
            </section>
            {visit.can_edit && (
              <section className="care-visit-finish">
                <button
                  type="button"
                  className="text-link"
                  disabled={busy}
                  onClick={() =>
                    void action(async () => {
                      setAddingReport((value) => !value);
                      const result = await getChart<{
                        records: typeof reports;
                      }>(
                        `/records?patient_id=${visit.patient_id}&include_source=false`,
                      );
                      setReports(
                        result.records.filter(
                          (record) =>
                            !visit.records?.some(
                              (item) => item.run_id === record.run_id,
                            ),
                        ),
                      );
                    })
                  }
                >
                  Use an existing report
                </button>
                {addingReport && (
                  <form
                    className="care-attach"
                    onSubmit={(event) => {
                      event.preventDefault();
                      void action(async () => {
                        await post(`/api/visits/${id}/reports`, {
                          run_id: selectedReport,
                        });
                        setAddingReport(false);
                        setSelectedReport("");
                        await reload();
                      });
                    }}
                  >
                    <label>
                      Saved report
                      <select
                        value={selectedReport}
                        onChange={(event) =>
                          setSelectedReport(event.target.value)
                        }
                      >
                        <option value="">Choose a report</option>
                        {reports.map((record) => (
                          <option key={record.run_id} value={record.run_id}>
                            {record.title}
                          </option>
                        ))}
                      </select>
                    </label>
                    <button
                      className="secondary"
                      disabled={busy || !selectedReport}
                    >
                      Add to visit
                    </button>
                  </form>
                )}
                <div className="care-section-heading">
                  <div>
                    <h2>Finish this visit</h2>
                    <p className="care-help">
                      Published information stays in the patient’s history.
                    </p>
                  </div>
                  <button
                    type="button"
                    className="secondary"
                    disabled={busy || !!visit.completion_checks?.length}
                    onClick={() => {
                      if (
                        window.confirm(
                          "Complete this visit? New information will belong to a new visit.",
                        )
                      )
                        void action(async () => {
                          await post(`/api/visits/${id}/complete`, {
                            expected_revision: visit.revision,
                          });
                          await reload();
                        });
                    }}
                  >
                    Complete visit
                  </button>
                </div>
                {!visit.records?.length && (
                  <button
                    type="button"
                    className="text-link"
                    disabled={busy}
                    onClick={() => {
                      if (window.confirm("Discard this empty visit?"))
                        void action(async () => {
                          await remove(`/api/visits/${id}`);
                          navigate(`/doctor/patients/${visit.patient_id}`);
                        });
                    }}
                  >
                    Discard empty visit
                  </button>
                )}
                {!!visit.completion_checks?.length && (
                  <ul className="care-completion-checks">
                    {visit.completion_checks.map((check) => (
                      <li key={check}>{check}</li>
                    ))}
                  </ul>
                )}
              </section>
            )}
          </>
        )
      )}
    </CareShell>
  );
}

function NewVisitContent({ id, report }: { id: string; report: boolean }) {
  const { data, error, loading, reload } = useResource<Visit>(
    `/api/visits/${id}`,
  );
  const [locked, setLocked] = useState(false);
  return (
    <CareShell
      title={report ? "Report & voice note" : "New prescription"}
      subtitle={data?.patient_name}
      back={{ label: "Visit", path: `/doctor/visits/${id}` }}
    >
      {error ? (
        <ErrorState error={error} retry={() => void reload()} />
      ) : loading ? (
        <p role="status">Opening visit…</p>
      ) : data?.can_edit ? (
        report ? (
          <ReportSubmission visit={data} />
        ) : (
          <NewPrescription
            patientId={data.patient_id}
            visitId={id}
            isDemo={useApp.getState().user?.id === "demo-doctor"}
            onLockChange={setLocked}
          />
        )
      ) : (
        <p>This visit is unavailable for new contributions.</p>
      )}
      {locked && (
        <p className="care-help">
          Your recording stays in this tab until you submit it.
        </p>
      )}
    </CareShell>
  );
}

export function CarePortal() {
  const user = useApp((state) => state.user)!;
  const location = useLocation();
  const path = location.split("?")[0];
  const parts = path.split("/");
  const { text } = useCareText();
  if (user.role === "doctor") {
    if (parts[2] === "patients" && parts[3])
      return <DoctorPatient key={parts[3]} patientId={parts[3]} />;
    if (parts[2] === "visits" && parts[3])
      return parts[4] ? (
        <NewVisitContent
          key={path}
          id={parts[3]}
          report={parts[4] === "report"}
        />
      ) : (
        <VisitDetail key={path} id={parts[3]} />
      );
    if (parts[2] === "visits")
      return (
        <CareShell
          title="Visits"
          subtitle="Your consultations, together in one place."
        >
          <VisitsPage />
        </CareShell>
      );
    if (parts[2] === "connections") return <DoctorConnections />;
    return <DoctorPatients />;
  }
  if (parts[2] === "visits" && parts[3])
    return <VisitDetail key={path} id={parts[3]} />;
  if (parts[2] === "visits")
    return (
      <CareShell title={text("Visits", "ডাক্তার দেখানো")}>
        <VisitsPage />
      </CareShell>
    );
  if (parts[2] === "doctors" || parts[2] === "activity")
    return (
      <CareShell title={text("My doctors", "আমার ডাক্তার")}>
        <PatientChart embedded />
      </CareShell>
    );
  if (parts[2] === "files")
    return (
      <CareShell
        title={text("Reports", "রিপোর্ট")}
        subtitle={text(
          "Your saved reports and prescriptions.",
          "আপনার সেভ করা রিপোর্ট ও প্রেসক্রিপশন।",
        )}
        actions={
          <button
            type="button"
            className="primary"
            onClick={() => navigate("/patient/upload")}
          >
            {text("Add report", "রিপোর্ট যোগ করুন")}
          </button>
        }
      >
        <PatientChart embedded />
      </CareShell>
    );
  if (parts[2] === "health")
    return (
      <CareShell
        title={text("My health", "আমার স্বাস্থ্য")}
        back={{ label: text("Home", "মূল পাতা"), path: "/patient" }}
      >
        <HealthSummary patientId={user.id} />
        <CurrentMedicines patientId={user.id} editable />
      </CareShell>
    );
  return (
    <CareShell
      title={user.full_name}
      subtitle={text(
        "Your health, in one place.",
        "আপনার স্বাস্থ্যের সব তথ্য এক জায়গায়।",
      )}
      actions={
        <button
          type="button"
          className="primary"
          onClick={() => navigate("/patient/upload")}
        >
          {text("Add report", "রিপোর্ট যোগ করুন")}
        </button>
      }
    >
      <HealthSummary patientId={user.id} compact />
      <button
        type="button"
        className="text-link"
        onClick={() => navigate("/patient/health")}
      >
        {text("My health & medicines", "আমার স্বাস্থ্য ও ওষুধ")} →
      </button>
      <VisitsPage home />
      <button
        className="secondary"
        type="button"
        onClick={() => navigate("/patient/visits")}
      >
        {text("All visits", "সব সাক্ষাৎ")}
      </button>
    </CareShell>
  );
}
