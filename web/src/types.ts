export type ExtractionMethod = "sample_plans" | "audit_plan" | "direct";
export type Stage =
  | "study"
  | "plans"
  | "decisions"
  | "universes"
  | "task"
  | "execute"
  | "verdicts"
  | "surprisal";

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
  cap: number;
  include: string[];
  exclude: string[];
}

export interface ExecuteConfig {
  agent: string;
  models: string[];
  dry_run: boolean;
}

export interface SurprisalConfig {
  model: string | null;
  n_samples: number;
}

export interface RunConfig {
  plans: PlansConfig;
  decisions: DecisionsConfig;
  universes: UniversesConfig;
  execute: ExecuteConfig;
  surprisal: SurprisalConfig;
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
  claim_id: string;
  hypothesis: string;
  dataset_name: string;
  config_label: string;
  status: Record<Stage, StageState>;
  n_complete: number;
  n_stages: number;
  running: boolean;
  n_universes: number | null;
  coverage: number | null;
  support_rate: number | null;
  fragility: number | null;
  joint_surprisal: number | null;
  created_at: string;
}

export interface DatasetRow {
  name: string;
  path?: string;
  csv_path?: string;
  kind?: string;
  n_rows: number | null;
  n_columns: number | null;
  columns?: string[];
  description?: string | null;
  research_questions?: string[];
  research_question?: string | null;
  n_claims?: number;
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
  joint_surprisal: number | null;
  fragility: number | null;
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

export interface AppSettings {
  default_experiment: RunConfig;
  review_before_execute: boolean;
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
