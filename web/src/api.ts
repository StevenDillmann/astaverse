import type {
  AppSettings,
  ArchiveKind,
  CommandPreview,
  DatasetPreview,
  DatasetRow,
  DatasetRows,
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

async function upload<T>(path: string, formData: FormData): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    method: "POST",
    body: formData,
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

const archiveQuery = (includeArchived: boolean) =>
  includeArchived ? "?include_archived=true" : "";

export const api = {
  overview: () => request<Overview>("/overview"),
  hypotheses: (includeArchived = false) =>
    request<HypothesisRow[]>(`/hypotheses${archiveQuery(includeArchived)}`),
  hypothesis: (id: string) => request<HypothesisDetail>(`/hypotheses/${id}`),
  experiments: (includeArchived = false) =>
    request<ExperimentRow[]>(`/experiments${archiveQuery(includeArchived)}`),
  experiment: (id: string) => request<ExperimentDetail>(`/experiments/${id}`),
  progress: (id: string) => request<Progress>(`/runs/${id}/progress`),
  datasets: (includeArchived = false) =>
    request<DatasetRow[]>(`/datasets${archiveQuery(includeArchived)}`),
  dataset: (name: string) => request<DatasetRow>(`/datasets/${encodeURIComponent(name)}`),
  datasetRows: (name: string, limit = 20) =>
    request<DatasetRows>(`/datasets/${encodeURIComponent(name)}/rows?limit=${limit}`),

  previewDataset: (payload: {
    file: File;
    name?: string;
    description?: string;
    column_descriptions?: Record<string, string>;
  }) => {
    const formData = new FormData();
    formData.append("file", payload.file);
    if (payload.name) formData.append("name", payload.name);
    if (payload.description) formData.append("description", payload.description);
    if (payload.column_descriptions && Object.keys(payload.column_descriptions).length) {
      formData.append("column_descriptions", JSON.stringify(payload.column_descriptions));
    }
    return upload<DatasetPreview>("/datasets/preview", formData);
  },

  createDataset: (payload: {
    file: File;
    name: string;
    description?: string;
    column_descriptions?: Record<string, string>;
  }) => {
    const formData = new FormData();
    formData.append("file", payload.file);
    formData.append("name", payload.name);
    if (payload.description) formData.append("description", payload.description);
    if (payload.column_descriptions && Object.keys(payload.column_descriptions).length) {
      formData.append("column_descriptions", JSON.stringify(payload.column_descriptions));
    }
    return upload<DatasetRow>("/datasets", formData);
  },

  modes: () => request<ExtractionMode[]>("/extraction-modes"),
  settings: () => request<AppSettings>("/settings"),
  setArchived: (kind: ArchiveKind, id: string, archived: boolean) =>
    request<AppSettings>("/archive", {
      method: "POST",
      body: JSON.stringify({ kind, id, archived }),
    }),
  // One request for the whole selection: the server applies it under a single
  // read-modify-write, so a bulk action cannot half-apply.
  setArchivedMany: (kind: ArchiveKind, ids: string[], archived: boolean) =>
    request<AppSettings>("/archive", {
      method: "POST",
      body: JSON.stringify({ kind, ids, archived }),
    }),

  preview: (config: RunConfig, experimentId = "<experiment-id>") =>
    request<CommandPreview>("/command-preview", {
      method: "POST",
      body: JSON.stringify({ config, experiment_id: experimentId }),
    }),

  createHypothesis: (payload: {
    hypothesis: string;
    dataset: string;
    description?: string;
  }) =>
    request<{ id: string; hypothesis: string; dataset_name: string }>("/hypotheses", {
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

  deleteDataset: (name: string) =>
    request<{ deleted: string }>(`/datasets/${encodeURIComponent(name)}`, {
      method: "DELETE",
    }),

  deleteHypothesis: (id: string) =>
    request<{ deleted: string }>(`/hypotheses/${id}`, { method: "DELETE" }),

  deleteExperiment: (id: string) =>
    request<{ deleted: string; hypothesis_id: string }>(`/experiments/${id}`, {
      method: "DELETE",
    }),

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
