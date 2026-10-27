import type { Run, SampleCase } from "./types";

export const apiBase = import.meta.env.VITE_API_BASE ?? "";

async function readError(response: Response): Promise<string> {
  const text = await response.text();
  try {
    const body = JSON.parse(text) as { detail?: string };
    return body.detail || text || response.statusText;
  } catch {
    return text || response.statusText;
  }
}

export async function listCases(): Promise<SampleCase[]> {
  const response = await fetch(`${apiBase}/api/cases`);
  if (!response.ok) throw new Error(await readError(response));
  const body = (await response.json()) as { cases: SampleCase[] };
  return body.cases;
}

export async function createRun(form: FormData): Promise<{ run_id: string }> {
  const response = await fetch(`${apiBase}/api/runs`, { method: "POST", body: form });
  if (!response.ok) throw new Error(await readError(response));
  return response.json() as Promise<{ run_id: string }>;
}

export async function getRun(runId: string): Promise<Run> {
  const response = await fetch(`${apiBase}/api/runs/${runId}`);
  if (!response.ok) throw new Error(await readError(response));
  return response.json() as Promise<Run>;
}

export async function confirmRun(runId: string): Promise<void> {
  const response = await fetch(`${apiBase}/api/runs/${runId}/confirm`, { method: "POST" });
  if (!response.ok) throw new Error(await readError(response));
}

export async function approveRun(runId: string, run: Run): Promise<Run["bundle"]> {
  const response = await fetch(`${apiBase}/api/runs/${runId}/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      rows: run.extraction?.rows ?? [],
      medications: run.extraction?.medications ?? [],
      note: run.encounter?.note ?? "",
    }),
  });
  if (!response.ok) throw new Error(await readError(response));
  const body = (await response.json()) as { bundle: Run["bundle"] };
  return body.bundle;
}

export async function exportRun(runId: string): Promise<void> {
  const response = await fetch(`${apiBase}/api/runs/${runId}/export`, { method: "POST" });
  if (!response.ok) throw new Error(await readError(response));
}

export async function shareRun(runId: string): Promise<string> {
  const response = await fetch(`${apiBase}/api/runs/${runId}/share`, { method: "POST" });
  if (!response.ok) throw new Error(await readError(response));
  const body = (await response.json()) as { code: string };
  return body.code;
}

export async function openShare(code: string): Promise<Run> {
  const response = await fetch(`${apiBase}/api/share/${encodeURIComponent(code)}`);
  if (!response.ok) throw new Error(await readError(response));
  return response.json() as Promise<Run>;
}

export async function dictate(runId: string, wav: Blob): Promise<Run> {
  const form = new FormData();
  form.append("audio", wav, "visit.wav");
  const response = await fetch(`${apiBase}/api/runs/${runId}/dictate`, { method: "POST", body: form });
  if (!response.ok) throw new Error(await readError(response));
  return response.json() as Promise<Run>;
}
