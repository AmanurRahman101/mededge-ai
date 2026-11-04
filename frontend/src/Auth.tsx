import { ArrowLeft, ArrowRight, Eye, EyeSlash } from "@phosphor-icons/react";
import { useEffect, useState, type FormEvent, type ReactNode } from "react";

import { ApiError, changePassword, forgotPassword, getDemoAccounts, type DemoAccounts, login, logout, register, resendVerification, resetPassword, setCsrfToken, verifyEmail, type UserRole } from "./api";
import { navigate } from "./navigation";
import { useApp } from "./store";

function LinkButton({ to, children, className = "text-link" }: { to: string; children: ReactNode; className?: string }) {
  return <button type="button" className={className} onClick={() => navigate(to)}>{children}</button>;
}

function PasswordField({ label, value, onChange, autoComplete, hint }: { label: string; value: string; onChange: (value: string) => void; autoComplete: "current-password" | "new-password"; hint?: string }) {
  const [visible, setVisible] = useState(false);
  const id = label.toLowerCase().replace(/\s+/g, "-");
  return <div className="auth-field"><label htmlFor={id}>{label}</label><div className="password-input"><input id={id} type={visible ? "text" : "password"} autoComplete={autoComplete} value={value} onChange={(event) => onChange(event.target.value)} required maxLength={128} minLength={autoComplete === "new-password" ? 12 : undefined} aria-describedby={hint ? `${id}-hint` : undefined} /><button type="button" className="password-toggle" onClick={() => setVisible(!visible)} aria-label={`${visible ? "Hide" : "Show"} ${label.toLowerCase()}`} aria-pressed={visible}>{visible ? <EyeSlash size={19} /> : <Eye size={19} />}</button></div>{hint && <small id={`${id}-hint`}>{hint}</small>}</div>;
}

