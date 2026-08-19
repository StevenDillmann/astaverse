import type { Stage } from "./types";

export const STAGE_LABELS: Record<Stage, string> = {
  study: "Profile",
  plans: "Plans",
  decisions: "Decisions",
  universes: "Universes",
  task: "Task",
  execute: "Execute",
  verdicts: "Verdicts",
  surprisal: "Surprisal",
};

export const STAGE_DESCRIPTIONS: Record<Stage, string> = {
  study: "Read the dataset",
  plans: "Generate valid approaches",
  decisions: "Extract analytic forks",
  universes: "Instantiate the grid",
  task: "Package the agent brief",
  execute: "Run the multiverse",
  verdicts: "Apply decision rules",
  surprisal: "Update belief",
};

export function formatDate(value?: string | null) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

export function formatPercent(value?: number | null) {
  return value == null ? "—" : `${Math.round(value * 100)}%`;
}
