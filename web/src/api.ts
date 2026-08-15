const BASE = import.meta.env.DEV ? "http://127.0.0.1:8000" : "";

export const STAGES = [
  "study",
  "plans",
  "decisions",
  "universes",
  "task",
  "execute",
  "verdicts",
  "surprisal",
] as const;

export type Stage = (typeof STAGES)[number];
export type StageState = "complete" | "ready" | "pending";

export interface RunSummary {
  run_id: string;
  hypothesis: string;
  dataset: string;
  created_at: string;
  status: Record<Stage, StageState>;
  n_complete: number;
}

export interface RunDetail {
  run_id: string;
  manifest: Record<string, unknown>;
  status: Record<Stage, StageState>;
  artifacts: Record<Stage, unknown>;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    const detail = body.detail;
    throw new Error(typeof detail === "string" ? detail : detail?.error ?? "Request failed");
  }
  return response.json();
}

export const listRuns = () => request<RunSummary[]>("/api/runs");
export const getRun = (id: string) => request<RunDetail>(`/api/runs/${id}`);
export const getLog = (id: string) => request<{ log: string }>(`/api/runs/${id}/log`);

export const runStage = (id: string, stage: Stage, options: Record<string, unknown> = {}) =>
  request<{ status: Record<Stage, StageState>; artifact: unknown }>(
    `/api/runs/${id}/stages/${stage}`,
    { method: "POST", body: JSON.stringify(options) },
  );

export const createRun = (hypothesis: string, dataset: string) =>
  request<{ run_id: string }>("/api/runs", {
    method: "POST",
    body: JSON.stringify({ hypothesis, dataset }),
  });
