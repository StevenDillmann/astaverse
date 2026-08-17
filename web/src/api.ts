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
  id: string;
  hypothesis: string;
  dataset: string;
  created_at: string;
  status: Record<Stage, StageState>;
  n_complete: number;
  running?: boolean;
}

export interface RunDetail {
  id: string;
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

export const listRuns = () => request<RunSummary[]>("/api/analyses");
export const getRun = (id: string) => request<RunDetail>(`/api/analyses/${id}`);
export const getLog = (id: string) => request<{ log: string }>(`/api/analyses/${id}/log`);

export const runStage = (id: string, stage: Stage, options: Record<string, unknown> = {}) =>
  request<{ status: Record<Stage, StageState>; artifact: unknown }>(
    `/api/analyses/${id}/stages/${stage}`,
    { method: "POST", body: JSON.stringify(options) },
  );

export const createRun = (hypothesis: string, dataset: string) =>
  request<{ id: string }>("/api/analyses", {
    method: "POST",
    body: JSON.stringify({ hypothesis, dataset }),
  });

export interface DatasetInfo {
  name: string;
  path: string;
  csv_path: string;
  kind: string;
  n_columns: number;
  n_rows: number | null;
  description: string | null;
  research_questions: string[];
  columns: string[];
}

export interface RunFile {
  path: string;
  name: string;
  category: string;
  bytes: number;
  modified: number;
}

export interface HistoryEntry {
  archived_at: string;
  directory: string;
  superseded_by: string;
  stages: string[];
}

export const listDatasets = () => request<DatasetInfo[]>("/api/datasets");
export const listFiles = (id: string) => request<RunFile[]>(`/api/analyses/${id}/files`);
export const readFile = (id: string, path: string) =>
  request<{ path: string; bytes: number; content: string }>(
    `/api/analyses/${id}/file?path=${encodeURIComponent(path)}`,
  );
export const getHistory = (id: string) => request<HistoryEntry[]>(`/api/analyses/${id}/history`);

export interface PlanRecord {
  normalized_id: string;
  dataset: string;
  hypothesis: string;
  source_path: string;
  success: boolean;
  has_code: boolean;
  query_preview: string;
  level: number | null;
  parent_idx: number | null;
  visits: number | null;
}

export const listHypotheses = (dataset: string, q = "") =>
  request<{ dataset: string; total: number; matched: number; hypotheses: PlanRecord[] }>(
    `/api/datasets/${encodeURIComponent(dataset)}/hypotheses?q=${encodeURIComponent(q)}`,
  );

export const createSeededRun = (
  hypothesis: string,
  dataset: string,
  seed?: { seed_dataset: string; seed_normalized_id: string },
) =>
  request<{ id: string }>("/api/analyses", {
    method: "POST",
    body: JSON.stringify({ hypothesis, dataset, ...(seed ?? {}) }),
  });

export interface RunConfig {
  plans: { k: number; model: string | null; temperature: number };
  decisions: {
    mode: string;
    models: string[];
    critique: boolean;
    union_modes: string[];
    max_decisions: number;
  };
  universes: { cap: number; include: string[]; exclude: string[] };
  execute: { agent: string; models: string[]; dry_run: boolean };
  surprisal: { model: string | null; n_samples: number };
  through: string;
}

export interface ExtractionModeInfo {
  id: string;
  description: string;
  needs_plans: boolean;
}

export interface RunProgress {
  run_id?: string;
  target?: string;
  pending?: string[];
  current?: string | null;
  done?: string[];
  skipped?: string[];
  failed?: string | null;
  error?: string | null;
  finished: boolean;
  running: boolean;
}

export const getConfig = (id: string) => request<RunConfig>(`/api/analyses/${id}/config`);

export const putConfig = (id: string, patch: Record<string, unknown>) =>
  request<RunConfig>(`/api/analyses/${id}/config`, {
    method: "PUT",
    body: JSON.stringify(patch),
  });

export const listModes = () => request<ExtractionModeInfo[]>("/api/extraction-modes");

/** JSON Schema of RunConfig — the same model that generates the CLI flags. */
export interface JsonSchema {
  properties?: Record<string, any>;
  $defs?: Record<string, any>;
  [k: string]: any;
}

export const getConfigSchema = () => request<JsonSchema>("/api/config-schema");

export const runAll = (id: string, through?: string) =>
  request<RunProgress>(
    `/api/analyses/${id}/run${through ? `?through=${encodeURIComponent(through)}` : ""}`,
    { method: "POST" },
  );

export const getProgress = (id: string) => request<RunProgress>(`/api/analyses/${id}/progress`);

// -- claims ----------------------------------------------------------------

export interface Attempt {
  id: string;
  created_at: string;
  status: Record<Stage, StageState>;
  n_complete: number;
  running: boolean;
  mode: string | null;
  models: string[];
  critique: boolean;
  cap: number | null;
  seeded: string | null;
  agent_models: string[];
  n_plans: number | null;
  decisions: string[];
  n_universes: number | null;
  n_grid: number | null;
  verdicts: Record<string, number>;
  joint_surprisal: number | null;
  fragility: number | null;
  top_flip: string | null;
  top_flip_rate: number | null;
  coverage: number | null;
}

export interface ClaimDetail {
  id: string;
  hypothesis: string;
  dataset: string;
  dataset_name: string;
  n_attempts: number;
  attempts: Attempt[];
  shared_decisions: string[];
  unique_decisions: Record<string, string[]>;
  agreement: "agree" | "disagree" | null;
  fragility_range: { min: number; max: number; n: number } | null;
}

export const listClaims = () => request<ClaimDetail[]>("/api/claims");
export const getClaim = (id: string) => request<ClaimDetail>(`/api/claims/${id}`);
export const newAttempt = (claimId: string, config?: Record<string, unknown>) =>
  request<{ id: string }>(`/api/claims/${claimId}/attempts`, {
    method: "POST",
    body: JSON.stringify({ config: config ?? null }),
  });
