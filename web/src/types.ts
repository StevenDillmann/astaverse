export type ExtractionMethod = "sample_plans" | "audit_plan" | "direct";
export type Stage =
  | "study"
  | "plans"
  | "decisions"
  | "universes"
  | "task"
  | "execute"
  | "verdicts"
  | "conclusion"
  | "refinement";

export type StageState = "complete" | "ready" | "pending" | "skipped";

export interface PlansConfig {
  k: number;
  model: string | null;
  temperature: number;
}

export interface DecisionsConfig {
  mode: ExtractionMethod;
  models: string[];
  critique: boolean;
  max_decisions: number;
}

export interface UniversesConfig {
  cap: number | null;
  include: string[];
  exclude: string[];
}

export interface ExecuteConfig {
  agent: string;
  models: string[];
  dry_run: boolean;
}

export interface ConclusionConfig {
  model: string | null;
}

export interface RunConfig {
  plans: PlansConfig;
  decisions: DecisionsConfig;
  universes: UniversesConfig;
  execute: ExecuteConfig;
  conclusion: ConclusionConfig;
  through: Stage;
}

export interface Support {
  verdict: string | null;
  rate_min: number | null;
  rate_max: number | null;
  n_scored: number;
  n_attempts: number;
  corroborated: boolean;
}

export interface HypothesisRow {
  id: string;
  hypothesis: string;
  dataset_name: string;
  n_attempts: number;
  running: boolean;
  support: Support;
  fragility_range: { min: number; max: number; n: number } | null;
  agreement: string | null;
  n_unique_decisions: number;
  updated_at: string;
}

export interface ExperimentRow {
  id: string;
  /** The short id shown to people — EXP-00014. Null only for a run predating numbering. */
  number: number | null;
  claim_id: string;
  hypothesis: string;
  dataset_name: string;
  config_label: string;
  mode: string | null;
  critique: boolean | null;
  cap: number | null;
  status: Record<Stage, StageState>;
  n_complete: number;
  n_stages: number;
  running: boolean;
  n_universes: number | null;
  coverage: number | null;
  support_rate: number | null;
  created_at: string;
}

export interface DatasetColumn {
  name: string;
  dtype: string;
  description?: string | null;
  n_missing?: number | null;
  min?: number | null;
  max?: number | null;
  samples?: unknown[];
  std?: number | null;
  num_unique_values?: number | null;
}

export interface DatasetPreview {
  name: string;
  n_rows: number | null;
  n_columns: number;
  description?: string | null;
  columns: DatasetColumn[];
  available: boolean;
}

export interface DatasetRows {
  name: string;
  columns: string[];
  rows: string[][];
  n_rows: number | null;
  limit: number;
}

export interface DatasetRow {
  name: string;
  path?: string;
  csv_path?: string;
  kind?: string;
  n_rows: number | null;
  n_columns: number | null;
  columns?: string[];
  fields?: DatasetColumn[];
  description?: string | null;
  n_claims?: number;
  n_hypotheses?: number;
  n_experiments?: number;
  n_attempts?: number;
  n_fragile?: number;
  n_available_hypotheses?: number;
  n_autodiscovery_hypotheses?: number;
}

export interface Overview {
  hypotheses: HypothesisRow[];
  experiments: ExperimentRow[];
  datasets: DatasetRow[];
}

export interface Attempt {
  id: string;
  number: number | null;
  created_at: string;
  status: Record<Stage, StageState>;
  n_complete: number;
  running: boolean;
  mode: ExtractionMethod | null;
  models: string[];
  critique: boolean;
  cap: number | null;
  seeded: string | null;
  agent_models: string[];
  n_plans: number | null;
  n_universes: number | null;
  decisions: string[];
  n_grid: number | null;
  verdicts: Record<string, number>;
  top_flip: string | null;
  top_flip_rate: number | null;
  coverage: number | null;
  config_label: string;
  support_rate: number | null;
}

export interface HypothesisDetail {
  id: string;
  hypothesis: string;
  dataset: string;
  dataset_name: string;
  support: Support;
  attempts: Attempt[];
  shared_decisions: string[];
  unique_decisions: Record<string, string[]>;
  agreement: string | null;
  fragility_range: { min: number; max: number; n: number } | null;
}

export interface CommandPreview {
  run: string;
  stages: Record<Stage, string>;
  planned_stages: Stage[];
}

export interface Progress {
  run_id?: string;
  target?: Stage;
  pending?: Stage[];
  current?: Stage | null;
  done?: Stage[];
  skipped?: Stage[];
  failed?: Stage | null;
  error?: string | null;
  finished: boolean;
  running: boolean;
}

export interface ExperimentDetail {
  id: string;
  number: number | null;
  claim_id: string;
  hypothesis: string;
  dataset: string;
  seed: Record<string, string> | null;
  status: Record<Stage, StageState>;
  stages: Stage[];
  config: RunConfig;
  review_before_execute: boolean;
  decision_reviewed_at: string | null;
  commands: CommandPreview;
  progress: Progress | null;
  artifacts: Record<Stage, unknown>;
  history: Array<Record<string, unknown>>;
}

export type ArchiveKind = "dataset" | "hypothesis" | "experiment";

export interface AppSettings {
  default_experiment: RunConfig;
  review_before_execute: boolean;
  archived_datasets: string[];
  archived_hypotheses: string[];
  archived_experiments: string[];
  providers: {
    openai: boolean;
    gemini: boolean;
    harbor: boolean;
  };
}

export interface ExtractionMode {
  id: ExtractionMethod;
  description: string;
  needs_plans: boolean;
}
