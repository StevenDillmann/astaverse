/** The tool's main screen: every analysis, its state, and what to do next.
 *
 * A dense table rather than cards, because the useful questions are
 * comparative — which of these finished, which stalled, which is running —
 * and those are answered by scanning a column, not by reading tiles.
 */

import { useMemo, useState } from "react";
import { Plus, Search } from "lucide-react";
import { STAGES } from "./api";
import type { RunSummary, Stage } from "./api";
import { Button, Card, Empty, Eyebrow, Input, Tag, cn } from "./ui";

type Filter = "all" | "running" | "complete" | "unfinished";

function StageTrack({ status, running }: { status: Record<Stage, string>; running?: boolean }) {
  return (
    <span className="flex items-center gap-[3px]" title={STAGES.map((s) => `${s}: ${status[s]}`).join("\n")}>
      {STAGES.map((s) => (
        <i
          key={s}
          className={cn(
            "h-1.5 w-3 rounded-[1px]",
            status[s] === "complete"
              ? "bg-ok"
              : status[s] === "ready"
                ? running
                  ? "animate-pulse bg-multiverse"
                  : "bg-multiverse/40"
                : "bg-border",
          )}
        />
      ))}
    </span>
  );
}

export function AnalysisList({
  analyses,
  onOpen,
  onNew,
}: {
  analyses: RunSummary[];
  onOpen: (id: string) => void;
  onNew: () => void;
}) {
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<Filter>("all");

  const counts = useMemo(
    () => ({
      all: analyses.length,
      running: analyses.filter((a) => a.running).length,
      complete: analyses.filter((a) => a.n_complete === STAGES.length).length,
      unfinished: analyses.filter((a) => a.n_complete < STAGES.length && !a.running).length,
    }),
    [analyses],
  );

  const shown = analyses.filter((a) => {
    if (filter === "running" && !a.running) return false;
    if (filter === "complete" && a.n_complete !== STAGES.length) return false;
    if (filter === "unfinished" && (a.n_complete === STAGES.length || a.running)) return false;
    if (!query) return true;
    const needle = query.toLowerCase();
    return (
      a.hypothesis?.toLowerCase().includes(needle) ||
      a.dataset?.toLowerCase().includes(needle) ||
      a.id.toLowerCase().includes(needle)
    );
  });

  const FILTERS: { id: Filter; label: string }[] = [
    { id: "all", label: "All" },
    { id: "running", label: "Running" },
    { id: "unfinished", label: "Unfinished" },
    { id: "complete", label: "Complete" },
  ];

  return (
    <>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="relative min-w-[240px] flex-1">
          <Search
            size={13}
            className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground"
          />
          <Input
            className="pl-7"
            placeholder="Search hypothesis, dataset, or id"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>

        <div className="flex items-center gap-1 rounded-md border border-border p-0.5">
          {FILTERS.map((f) => (
            <button
              key={f.id}
              onClick={() => setFilter(f.id)}
              className={cn(
                "rounded px-2.5 py-1 text-xs transition-colors",
                filter === f.id
                  ? "bg-accent text-foreground"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {f.label}
              <span className="ml-1.5 font-mono text-[11px] opacity-70">{counts[f.id]}</span>
            </button>
          ))}
        </div>

        <Button variant="primary" onClick={onNew}>
          <Plus size={13} /> New analysis
        </Button>
      </div>

      <Card>
        {shown.length === 0 ? (
          <Empty>
            {analyses.length === 0
              ? "No analyses yet. Create one, or run `astaverse new` in the terminal."
              : "Nothing matches that filter."}
          </Empty>
        ) : (
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-border">
                {["Hypothesis", "Dataset", "Progress", "Created"].map((h) => (
                  <th key={h} className="px-4 py-2.5">
                    <Eyebrow>{h}</Eyebrow>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {shown.map((a) => (
                <tr
                  key={a.id}
                  onClick={() => onOpen(a.id)}
                  className="cursor-pointer border-b border-border/60 last:border-0 hover:bg-accent/60"
                >
                  <td className="max-w-[46ch] px-4 py-3">
                    <span className="line-clamp-2 text-[13px] leading-snug">{a.hypothesis}</span>
                    <span className="mt-1 block font-mono text-[11px] text-muted-foreground">
                      {a.id.slice(0, 13)}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <Tag>{a.dataset?.split("/").pop() || "—"}</Tag>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <StageTrack status={a.status} running={a.running} />
                      <span className="tabular font-mono text-[11px] text-muted-foreground">
                        {a.n_complete}/{STAGES.length}
                      </span>
                      {a.running && <Tag tone="multiverse">running</Tag>}
                    </div>
                  </td>
                  <td className="px-4 py-3 font-mono text-[11px] text-muted-foreground">
                    {a.created_at?.slice(0, 16).replace("T", " ") || "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </>
  );
}
