import type { Stage } from "./types";

export const STAGE_LABELS: Record<Stage, string> = {
  study: "Profile",
  plans: "Plans",
  decisions: "Decisions",
  universes: "Universes",
  task: "Task",
  execute: "Execute",
  verdicts: "Verdicts",
  conclusion: "Conclusion",
  refinement: "Refinement",
};

export const STAGE_DESCRIPTIONS: Record<Stage, string> = {
  study: "Read the dataset",
  plans: "Generate valid approaches",
  decisions: "Extract analytic forks",
  universes: "Instantiate the grid",
  task: "Package the agent brief",
  execute: "Run the multiverse",
  verdicts: "Apply decision rules",
  conclusion: "Synthesize the answer",
  refinement: "Split an underspecified hypothesis",
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
  // NaN and Infinity reach here as a share with an empty denominator — a run
  // where no universe produced a testable result. That is "no percentage", not
  // a number, so it renders as a dash like any other missing value.
  return value == null || !Number.isFinite(value) ? "—" : `${Math.round(value * 100)}%`;
}

/**
 * The short id a person reads and retypes — EXP-00014.
 *
 * The number is assigned once at creation and never reused, so it is stable
 * across deletions. The timestamp form is the fallback for a run made before
 * numbering existed and not yet backfilled.
 */
export function formatExperimentId(runId: string, number?: number | null) {
  if (number != null) return `EXP-${String(number).padStart(5, "0")}`;
  const [timestamp = runId, slug = ""] = runId.split("__", 2);
  const duplicate = slug.match(/-(\d+)$/)?.[1];
  return `EXP-${timestamp}${duplicate ? `-${duplicate.padStart(2, "0")}` : ""}`;
}

/** An empty universe cap means the whole grid, not zero universes. */
export function parseCap(value: string) {
  const trimmed = value.trim();
  if (!trimmed) return null;
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) ? parsed : null;
}

/**
 * A CSV of the selected rows, for pasting into a sheet.
 *
 * Quoting is the full rule rather than a comma check: hypothesis text contains
 * quotes and newlines often enough that a naive join corrupts the file.
 */
export function toCsv(headers: string[], rows: Array<Array<string | number | null>>) {
  const cell = (value: string | number | null) => {
    const text = value == null ? "" : String(value);
    return /["\n,]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
  };
  return [headers, ...rows].map((row) => row.map(cell).join(",")).join("\n");
}

/** Hand the browser a file. Local app, so a blob download is the whole story. */
export function downloadText(filename: string, text: string, type = "text/csv") {
  const url = URL.createObjectURL(new Blob([text], { type: `${type};charset=utf-8` }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

/** Clipboard write, reporting failure rather than throwing (it needs a secure origin). */
export async function copyText(text: string) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}

/** A filename stamp — 20260909-1757 — so exports sort by when they were taken. */
export function stamp(date = new Date()) {
  const pad = (value: number) => String(value).padStart(2, "0");
  return (
    `${date.getFullYear()}${pad(date.getMonth() + 1)}${pad(date.getDate())}` +
    `-${pad(date.getHours())}${pad(date.getMinutes())}`
  );
}
