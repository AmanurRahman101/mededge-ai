import { ArrowRight, Plus } from "@phosphor-icons/react";
import {
  PixelDocument as ClipboardText,
  PixelShield as ShieldCheck,
  PixelVisit as Users,
  PixelVitals,
  PixelWorkspaceIcon,
} from "./PixelIcons";
import { ChartOverview, recordStatus } from "./ChartOverview";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { deleteChart, getChart, post, updateChart } from "./api";
import { navigate } from "./navigation";
import { useApp } from "./store";

type RecordItem = {
  run_id: string;
  has_published_note: boolean;
  title: string;
  status: string;
  document_type: string | null;
  created_at: string;
};
type Connection = {
  doctor_id: string;
  patient_id: string | null;
  status: string;
  name: string | null;
  email: string | null;
};
type Activity = {
  id: string;
  action: string;
  occurred_at: string;
  run_id: string | null;
};
const activityText: Record<string, string> = {
  connection_requested: "Doctor requested access",
  connection_approved: "Doctor access approved",
  connection_declined: "Doctor request declined",
  connection_revoked: "Doctor access ended",
  record_updated: "Record updated",
  record_deleted: "Record deleted",
  summary_published: "Doctor published a note",
};

type PatientTab = "records" | "doctors" | "activity" | "summary" | "history";
function currentTab(): PatientTab {
  const value = new URLSearchParams(window.location.search).get("tab");
  return value === "doctors" || value === "activity" || value === "summary" || value === "history"
    ? value
    : "records";
}
function RecordMenu({ children }: { children: ReactNode }) {
  const menu = useRef<HTMLDetailsElement>(null);
  useEffect(() => {
    function onPointer(event: PointerEvent) {
      if (menu.current?.open && !menu.current.contains(event.target as Node))
        menu.current.open = false;
    }
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape" && menu.current?.open) {
        menu.current.open = false;
        menu.current.querySelector("summary")?.focus();
        event.preventDefault();
      }
    }
    document.addEventListener("pointerdown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, []);
  return (
    <details ref={menu} className="record-manage">
      <summary>Manage</summary>
      <div
        onClick={(event) => {
          if ((event.target as HTMLElement).closest("button") && menu.current)
            menu.current.open = false;
        }}
      >
        {children}
      </div>
    </details>
  );
}

export function PatientChart() {
  const user = useApp((state) => state.user);
  const [tab, setTab] = useState<PatientTab>(currentTab);
  useEffect(() => {
    const sync = () => setTab(currentTab());
    window.addEventListener("popstate", sync);
    return () => window.removeEventListener("popstate", sync);
  }, []);
  function selectTab(next: PatientTab) {
    if (next === tab && currentTab() === next) return;
    navigate(next === "records" ? "/patient" : `/patient?tab=${next}`);
  }
  const [records, setRecords] = useState<RecordItem[]>([]);
  const [connections, setConnections] = useState<Connection[]>([]);
  const [activity, setActivity] = useState<Activity[]>([]);
  const [olderActivity, setOlderActivity] = useState(false);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("");
  const [status, setStatus] = useState("");
  const [archived, setArchived] = useState(false);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [code, setCode] = useState("");
  const [consentVersion, setConsentVersion] = useState("");
  const [consentText, setConsentText] = useState("");
  const [accept, setAccept] = useState<Record<string, boolean>>({});
  const [editing, setEditing] = useState("");
  const [title, setTitle] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);

  const requestSequence = useRef(0);
  const loadRecords = useCallback(async () => {
    const sequence = ++requestSequence.current;
    setLoading(true);
    try {
      const query = new URLSearchParams({
        archived: String(archived),
        include_source: "false",
        search,
        offset: String(offset),
        limit: "20",
      });
      if (filter) query.set("document_type", filter);
      if (status) query.set("status", status);
      const data = await getChart<{ records: RecordItem[]; has_more: boolean }>(
        `/records?${query}`,
      );
      if (sequence === requestSequence.current) {
        setRecords(data.records);
        setHasMore(data.has_more);
      }
    } catch (e) {
      if (sequence === requestSequence.current)
        setError(
          e instanceof Error ? e.message : "Could not load your records.",
        );
    } finally {
      if (sequence === requestSequence.current) setLoading(false);
    }
  }, [search, archived, filter, status, offset]);
  const loadConnections = useCallback(async () => {
    const people = await getChart<{
      connections: Connection[];
      consent_version: string;
      consent_text: string;
    }>("/connections");
    setConnections(people.connections);
    setConsentVersion(people.consent_version);
    setConsentText(people.consent_text);
  }, []);
  const loadActivity = useCallback(async () => {
    const log = await getChart<{ activity: Activity[] }>("/activity");
    setActivity(log.activity);
  }, []);
  useEffect(() => {
    const timer = window.setTimeout(() => void loadRecords(), 250);
    return () => {
      window.clearTimeout(timer);
      requestSequence.current++;
    };
  }, [loadRecords]);
  useEffect(() => {
    void loadConnections().catch((e) =>
      setError(
        e instanceof Error ? e.message : "Could not load your care team.",
      ),
    );
  }, [loadConnections]);
  useEffect(() => {
    if (tab === "activity")
      void loadActivity().catch((e) =>
        setError(e instanceof Error ? e.message : "Could not load activity."),
      );
  }, [tab, loadActivity]);

  async function action(fn: () => Promise<unknown>) {
    setBusy(true);
    setError("");
    try {
      await fn();
      if (tab === "records") await loadRecords();
      else if (tab === "doctors") await loadConnections();
      else await loadActivity();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Please try again.");
    } finally {
      setBusy(false);
    }
  }
  function setQuery(value: string) {
    setSearch(value);
    setOffset(0);
  }
  return (
    <main className="workspace patient-workspace">
      <header className="workspace-heading">
        <div className="workspace-title">
          <PixelWorkspaceIcon workspace="patient" size={42} />
          <div>
            <h1>My health</h1>
            <p>{user?.full_name} · Your health information</p>
          </div>
        </div>
        <button
          className="primary"
          type="button"
          onClick={() => navigate("/patient/upload")}
        >
          <Plus size={17} /> Add a report
        </button>
      </header>
      <nav className="module-tabs" aria-label="Patient chart">
        <button
          type="button"
          aria-current={(tab === "records" || tab === "history") ? "page" : undefined}
          onClick={() => selectTab("records")}
        >
          <ClipboardText size={18} /> My records
        </button>
        <button
          type="button"
          aria-current={tab === "doctors" ? "page" : undefined}
          onClick={() => selectTab("doctors")}
        >
          <Users size={18} /> My doctors{" "}
          {connections.some((c) => c.status === "pending") && (
            <span className="chart-dot" aria-label="Pending requests" />
          )}
        </button>
        <button
          type="button"
          aria-current={tab === "summary" ? "page" : undefined}
          onClick={() => selectTab("summary")}
        >
          <PixelVitals size={18} /> My summary
        </button>
      </nav>
      {error && (
        <p className="banner pii" role="alert">
          {error}
        </p>
      )}
      {tab === "summary" && user ? (
        <ChartOverview patientId={user.id} role="patient" />
      ) : tab === "history" && user ? (
        <ChartOverview patientId={user.id} role="patient" detailsOnly />
      ) : tab === "records" ? (
        <section className="chart-section">
          <div className="chart-heading">
            <div>
              <h2>Your reports</h2>
              <p className="lede">Choose a report to open it.</p>
            </div>
            <button
              className="secondary"
              type="button"
              onClick={() => void loadRecords()}
              disabled={loading}
            >
              Refresh
            </button>
          </div>
          <div className="patient-search-tools">
            <div className="chart-filters">
              <label>
                Find a report
                <input
                  type="search"
                  value={search}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Search your records"
                />
              </label>
              <details className="patient-tools"><summary>Filter reports</summary><div className="advanced-report-filters">
              <label>
                Type
                <select
                  value={filter}
                  onChange={(e) => {
                    setFilter(e.target.value);
                    setOffset(0);
                  }}
                >
                  <option value="">All types</option>
                  <option value="prescription">Prescription</option>
                  <option value="lab_report">Lab report</option>
                  <option value="mixed">Mixed</option>
                  <option value="other">Other</option>
                </select>
              </label>
              <label>
                Status
                <select
                  value={status}
                  onChange={(e) => {
                    setStatus(e.target.value);
                    setOffset(0);
                  }}
                >
                  <option value="">All statuses</option>
                  <option value="reviewing">Ready for review</option>
                  <option value="approved">Approved</option>
                  <option value="failed">Failed</option>
                  <option value="interrupted">Interrupted</option>
                </select>
              </label>
              <label className="check">
                <input
                  type="checkbox"
                  checked={archived}
                  onChange={(e) => {
                    setArchived(e.target.checked);
                    setOffset(0);
                  }}
                />{" "}
                Show archived reports
              </label>
              </div></details>
            </div>
          </div>
          <button className="text-link" type="button" onClick={() => selectTab("history")}>Detailed history</button>
          {loading ? (
            <p className="lede" role="status">
              Loading records…
            </p>
          ) : records.length === 0 ? (
            <div className="chart-empty">
              <ClipboardText size={25} />
              <h3>{archived ? "No archived records" : "No records found"}</h3>
              <p>Upload a report or adjust your search to get started.</p>
            </div>
          ) : (
            <div className="record-list">
              {records.map((item) => (
                <article className="record-row" key={item.run_id}>
                  <div className="record-icon">
                    <ClipboardText size={22} />
                  </div>
                  <div className="record-main">
                    {editing === item.run_id ? (
                      <form
                        onSubmit={(e) => {
                          e.preventDefault();
                          void action(async () => {
                            await updateChart(`/records/${item.run_id}`, {
                              title,
                            });
                            setEditing("");
                          });
                        }}
                      >
                        <label>
                          Record title
                          <input
                            value={title}
                            maxLength={120}
                            onChange={(e) => setTitle(e.target.value)}
                            required
                          />
                        </label>
                        <button className="secondary" disabled={busy}>
                          Save
                        </button>
                        <button
                          className="text-link"
                          type="button"
                          onClick={() => setEditing("")}
                        >
                          Cancel
                        </button>
                      </form>
                    ) : (
                      <>
                        <h3>
                          {item.title === "Report"
                            ? item.document_type === "prescription"
                              ? "Prescription"
                              : "Medical report"
                            : item.title}
                        </h3>
                        <p>
                          {new Date(item.created_at).toLocaleDateString(
                            "en-GB",
                            { day: "numeric", month: "short", year: "numeric" },
                          )}{" "}
                          ·
                          {item.has_published_note
                            ? "Doctor’s note ready"
                            : item.status === "reviewing"
                              ? "Not yet checked by a doctor"
                              : recordStatus(item.status)}
                        </p>
                      </>
                    )}
                  </div>
                  <div className="record-actions">
                    <RecordMenu>
                      <button
                        className="text-link"
                        type="button"
                        onClick={() => {
                          setEditing(item.run_id);
                          setTitle(item.title);
                        }}
                      >
                        Rename
                      </button>
                      <button
                        className="text-link"
                        type="button"
                        disabled={busy}
                        onClick={() =>
                          void action(() =>
                            updateChart(`/records/${item.run_id}`, {
                              archived: !archived,
                            }),
                          )
                        }
                      >
                        {archived ? "Restore" : "Archive"}
                      </button>
                      <button
                        className="text-link danger-link"
                        type="button"
                        disabled={busy}
                        onClick={() => {
                          if (
                            window.confirm(
                              `Permanently delete “${item.title}” and its notes? This cannot be undone.`,
                            )
                          )
                            void action(() =>
                              deleteChart(`/records/${item.run_id}`),
                            );
                        }}
                      >
                        Delete
                      </button>
                    </RecordMenu>
                    <button
                      className="record-open"
                      type="button"
                      aria-label={`Open ${item.title}`}
                      onClick={() =>
                        navigate(`/patient/records/${item.run_id}`)
                      }
                    >
                      Open report <ArrowRight size={20} />
                    </button>
                  </div>
                </article>
              ))}
            </div>
          )}
          {(offset > 0 || hasMore) && (
            <div className="row-actions chart-pages">
              <button
                className="secondary"
                type="button"
                disabled={offset === 0 || loading}
                onClick={() => setOffset(Math.max(0, offset - 20))}
              >
                Previous
              </button>
              <span>Page {Math.floor(offset / 20) + 1}</span>
              <button
                className="secondary"
                type="button"
                disabled={!hasMore || loading}
                onClick={() => setOffset(offset + 20)}
              >
                Next
              </button>
            </div>
          )}
        </section>
      ) : tab === "doctors" ? (
        <section className="chart-section">
          <div className="chart-heading">
            <div>
              <h2>My doctors</h2>
              <p className="lede">
                You decide which doctors can see your reports.
              </p>
              <button
                className="text-link"
                type="button"
                onClick={() =>
                  void loadConnections().catch((e) =>
                    setError(
                      e instanceof Error
                        ? e.message
                        : "Could not load your care team.",
                    ),
                  )
                }
              >
                Check for requests
              </button>
            </div>
            <button
              className="secondary"
              type="button"
              disabled={busy}
              onClick={() =>
                void action(async () => {
                  const value = await post<{ code: string }>(
                    "/api/chart/connection-code",
                  );
                  setCode(value.code);
                })
              }
            >
              Share with a doctor
            </button>
          </div>
          {code && (
            <div className="connection-code">
              <div>
                <span>ONE-TIME CODE · VALID FOR 20 MINUTES</span>
                <strong>{code}</strong>
              </div>
              <p>
                Give this code to your doctor. They can request access, but
                cannot see your chart until you approve.
              </p>
            </div>
          )}
          {connections.length === 0 && (
            <div className="chart-empty">
              <Users size={25} />
              <h3>No connections yet</h3>
              <p>Create a code when you’re ready to connect with a doctor.</p>
            </div>
          )}
          {connections.map((c) => (
            <article className="connection-card" key={c.doctor_id}>
              <div>
                <h3>{c.name || "Doctor"}</h3>
                <p>
                  {c.status === "approved"
                    ? "Can see your reports"
                    : c.status === "pending"
                      ? "Wants to see your reports"
                      : "Cannot see your reports"}
                </p>
                <details>
                  <summary>Doctor details</summary>
                  <p>{c.email}</p>
                  <p>
                    Professional qualifications have not been checked by
                    MedEdge.
                  </p>
                </details>
              </div>
              {c.status === "pending" && (
                <div className="consent-details">
                  <p>{consentText}</p>
                  <label className="check">
                    <input
                      type="checkbox"
                      checked={!!accept[c.doctor_id]}
                      onChange={(e) =>
                        setAccept({
                          ...accept,
                          [c.doctor_id]: e.target.checked,
                        })
                      }
                    />
                    I understand what this doctor can see and do.
                  </label>
                  <div className="row-actions">
                    <button
                      className="primary"
                      type="button"
                      disabled={
                        busy ||
                        !accept[c.doctor_id] ||
                        !consentVersion ||
                        !consentText
                      }
                      onClick={() =>
                        void action(() =>
                          post(
                            `/api/chart/connections/${c.doctor_id}/decision`,
                            { approve: true, consent_version: consentVersion },
                          ),
                        )
                      }
                    >
                      Allow this doctor
                    </button>
                    <button
                      className="secondary"
                      type="button"
                      disabled={busy}
                      onClick={() =>
                        void action(() =>
                          post(
                            `/api/chart/connections/${c.doctor_id}/decision`,
                            { approve: false },
                          ),
                        )
                      }
                    >
                      Do not allow
                    </button>
                  </div>
                </div>
              )}
              {c.status === "approved" && (
                <button
                  className="secondary"
                  type="button"
                  disabled={busy}
                  onClick={() => {
                    if (
                      window.confirm(
                        `Stop sharing your reports with ${c.name || "this doctor"}?`,
                      )
                    )
                      void action(() =>
                        post(`/api/chart/connections/${c.doctor_id}/revoke`),
                      );
                  }}
                >
                  Stop sharing
                </button>
              )}
            </article>
          ))}
        </section>
      ) : (
        <section className="chart-section">
          <div className="chart-heading">
            <div>
              <h2>Recent changes</h2>
              <p className="lede">Changes to your reports and doctor access.</p>
            </div>
            <button
              className="secondary"
              type="button"
              onClick={() =>
                void loadActivity().catch((e) =>
                  setError(
                    e instanceof Error ? e.message : "Could not load activity.",
                  ),
                )
              }
            >
              Refresh
            </button>
          </div>
          {activity.length === 0 ? (
            <div className="chart-empty">
              <ShieldCheck size={25} />
              <h3>No activity yet</h3>
              <p>Changes to your chart will appear here.</p>
            </div>
          ) : (
            <ol className="activity-list">
              {activity
                .filter((entry) => entry.action !== "summary_amendment_started")
                .slice(0, olderActivity ? undefined : 5)
                .map((entry) => (
                  <li key={entry.id}>
                    <strong>
                      {activityText[entry.action] || "Your record was updated"}
                    </strong>
                    <time>{new Date(entry.occurred_at).toLocaleString()}</time>
                    {entry.run_id && (
                      <button
                        className="text-link"
                        type="button"
                        onClick={() =>
                          navigate(`/patient/records/${entry.run_id}`)
                        }
                      >
                        Open record
                      </button>
                    )}
                  </li>
                ))}
            </ol>
          )}
          {activity.filter(entry => entry.action !== "summary_amendment_started").length > 5 && <button className="secondary" type="button" onClick={() => setOlderActivity(value => !value)}>{olderActivity ? "Show fewer changes" : "Show older changes"}</button>}
        </section>
      )}

    </main>
  );
}
