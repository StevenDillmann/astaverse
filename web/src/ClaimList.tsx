/** Home: every claim, with how its attempts came out.
 *
 * Claims rather than runs, because a re-run under a different configuration is
 * another attempt at the same question, not a different question. Grouping
 * them is what makes "did my attempts agree?" answerable at a glance.
 */

import { useMemo, useState } from "react";
import { Plus, Search } from "lucide-react";
import type { ClaimDetail } from "./api";
import { Button, Card, Empty, Eyebrow, Tag, cn } from "./ui";

type Filter = "all" | "multiple" | "fragile" | "running";

const fmt = (v: number | null | undefined, d = 3) =>
  v === null || v === undefined ? "—" : v.toFixed(d);

export function ClaimList({
  claims,
  onOpen,
  onNew,
}: {
  claims: ClaimDetail[];
  onOpen: (id: string) => void;
  onNew: () => void;
}) {
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<Filter>("all");

  const isFragile = (c: ClaimDetail) =>
    c.attempts.some((a) => (a.fragility ?? 0) > 0.1);
  const isRunning = (c: ClaimDetail) => c.attempts.some((a) => a.running);

  const counts = useMemo(
    () => ({
      all: claims.length,
      multiple: claims.filter((c) => c.n_attempts > 1).length,
      fragile: claims.filter(isFragile).length,
      running: claims.filter(isRunning).length,
    }),
    [claims],
  );

  const shown = claims.filter((c) => {
    if (filter === "multiple" && c.n_attempts < 2) return false;
    if (filter === "fragile" && !isFragile(c)) return false;
    if (filter === "running" && !isRunning(c)) return false;
    if (!query) return true;
    const needle = query.toLowerCase();
    return (
      c.hypothesis.toLowerCase().includes(needle) ||
      c.dataset_name.toLowerCase().includes(needle)
    );
  });

  const FILTERS: { id: Filter; label: string }[] = [
    { id: "all", label: "All" },
    { id: "multiple", label: "Compared" },
    { id: "fragile", label: "Fragile" },
    { id: "running", label: "Running" },
  ];

  return (
    <>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="relative min-w-[240px] flex-1">
          <Search
            size={13}
            className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground"
          />
          <input
            className="w-full rounded-md border border-input bg-background py-1.5 pl-7 pr-2.5 text-[13px] placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            placeholder="Search hypothesis or dataset"
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
          <Plus size={13} /> New claim
        </Button>
      </div>

      <Card>
        {shown.length === 0 ? (
          <Empty>
            {claims.length === 0
              ? "No claims yet. Create one, or run `astaverse new` in the terminal."
              : "Nothing matches that filter."}
          </Empty>
        ) : (
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-border">
                {["Claim", "Dataset", "Attempts", "Fragility", "Agreement"].map((h) => (
                  <th key={h} className="px-4 py-2.5">
                    <Eyebrow>{h}</Eyebrow>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {shown.map((c) => {
                const range = c.fragility_range;
                return (
                  <tr
                    key={c.id}
                    onClick={() => onOpen(c.id)}
                    className="cursor-pointer border-b border-border/60 last:border-0 hover:bg-accent/60"
                  >
                    <td className="max-w-[52ch] px-4 py-3">
                      <span className="line-clamp-2 text-[13px] leading-snug">{c.hypothesis}</span>
                    </td>
                    <td className="px-4 py-3">
                      <Tag>{c.dataset_name}</Tag>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1.5">
                        <span className="tabular font-mono text-[12px]">{c.n_attempts}</span>
                        {c.attempts.some((a) => a.running) && (
                          <Tag tone="multiverse">running</Tag>
                        )}
                      </div>
                      <span className="mt-0.5 block font-mono text-[10px] text-muted-foreground">
                        {c.attempts
                          .map((a) => a.mode ?? "default")
                          .filter((m, i, arr) => arr.indexOf(m) === i)
                          .join(", ")}
                      </span>
                    </td>
                    <td className="tabular px-4 py-3 font-mono text-[12px]">
                      {range
                        ? range.min === range.max
                          ? fmt(range.min)
                          : `${fmt(range.min)}–${fmt(range.max)}`
                        : "—"}
                    </td>
                    <td className="px-4 py-3">
                      {c.agreement === "disagree" ? (
                        <Tag tone="single">disagree</Tag>
                      ) : c.agreement === "agree" ? (
                        <Tag tone="ok">agree</Tag>
                      ) : (
                        <span className="text-xs text-muted-foreground">—</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </Card>
    </>
  );
}
