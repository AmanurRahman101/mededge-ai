import { useEffect, useState } from "react";
import { getChart, post } from "../api";
import { usePatientLanguage } from "../patientLanguage";
import { useCareText } from "./CareShell";

export function HealthSummary({
  patientId,
  compact = false,
}: {
  patientId: string;
  compact?: boolean;
}) {
  const [summary, setSummary] = useState<{
    status: string;
    narrative_en?: string;
    narrative_bn?: string;
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [retry, setRetry] = useState(0);
  const { language } = usePatientLanguage();
  const [doctorLanguage, setDoctorLanguage] = useState<"en" | "bn">("en");
  const { text } = useCareText();
  const patient = window.location.pathname.startsWith("/patient");
  const displayLanguage = patient ? language : doctorLanguage;
  useEffect(() => {
    let active = true;
    setLoading(true);
    setSummary(null);
    void getChart<{ published_note_count: number }>(
      `/patients/${encodeURIComponent(patientId)}/summary`,
    )
      .then(async (result) =>
        result.published_note_count
          ? post<typeof summary>(
              `/api/chart/patients/${encodeURIComponent(patientId)}/summary${retry ? "?retry=true" : ""}`,
            )
          : { status: "empty" },
      )
      .then((result) => {
        if (active) setSummary(result);
      })
      .catch(() => {
        if (active) setSummary({ status: "failed" });
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [patientId, retry]);
  return (
    <section
      className={`care-health${compact ? " care-health-compact" : ""}`}
      aria-label={text("Health summary", "স্বাস্থ্যের সারাংশ")}
    >
      <div className="care-section-heading">
        <h2>{text("Health summary", "স্বাস্থ্যের সারাংশ")}</h2>
        {!patient && (
          <div className="segmented" role="group" aria-label="Summary language">
            <button
              type="button"
              aria-pressed={doctorLanguage === "en"}
              onClick={() => setDoctorLanguage("en")}
            >
              English
            </button>
            <button
              type="button"
              aria-pressed={doctorLanguage === "bn"}
              onClick={() => setDoctorLanguage("bn")}
            >
              বাংলা
            </button>
          </div>
        )}
      </div>
      {loading ? (
        <p role="status">{text("Loading health summary…", "সারাংশ আসছে…")}</p>
      ) : summary?.status === "ready" ? (
        <p className="care-narrative" lang={displayLanguage}>
          {displayLanguage === "bn"
            ? summary.narrative_bn
            : summary.narrative_en}
        </p>
      ) : summary?.status === "empty" ? (
        <p className="care-empty-inline">
          {text(
            "A health summary will appear after a doctor publishes your first visit note.",
            "ডাক্তার প্রথম নোট দিলে এখানে স্বাস্থ্যের সারাংশ দেখা যাবে।",
          )}
        </p>
      ) : (
        <div>
          <p>
            {text(
              "The summary is unavailable. Your saved visit notes are still available.",
              "এখন সারাংশ পাওয়া যাচ্ছে না। সেভ করা নোট দেখতে পারবেন।",
            )}
          </p>
          <button
            type="button"
            className="secondary"
            onClick={() => setRetry((value) => value + 1)}
          >
            {text("Try again", "আবার চেষ্টা করুন")}
          </button>
        </div>
      )}
    </section>
  );
}
