import { Moon, Sun, UserCircle } from "@phosphor-icons/react";
import { useCallback, useEffect, useState } from "react";

import { getSession, logout } from "./api";
import { AuthPage, AccountPage } from "./Auth";
import { DemoPage } from "./Demo";
import { Doctor } from "./Doctor";
import { Patient } from "./Patient";
import { Start } from "./Start";
import { navigate } from "./navigation";
import { useApp } from "./store";

export const DISCLAIMER = "MedEdge AI is an administrative data interoperability and optical ingestion pipeline, not a clinical decision or diagnostic tool.";

export function App() {
  const theme = useApp((state) => state.theme);
  const toggleTheme = useApp((state) => state.toggleTheme);
  const user = useApp((state) => state.user);
  const setUser = useApp((state) => state.setUser);
  const [path, setPath] = useState(window.location.pathname);
  const [checking, setChecking] = useState(true);
  const [connectionError, setConnectionError] = useState("");

  const bootstrap = useCallback(async () => {
    setChecking(true); setConnectionError("");
    try { setUser(await getSession()); }
    catch (error) { setConnectionError(error instanceof Error ? error.message : "The service is unavailable."); }
    finally { setChecking(false); }
  }, [setUser]);

  useEffect(() => { void bootstrap(); }, [bootstrap]);
  useEffect(() => {
    const onNavigation = () => setPath(window.location.pathname);
    window.addEventListener("popstate", onNavigation);
    return () => window.removeEventListener("popstate", onNavigation);
  }, []);
  useEffect(() => {
    if (checking || connectionError) return;
    if (["/patient", "/doctor", "/account"].includes(path) && !user) {
      const role = path === "/patient" || path === "/doctor" ? `?role=${path.slice(1)}` : "";
      navigate(`/signin${role}`, true);
    } else if ((path === "/patient" || path === "/doctor") && user && path !== `/${user.role}`) {
      navigate(`/${user.role}`, true);
    }
  }, [checking, connectionError, path, user]);

  async function signOut() {
    try { await logout(); setUser(null); navigate("/"); }
    catch (error) { setConnectionError(error instanceof Error ? error.message : "Sign out failed. Please try again."); }
  }
  const protectedPath = path === "/patient" || path === "/doctor" || path === "/account";
  return (
    <div className="app">
      <header className="topbar">
        <button className="wordmark" type="button" onClick={() => navigate("/")}>MedEdge<span className="wordmark-ai"> AI</span><span className="wordmark-dot" aria-hidden="true">.</span></button>
        <nav className="top-actions" aria-label="Account and appearance">
          {user ? <><button className="top-link account-link" onClick={() => navigate("/account")} type="button"><UserCircle size={19} /> <span>Account</span></button><button className="top-link" onClick={() => void signOut()} type="button">Sign out</button></> : <button className="top-link" onClick={() => navigate("/signin")} type="button">Sign in</button>}
          <button className="icon-button" type="button" onClick={toggleTheme} aria-label={theme === "dark" ? "Use light mode" : "Use dark mode"}>{theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}</button>
        </nav>
      </header>
      {checking ? <main className="stage loading-stage" aria-live="polite"><span className="loading-dot" /> Connecting to MedEdge…</main> : connectionError ? <main className="stage"><h1>We couldn’t connect.</h1><p className="lede">{connectionError}</p><button className="secondary" type="button" onClick={() => void bootstrap()}>Try again</button></main> :
        protectedPath && (!user || (path !== "/account" && path !== `/${user.role}`)) ? <main className="stage" aria-live="polite">Opening your workspace…</main> :
        path === "/patient" ? <Patient /> : path === "/doctor" ? <Doctor /> : path === "/account" ? <AccountPage /> : path === "/demo" ? <DemoPage /> : ["/signin", "/signup", "/verify-email", "/forgot-password", "/reset-password", "/check-email"].includes(path) ? <AuthPage key={path} path={path} /> : <Start />}
      <footer className="footer">{DISCLAIMER}</footer>
    </div>
  );
}
