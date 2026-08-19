import type {
  AppSettings,
  CommandPreview,
  DatasetRow,
  ExperimentDetail,
  ExperimentRow,
  ExtractionMode,
  HypothesisDetail,
  HypothesisRow,
  Overview,
  Progress,
  RunConfig,
  Stage,
} from "./types";

const API = "/api";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as
      | { detail?: string | { error?: string }; error?: string }
      | null;
    const detail = payload?.detail;
    const message =
      typeof detail === "string"
        ? detail
        : detail?.error || payload?.error || `${response.status} ${response.statusText}`;
    throw new ApiError(response.status, message);
  }
  return (await response.json()) as T;
}

export const api = {
  overview: () => request<Overview>("/overview"),
  hypotheses: () => request<HypothesisRow[]>("/hypotheses"),
  hypothesis: (id: string) => request<HypothesisDetail>(`/hypotheses/${id}`),
  experiments: () => request<ExperimentRow[]>("/experiments"),
  experiment: (id: string) => request<ExperimentDetail>(`/experiments/${id}`),
  progress: (id: string) => request<Progress>(`/runs/${id}/progress`),
  datasets: () => request<DatasetRow[]>("/datasets"),
  dataset: (name: string) => request<DatasetRow>(`/datasets/${encodeURIComponent(name)}`),
  modes: () => request<ExtractionMode[]>("/extraction-modes"),
  settings: () => request<AppSettings>("/settings"),

  preview: (config: RunConfig, experimentId = "<experiment-id>") =>
    request<CommandPreview>("/command-preview", {
      method: "POST",
      body: JSON.stringify({ config, experiment_id: experimentId }),
    }),

  createHypothesis: (payload: {
    hypothesis: string;
    dataset: string;
    config: RunConfig;
    review_before_execute: boolean;
  }) =>
    request<{ run_id: string; claim_id: string }>("/hypotheses", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  createExperiment: (
    hypothesisId: string,
    payload: { config: RunConfig; review_before_execute: boolean },
  ) =>
    request<{ run_id: string; claim_id: string }>(
      `/hypotheses/${hypothesisId}/experiments`,
      { method: "POST", body: JSON.stringify(payload) },
    ),

  updateConfig: (id: string, patch: Partial<RunConfig>) =>
    request<RunConfig>(`/experiments/${id}/config`, {
      method: "PUT",
      body: JSON.stringify(patch),
    }),

  run: (id: string, through?: Stage, force = false, confirm = false) => {
    const params = new URLSearchParams();
    if (through) params.set("through", through);
    if (force) params.set("force", "true");
    if (confirm) params.set("confirm", "true");
    const query = params.size ? `?${params}` : "";
    return request<Progress>(`/experiments/${id}/run${query}`, { method: "POST" });
  },

  runStage: (id: string, stage: Stage, confirm = false) =>
    request<{ id: string; stage: Stage; status: Record<string, string> }>(
      `/experiments/${id}/stages/${stage}${confirm ? "?confirm=true" : ""}`,
      { method: "POST" },
    ),

  approve: (id: string) =>
    request<{ id: string; decision_reviewed_at: string }>(`/experiments/${id}/review`, {
      method: "POST",
    }),

  updateSettings: (patch: Partial<AppSettings>) =>
    request<Omit<AppSettings, "providers">>("/settings", {
      method: "PUT",
      body: JSON.stringify(patch),
    }),

  files: (id: string) =>
    request<Array<{ path: string; name: string; category: string; bytes: number }>>(
      `/runs/${id}/files`,
    ),
  file: (id: string, path: string) =>
    request<{ path: string; bytes: number; content: string }>(
      `/runs/${id}/file?path=${encodeURIComponent(path)}`,
    ),
};
