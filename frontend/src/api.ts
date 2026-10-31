import type { Run, SampleCase, Extraction, Encounter } from "./types";

export const apiBase = import.meta.env.VITE_API_BASE ?? "";
let csrfToken = "";
export const setCsrfToken = (token: string) => { csrfToken = token; };

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) { super(message); this.status = status; }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.method && init.method !== "GET" && csrfToken) headers.set("X-CSRF-Token", csrfToken);
  let response: Response;
  try {
    response = await fetch(`${apiBase}${path}`, { ...init, headers, credentials: "same-origin" });
  } catch {
    throw new ApiError("The service is starting or unavailable. Please try again in a moment.", 0);
  }
  if (!response.ok) {
    let message = "Something went wrong. Please try again.";
    try {
      const body = await response.json() as { detail?: string | { msg?: string }[] };
      if (typeof body.detail === "string") message = body.detail;
      else if (Array.isArray(body.detail)) message = body.detail.map((item) => item.msg).filter(Boolean).join(". ") || message;
    } catch { /* keep the safe fallback */ }
    throw new ApiError(message, response.status);
  }
  return response.json() as Promise<T>;
}

export function post<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body ?? {}) });
}

export const getChart = <T,>(path: string) => request<T>(`/api/chart${path}`);
export const updateChart = <T,>(path: string, body: unknown) => request<T>(`/api/chart${path}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
export const deleteChart = <T,>(path: string) => request<T>(`/api/chart${path}`, { method: "DELETE" });

export type UserRole = "patient" | "doctor";
export interface User { id: string; full_name: string; email: string; role: UserRole; verified: boolean }
interface Session { user: User; csrf_token: string }
type Message = { message: string };

export async function getSession(): Promise<User | null> {
  try { const data = await request<Session>("/api/auth/me"); setCsrfToken(data.csrf_token); return data.user; }
  catch (error) { if (error instanceof ApiError && error.status === 401) { setCsrfToken(""); return null; } throw error; }
}
export async function login(email: string, password: string, remember: boolean): Promise<User> {
  const data = await post<Session>("/api/auth/login", { email, password, remember });
  setCsrfToken(data.csrf_token); return data.user;
}
export const register = (data: { full_name: string; email: string; password: string; role: UserRole }) => post<Message>("/api/auth/register", data);
export const verifyEmail = (token: string, password: string) => post<Message>("/api/auth/verify", { token, password });
export const resendVerification = (email: string) => post<Message>("/api/auth/resend-verification", { email });
export const forgotPassword = (email: string) => post<Message>("/api/auth/forgot-password", { email });
export const resetPassword = (token: string, password: string) => post<Message>("/api/auth/reset-password", { token, password });
export const changePassword = (current_password: string, new_password: string) => post<Message>("/api/auth/change-password", { current_password, new_password });
export async function logout(all = false): Promise<void> { await post<Message>(all ? "/api/auth/logout-all" : "/api/auth/logout"); setCsrfToken(""); }

export async function listCases(): Promise<SampleCase[]> { return (await request<{ cases: SampleCase[] }>("/api/cases")).cases; }
export interface Demo { id: string; title: string; kind: string; summary: string; image_url: string; extraction: Extraction; encounter: Encounter; bundle: Record<string, unknown>; replay: boolean }
export const getDemo = (id: string) => request<Demo>(`/api/demo/${encodeURIComponent(id)}`);
export const createRun = (form: FormData) => request<{ run_id: string }>("/api/runs", { method: "POST", body: form });
export const getRun = (runId: string) => request<Run>(`/api/runs/${runId}`);
export const confirmRun = async (runId: string) => { await post(`/api/runs/${runId}/confirm`); };
export async function approveRun(runId: string, run: Run): Promise<Run["bundle"]> {
  const data = await post<{ bundle: Run["bundle"] }>(`/api/runs/${runId}/approve`, { rows: run.extraction?.rows ?? [], medications: run.extraction?.medications ?? [], note: run.encounter?.note ?? "" });
  return data.bundle;
}
export const exportRun = async (runId: string) => { await post(`/api/runs/${runId}/export`); };
export async function shareRun(runId: string): Promise<string> { return (await post<{ code: string }>(`/api/runs/${runId}/share`)).code; }
export const openShare = (code: string) => post<Run>("/api/share/redeem", { code });
export async function dictate(runId: string, wav: Blob): Promise<Run> { const form = new FormData(); form.append("audio", wav, "visit.wav"); return request<Run>(`/api/runs/${runId}/dictate`, { method: "POST", body: form }); }

export interface DemoAccounts { enabled: boolean; patient_email?: string; doctor_email?: string; password?: string }
export const getDemoAccounts = () => request<DemoAccounts>("/api/demo/accounts");
export async function getSampleDictation(): Promise<Blob> {
  const response = await fetch(`${apiBase}/api/demo/dictation`, { credentials: "same-origin" });
  if (!response.ok) throw new ApiError("The sample dictation is unavailable.", response.status);
  return response.blob();
}