function EmailField({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  return <div className="auth-field"><label htmlFor="email">Email address</label><input id="email" type="email" autoComplete="email" inputMode="email" value={value} onChange={(event) => onChange(event.target.value)} placeholder="you@example.com" required maxLength={254} /></div>;
}

function AuthShell({ children }: { children: ReactNode }) {
  return <main className="auth-layout"><section className="auth-content">{children}</section></main>;
}

const errorText = (error: unknown) => error instanceof Error ? error.message : "Something went wrong. Please try again.";

export function AuthPage({ path }: { path: string }) {
  const setUser = useApp((state) => state.setUser);
  const [role, setRole] = useState<UserRole>(() => new URLSearchParams(window.location.search).get("role") === "doctor" ? "doctor" : "patient");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [remember, setRemember] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);
  const [cooldown, setCooldown] = useState(0);
  const [demoAccounts, setDemoAccounts] = useState<DemoAccounts | null>(null);
  const [token] = useState(() => new URLSearchParams(window.location.hash.slice(1)).get("token") ?? "");

  useEffect(() => { if (path === "/signin") void getDemoAccounts().then(setDemoAccounts).catch(() => setDemoAccounts(null)); }, [path]);
  useEffect(() => { if (window.location.hash) window.history.replaceState(window.history.state, "", `${window.location.pathname}${window.location.search}`); }, []);
  useEffect(() => { if (!cooldown) return; const timer = window.setTimeout(() => setCooldown((value) => value - 1), 1000); return () => window.clearTimeout(timer); }, [cooldown]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError("");
    if ((path === "/signup" || path === "/reset-password") && password !== confirm) { setError("The passwords don’t match. Please check and try again."); return; }
    if ((path === "/verify-email" || path === "/reset-password") && !token) { setError("This link is missing its token. Request a new link to continue."); return; }
    setBusy(true);
    try {
      if (path === "/signin") { const user = await login(email, password, remember); setUser(user); const next = sessionStorage.getItem("mededge-next"); sessionStorage.removeItem("mededge-next"); navigate(next && (next === "/account" || next === `/${user.role}` || next.startsWith(`/${user.role}?`) || next.startsWith(`/${user.role}/`)) ? next : `/${user.role}`, true); }
      else if (path === "/signup") { await register({ full_name: name.trim(), email, password, role }); setDone(true); setCooldown(60); }
      else if (path === "/verify-email") { await verifyEmail(token, password); setDone(true); setPassword(""); }
      else if (path === "/forgot-password") { await forgotPassword(email); setDone(true); }
      else if (path === "/reset-password") { await resetPassword(token, password); setDone(true); setPassword(""); setConfirm(""); }
      else if (path === "/check-email") { await resendVerification(email); setDone(true); setCooldown(60); }
    } catch (caught) { setError(errorText(caught)); if (caught instanceof ApiError && caught.retryAfter) setCooldown(caught.retryAfter); }
    finally { setBusy(false); }
  }

  async function resend() {
    if (!email || cooldown || busy) return;
    setBusy(true); setError("");
    try { await resendVerification(email); setCooldown(60); setDone(true); }
    catch (caught) { setError(errorText(caught)); if (caught instanceof ApiError && caught.retryAfter) setCooldown(caught.retryAfter); }
    finally { setBusy(false); }
  }

  const title = done && ["/signup", "/forgot-password"].includes(path) ? "Check your email" : done && path === "/verify-email" ? "Email confirmed" : done && path === "/reset-password" ? "Password updated" : path === "/signin" ? "Sign in" : path === "/signup" ? "Create account" : path === "/verify-email" ? "Confirm your email" : path === "/forgot-password" ? "Reset your password" : path === "/reset-password" ? "Choose a new password" : "Resend verification email";
  const description = path === "/signin" || path === "/signup" || done ? "" : path === "/verify-email" ? "Enter your password to confirm your email address." : path === "/forgot-password" ? "We’ll email you a reset link." : path === "/reset-password" ? "Choose a password you haven’t used here before." : "Enter your account’s email address.";
  const action = path === "/signin" ? "Sign in" : path === "/signup" ? "Create account" : path === "/verify-email" ? "Verify email" : path === "/forgot-password" ? "Send reset link" : path === "/reset-password" ? "Reset password" : "Send verification link";

  return <AuthShell><div className="auth-form-wrap">{!["/signin", "/signup"].includes(path) && <LinkButton to="/signin" className="back-link"><ArrowLeft size={16} /> Back to sign in</LinkButton>}<div className="auth-heading"><h1>{title}</h1>{description && <p>{description}</p>}</div>
    {error && <p className="auth-error" role="alert">{error}</p>}
    {done && path === "/signup" ? <div className="auth-success" role="status"><p>If registration can be completed, you’ll receive a verification link. It expires in 24 hours.</p><button type="button" className="secondary" disabled={busy || cooldown > 0} onClick={() => void resend()}>{cooldown ? `Resend in ${cooldown}s` : "Resend verification email"}</button><LinkButton to="/signin">Return to sign in</LinkButton></div> :
    done && path === "/verify-email" ? <div className="auth-success" role="status"><p>Your account is ready.</p><LinkButton className="primary auth-submit" to="/signin">Continue to sign in <ArrowRight size={18} /></LinkButton></div> :
    done && path === "/forgot-password" ? <div className="auth-success" role="status"><p>If an account exists for that email, you’ll receive a reset link.</p><LinkButton to="/signin">Return to sign in</LinkButton></div> :
    done && path === "/reset-password" ? <div className="auth-success" role="status"><p>Your other sessions have been signed out.</p><LinkButton className="primary auth-submit" to="/signin">Sign in <ArrowRight size={18} /></LinkButton></div> :
    <form className="auth-form" onSubmit={(event) => void submit(event)}>
      {path === "/signup" && <><fieldset className="role-field"><legend>Account type</legend><div className="role-options"><label className={role === "patient" ? "selected" : ""}><input type="radio" name="role" value="patient" checked={role === "patient"} onChange={() => setRole("patient")} /><span>Patient</span></label><label className={role === "doctor" ? "selected" : ""}><input type="radio" name="role" value="doctor" checked={role === "doctor"} onChange={() => setRole("doctor")} /><span>Doctor</span></label></div>{role === "doctor" && <small>Doctor credentials are self-declared, not professionally verified.</small>}</fieldset><div className="auth-field"><label htmlFor="full-name">Full name</label><input id="full-name" value={name} onChange={(event) => setName(event.target.value)} autoComplete="name" placeholder="Your full name" maxLength={100} required /></div></>}
      {["/signin", "/signup", "/forgot-password", "/check-email"].includes(path) && <EmailField value={email} onChange={setEmail} />}
      {["/signin", "/signup", "/reset-password", "/verify-email"].includes(path) && <PasswordField label={path === "/reset-password" ? "New password" : "Password"} value={password} onChange={setPassword} autoComplete={path === "/signin" || path === "/verify-email" ? "current-password" : "new-password"} hint={path === "/signup" || path === "/reset-password" ? "At least 12 characters. Spaces are welcome." : undefined} />}
      {["/signup", "/reset-password"].includes(path) && <PasswordField label="Confirm password" value={confirm} onChange={setConfirm} autoComplete="new-password" />}
      {path === "/signin" && <div className="auth-form-between"><label className="check"><input type="checkbox" checked={remember} onChange={(event) => setRemember(event.target.checked)} />Remember me</label><LinkButton to="/forgot-password">Forgot password?</LinkButton></div>}
      {done && path === "/check-email" && <p className="auth-status" role="status">If the account needs verification, a link has been sent.</p>}
      {(path === "/verify-email" || path === "/reset-password") && !token && <p className="auth-error" role="alert">This link is missing its token. Please request a new link.</p>}
      {path === "/verify-email" && <LinkButton to="/forgot-password">Forgot your password?</LinkButton>}
      <button className="primary auth-submit" type="submit" disabled={busy || cooldown > 0 || (["/verify-email", "/reset-password"].includes(path) && !token)}>{busy ? "Please wait…" : cooldown ? `Try again in ${cooldown}s` : action}<ArrowRight size={18} /></button>
    </form>}
    {path === "/signin" && <><div className="auth-bottom"><span>New here?</span><LinkButton to={`/signup?role=${role}`}>Create an account</LinkButton></div><div className="auth-options"><details><summary>Trouble signing in?</summary><LinkButton to="/check-email">Resend verification email</LinkButton></details>{demoAccounts?.enabled && <details><summary>Try a demo account</summary><p>Fictional records only.</p><div className="demo-login" role="group" aria-label="Demo accounts"><button type="button" className="secondary" onClick={() => { setEmail(demoAccounts.patient_email ?? ""); setPassword(demoAccounts.password ?? ""); }}>Use demo patient</button><button type="button" className="secondary" onClick={() => { setEmail(demoAccounts.doctor_email ?? ""); setPassword(demoAccounts.password ?? ""); }}>Use demo doctor</button></div></details>}</div></>}
    {path === "/signup" && !done && <div className="auth-bottom"><span>Already have an account?</span><LinkButton to={`/signin?role=${role}`}>Sign in</LinkButton></div>}
    {(["/verify-email", "/reset-password"].includes(path) && !token) && <div className="auth-bottom"><LinkButton to={path === "/verify-email" ? "/check-email" : "/forgot-password"}>Request a new link</LinkButton></div>}
  </div></AuthShell>;
}

