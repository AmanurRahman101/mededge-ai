import { ArrowLeft, ArrowRight, Eye, EyeSlash, FileText, LockKey, ShareNetwork } from "@phosphor-icons/react";
import { useEffect, useState, type FormEvent, type ReactNode } from "react";

import { changePassword, forgotPassword, getDemoAccounts, type DemoAccounts, login, logout, register, resendVerification, resetPassword, setCsrfToken, verifyEmail, type UserRole } from "./api";
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
  return <main className="auth-layout"><aside className="auth-aside"><div className="auth-aside-main"><div className="auth-symbol" aria-hidden="true"><span></span><span></span><span></span><span></span></div><h2>Care in the details.<br /><span>Clarity in the record.</span></h2><p>Turn paper reports into structured records, with the source available for review.</p></div><div className="auth-principles"><div><FileText size={18} /><span>From page to record</span></div><div><LockKey size={18} /><span>Review before sharing</span></div><div><ShareNetwork size={18} /><span>Made for the handoff</span></div></div></aside><section className="auth-content">{children}</section></main>;
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
  useEffect(() => { if (window.location.hash) window.history.replaceState(null, "", `${window.location.pathname}${window.location.search}`); }, []);
  useEffect(() => { if (!cooldown) return; const timer = window.setTimeout(() => setCooldown((value) => value - 1), 1000); return () => window.clearTimeout(timer); }, [cooldown]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError("");
    if ((path === "/signup" || path === "/reset-password") && password !== confirm) { setError("The passwords don’t match. Please check and try again."); return; }
    if ((path === "/verify-email" || path === "/reset-password") && !token) { setError("This link is missing its token. Request a new link to continue."); return; }
    setBusy(true);
    try {
      if (path === "/signin") { const user = await login(email, password, remember); setUser(user); const next = sessionStorage.getItem("mededge-next"); sessionStorage.removeItem("mededge-next"); navigate(next && (next === "/account" || next.startsWith(`/${user.role}/`)) ? next : `/${user.role}`, true); }
      else if (path === "/signup") { await register({ full_name: name.trim(), email, password, role }); setDone(true); }
      else if (path === "/verify-email") { await verifyEmail(token, password); setDone(true); setPassword(""); }
      else if (path === "/forgot-password") { await forgotPassword(email); setDone(true); }
      else if (path === "/reset-password") { await resetPassword(token, password); setDone(true); setPassword(""); setConfirm(""); }
      else if (path === "/check-email") { await resendVerification(email); setDone(true); setCooldown(60); }
    } catch (caught) { setError(errorText(caught)); }
    finally { setBusy(false); }
  }

  async function resend() {
    if (!email || cooldown || busy) return;
    setBusy(true); setError("");
    try { await resendVerification(email); setCooldown(60); setDone(true); }
    catch (caught) { setError(errorText(caught)); }
    finally { setBusy(false); }
  }

  const title = path === "/signin" ? "Welcome back." : path === "/signup" ? "Create your account." : path === "/verify-email" ? "Confirm your email." : path === "/forgot-password" ? "Forgot your password?" : path === "/reset-password" ? "Choose a new password." : "Check your email.";
  const description = path === "/signin" ? "Sign in to continue to your workspace." : path === "/signup" ? "A place for your records, ready when you need them." : path === "/verify-email" ? "Enter your account password to confirm this address and finish setting up your account." : path === "/forgot-password" ? "Enter your email and we’ll send you a reset link." : path === "/reset-password" ? "Choose a password you haven’t used here before." : "Request another verification link for your account.";
  const action = path === "/signin" ? "Sign in" : path === "/signup" ? "Create account" : path === "/verify-email" ? "Verify email" : path === "/forgot-password" ? "Send reset link" : path === "/reset-password" ? "Reset password" : "Send verification link";

  return <AuthShell><div className="auth-form-wrap"><LinkButton to="/" className="back-link"><ArrowLeft size={16} /> Back to MedEdge</LinkButton><div className="auth-heading"><h1>{title}</h1><p>{description}</p></div>
    {done && path === "/signup" ? <div className="auth-success" role="status"><h2>Check your email.</h2><p>If registration can be completed, a verification link has been sent to your address. The link is valid for 24 hours.</p><button type="button" className="secondary" disabled={busy || cooldown > 0} onClick={() => void resend()}>{cooldown ? `Resend in ${cooldown}s` : "Resend verification email"}</button><LinkButton to="/signin">Return to sign in</LinkButton></div> :
    done && path === "/verify-email" ? <div className="auth-success" role="status"><h2>Email confirmed.</h2><p>Your account is ready. Sign in to continue.</p><LinkButton className="primary auth-submit" to="/signin">Continue to sign in <ArrowRight size={18} /></LinkButton></div> :
    done && path === "/forgot-password" ? <div className="auth-success" role="status"><h2>Check your inbox.</h2><p>If an account exists for that address, you’ll receive a password reset link.</p><LinkButton to="/signin">Return to sign in</LinkButton></div> :
    done && path === "/reset-password" ? <div className="auth-success" role="status"><h2>Password updated.</h2><p>For your security, your other sessions have been signed out.</p><LinkButton className="primary auth-submit" to="/signin">Sign in <ArrowRight size={18} /></LinkButton></div> :
    <form className="auth-form" onSubmit={(event) => void submit(event)}>
      {path === "/signin" && demoAccounts?.enabled && <div className="demo-login" role="group" aria-label="Judge demo accounts"><span>Judging? Try the shared demo, fictional data only.</span><div><button type="button" className="text-link" onClick={() => { setEmail(demoAccounts.patient_email ?? ""); setPassword(demoAccounts.password ?? ""); }}>Use demo patient</button><button type="button" className="text-link" onClick={() => { setEmail(demoAccounts.doctor_email ?? ""); setPassword(demoAccounts.password ?? ""); }}>Use demo doctor</button></div></div>}
      {path === "/signup" && <><div className="auth-field"><label htmlFor="full-name">Full name</label><input id="full-name" value={name} onChange={(event) => setName(event.target.value)} autoComplete="name" placeholder="Your full name" maxLength={100} required /></div><fieldset className="role-field"><legend>I’m joining as a</legend><div className="role-options"><label className={role === "patient" ? "selected" : ""}><input type="radio" name="role" value="patient" checked={role === "patient"} onChange={() => setRole("patient")} /><span>Patient<small>Manage and share records</small></span></label><label className={role === "doctor" ? "selected" : ""}><input type="radio" name="role" value="doctor" checked={role === "doctor"} onChange={() => setRole("doctor")} /><span>Doctor<small>Review and export records</small></span></label></div>{role === "doctor" && <small>Doctor accounts are self-declared; email verification does not verify credentials.</small>}</fieldset></>}
      {["/signin", "/signup", "/forgot-password", "/check-email"].includes(path) && <EmailField value={email} onChange={setEmail} />}
      {["/signin", "/signup", "/reset-password", "/verify-email"].includes(path) && <PasswordField label={path === "/reset-password" ? "New password" : "Password"} value={password} onChange={setPassword} autoComplete={path === "/signin" || path === "/verify-email" ? "current-password" : "new-password"} hint={path === "/signup" || path === "/reset-password" ? "At least 12 characters. Spaces are welcome." : undefined} />}
      {["/signup", "/reset-password"].includes(path) && <PasswordField label="Confirm password" value={confirm} onChange={setConfirm} autoComplete="new-password" />}
      {path === "/signin" && <div className="auth-form-between"><label className="check"><input type="checkbox" checked={remember} onChange={(event) => setRemember(event.target.checked)} />Remember me</label><LinkButton to="/forgot-password">Forgot password?</LinkButton></div>}
      {error && <p className="auth-error" role="alert">{error}</p>}
      {done && path === "/check-email" && <p className="auth-status" role="status">If the account needs verification, a link has been sent.</p>}
      {(path === "/verify-email" || path === "/reset-password") && !token && <p className="auth-error" role="alert">This link is missing its token. Please request a new link.</p>}
      {path === "/verify-email" && <LinkButton to="/forgot-password">Forgot your password?</LinkButton>}
      <button className="primary auth-submit" type="submit" disabled={busy || (path === "/check-email" && cooldown > 0) || (["/verify-email", "/reset-password"].includes(path) && !token)}>{busy ? "Please wait…" : path === "/check-email" && cooldown ? `Try again in ${cooldown}s` : action}<ArrowRight size={18} /></button>
    </form>}
    {path === "/signin" && <div className="auth-bottom"><span>New to MedEdge?</span><LinkButton to={`/signup?role=${role}`}>Create an account</LinkButton><LinkButton to="/check-email">Resend verification</LinkButton></div>}
    {path === "/signup" && !done && <div className="auth-bottom"><span>Already have an account?</span><LinkButton to={`/signin?role=${role}`}>Sign in</LinkButton></div>}
    {(["/verify-email", "/reset-password"].includes(path) && !token) && <div className="auth-bottom"><LinkButton to={path === "/verify-email" ? "/check-email" : "/forgot-password"}>Request a new link</LinkButton></div>}
    {(path === "/forgot-password" || path === "/check-email") && !done && <div className="auth-bottom"><LinkButton to="/signin">Back to sign in</LinkButton></div>}
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
