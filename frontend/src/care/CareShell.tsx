import { useEffect, useState, type ReactNode } from "react";
import { navigate } from "../navigation";
import { PatientLanguageControl, usePatientLanguage } from "../patientLanguage";
import {
  PixelWorkspaceIcon,
  PixelDocument,
  PixelVisit,
  PixelVitals,
} from "../PixelIcons";
import { useApp } from "../store";

export function useLocation() {
  const [location, setLocation] = useState(
    window.location.pathname + window.location.search,
  );
  useEffect(() => {
    const sync = () =>
      setLocation(window.location.pathname + window.location.search);
    window.addEventListener("popstate", sync);
    return () => window.removeEventListener("popstate", sync);
  }, []);
  return location;
}
export function useCareText() {
  const { language, locale } = usePatientLanguage();
  return {
    locale,
    text: (english: string, bangla: string) =>
      language === "bn" ? bangla : english,
  };
}
export function CareShell({
  title,
  subtitle,
  children,
  actions,
  back,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
  actions?: ReactNode;
  back?: { label: string; path: string };
}) {
  const user = useApp((state) => state.user)!;
  const location = useLocation();
  const { text } = useCareText();
  const patient = user.role === "patient";
  const links = patient
    ? [
        {
          path: "/patient",
          label: text("Home", "মূল পাতা"),
          icon: PixelWorkspaceIcon,
        },
        {
          path: "/patient/visits",
          label: text("Visits", "ডাক্তার দেখানো"),
          icon: PixelVisit,
        },
        {
          path: "/patient/files",
          label: text("Reports", "রিপোর্ট"),
          icon: PixelDocument,
        },
        {
          path: "/patient/doctors",
          label: text("Doctors", "ডাক্তার"),
          icon: PixelVitals,
        },
      ]
    : [
        { path: "/doctor", label: "Patients", icon: PixelWorkspaceIcon },
        { path: "/doctor/visits", label: "Visits", icon: PixelVisit },
        {
          path: "/doctor/connections",
          label: "Connect patient",
          icon: PixelVitals,
        },
      ];
  return (
    <div className="care-shell">
      <aside className="care-navigation">
        <div className="care-role">
          <PixelWorkspaceIcon workspace={user.role} size={28} />
          <span>
            {patient ? text("My health", "আমার স্বাস্থ্য") : "My practice"}
          </span>
        </div>
        <nav aria-label={patient ? "Patient navigation" : "Doctor navigation"}>
          {links.map((link) => (
            <button
              type="button"
              key={link.path}
              aria-current={
                location.split("?")[0] === link.path ||
                (!patient &&
                  link.path === "/doctor" &&
                  location.includes("/doctor/patients/"))
                  ? "page"
                  : undefined
              }
              onClick={() => navigate(link.path)}
            >
              <link.icon workspace={patient ? "patient" : "doctor"} size={20} />
              <span>{link.label}</span>
            </button>
          ))}
        </nav>
        <p className="care-signed-in">{user.full_name}</p>
      </aside>
      <main className="care-main">
        <div className="care-toolbar">
          {back ? (
            <button
              type="button"
              className="back-link"
              onClick={() => navigate(back.path)}
            >
              ← {back.label}
            </button>
          ) : (
            <span />
          )}
          {patient && <PatientLanguageControl />}
        </div>
        <header className="care-heading">
          <div>
            <h1>{title}</h1>
            {subtitle && <p>{subtitle}</p>}
          </div>
          {actions && <div className="care-actions">{actions}</div>}
        </header>
        {children}
      </main>
    </div>
  );
}