export function AccountPage() {
  const user = useApp((state) => state.user);
  const setUser = useApp((state) => state.setUser);
  const [current, setCurrent] = useState(""); const [next, setNext] = useState(""); const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  async function onChange(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(""); if (next !== confirm) { setError("The new passwords don’t match."); return; }
    setBusy(true);
    try { await changePassword(current, next); setCsrfToken(""); setUser(null); navigate("/signin", true); }
    catch (caught) { setError(errorText(caught)); } finally { setBusy(false); }
  }
  async function signOutAll() {
    setBusy(true); setError("");
    try { await logout(true); setUser(null); navigate("/signin", true); }
    catch (caught) { setError(errorText(caught)); } finally { setBusy(false); }
  }
  return <main className="account-page"><LinkButton className="back-link" to={user ? `/${user.role}` : "/"}><ArrowLeft size={16} /> Back to workspace</LinkButton><h1>Account settings.</h1><p className="lede">Manage your account and sign-in details.</p><div className="account-grid"><section className="account-summary"><h2>Your account</h2><p>{user?.full_name}</p><p>{user?.email}</p><p className="account-role">{user?.role === "doctor" ? "Doctor · self-declared" : "Patient"}</p><button className="secondary" type="button" disabled={busy} onClick={() => void signOutAll()}>Sign out of all devices</button></section><section className="account-security"><h2>Change password</h2><p className="lede">Changing your password signs you out on all devices.</p><form className="auth-form" onSubmit={(event) => void onChange(event)}><PasswordField label="Current password" value={current} onChange={setCurrent} autoComplete="current-password" /><PasswordField label="New password" value={next} onChange={setNext} autoComplete="new-password" hint="At least 12 characters. Spaces are welcome." /><PasswordField label="Confirm password" value={confirm} onChange={setConfirm} autoComplete="new-password" />{error && <p className="auth-error" role="alert">{error}</p>}<button type="submit" className="primary auth-submit" disabled={busy}>{busy ? "Please wait…" : "Update password"}<ArrowRight size={18} /></button></form></section></div></main>;
}
