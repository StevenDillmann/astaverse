/** Start an analysis: pick the data, then say what you think is true of it.
 *
 * A BLADE dataset carries one published research question, but AutoDiscovery
 * has generated hundreds against the same data, each with the plan it
 * produced. Picking one of those seeds stage 2 with that plan, so the
 * decision space describes the plan under evaluation rather than one invented
 * from scratch — which is the mode that matters for evaluating AutoDiscovery.
 */

import { useEffect, useState } from "react";
import { Search } from "lucide-react";
import { createSeededRun, listDatasets, listHypotheses } from "./api";
import type { DatasetInfo, PlanRecord } from "./api";
import { Button, Card, Empty, ErrorNote, Eyebrow, Input, Tag, cn } from "./ui";

export function NewRun({
  onCreated,
  onCancel,
}: {
  onCreated: (id: string) => void;
  onCancel: () => void;
}) {
  const [datasets, setDatasets] = useState<DatasetInfo[]>([]);
  const [selected, setSelected] = useState<DatasetInfo | null>(null);
  const [hypothesis, setHypothesis] = useState("");
  const [filter, setFilter] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [records, setRecords] = useState<PlanRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [hypFilter, setHypFilter] = useState("");
  const [seed, setSeed] = useState<PlanRecord | null>(null);

  useEffect(() => {
    listDatasets().then(setDatasets).catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    if (!selected) return;
    listHypotheses(selected.name, hypFilter)
      .then((r) => {
        setRecords(r.hypotheses);
        setTotal(r.total);
      })
      .catch(() => {
        setRecords([]);
        setTotal(0);
      });
  }, [selected, hypFilter]);

  const shown = datasets.filter(
    (d) =>
      !filter ||
      d.name.includes(filter.toLowerCase()) ||
      d.research_questions.join(" ").toLowerCase().includes(filter.toLowerCase()),
  );

  async function create() {
    if (!selected || !hypothesis.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const { id } = await createSeededRun(
        hypothesis.trim(),
        selected.path,
        seed ? { seed_dataset: seed.dataset, seed_normalized_id: seed.normalized_id } : undefined,
      );
      onCreated(id);
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  }

  return (
    <>
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <Eyebrow>New analysis</Eyebrow>
          <h1 className="mt-1 text-[17px] font-medium">
            Pick the data, then say what you think is true of it.
          </h1>
        </div>
        <Button onClick={onCancel}>Cancel</Button>
      </div>

      {error && <ErrorNote>{error}</ErrorNote>}

      <div className="grid gap-8 lg:grid-cols-2">
        <section>
          <Eyebrow className="mb-2">
            Dataset {datasets.length > 0 && `· ${shown.length} of ${datasets.length}`}
          </Eyebrow>
          <div className="relative mb-2">
            <Search
              size={13}
              className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground"
            />
            <Input
              className="pl-7"
              placeholder="Filter by name or research question"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
            />
          </div>
          <Card className="max-h-[460px] overflow-y-auto">
            {datasets.length === 0 && !error && <Empty>Looking for datasets…</Empty>}
            {shown.map((d) => (
              <button
                key={d.path}
                onClick={() => {
                  setSelected(d);
                  setSeed(null);
                  setHypFilter("");
                  if (!hypothesis.trim() && d.research_questions[0])
                    setHypothesis(d.research_questions[0]);
                }}
                className={cn(
                  "block w-full border-b border-border/60 px-4 py-3 text-left last:border-0 transition-colors",
                  selected?.path === d.path
                    ? "bg-accent"
                    : "hover:bg-accent/60",
                )}
              >
                <span className="font-mono text-[13px]">{d.name}</span>
                <span className="mt-0.5 block font-mono text-[11px] text-muted-foreground">
                  {d.n_rows ?? "?"} rows · {d.n_columns} cols
                  {(d as any).n_autodiscovery_hypotheses > 0 &&
                    ` · ${(d as any).n_autodiscovery_hypotheses} hypotheses`}
                </span>
                {d.research_questions[0] && (
                  <span className="mt-1.5 block text-xs leading-relaxed text-muted-foreground">
                    {d.research_questions[0]}
                  </span>
                )}
              </button>
            ))}
          </Card>
        </section>

        <section>
          <Eyebrow className="mb-2">Hypothesis</Eyebrow>
          <textarea
            rows={5}
            className="w-full rounded-md border border-input bg-background px-2.5 py-2 text-[13px] placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            placeholder="A claim the data can bear on, stated so it could turn out false."
            value={hypothesis}
            onChange={(e) => setHypothesis(e.target.value)}
          />

          {seed && (
            <p className="mt-2 rounded-md border-l-2 border-multiverse bg-multiverse/5 px-3 py-2 text-xs leading-relaxed text-multiverse">
              Seeded with AutoDiscovery plan <code className="font-mono">{seed.normalized_id}</code>.
              Stage 2 keeps this plan verbatim and samples alternatives against it.{" "}
              <button className="underline" onClick={() => setSeed(null)}>
                Clear
              </button>
            </p>
          )}

          {selected && (
            <>
              {selected.research_questions.length > 0 && (
                <>
                  <Eyebrow className="mb-1.5 mt-5">Published research question</Eyebrow>
                  {selected.research_questions.map((q, i) => (
                    <button
                      key={i}
                      onClick={() => {
                        setHypothesis(q);
                        setSeed(null);
                      }}
                      className="mb-1 block w-full rounded-md border border-border px-3 py-2 text-left text-xs leading-relaxed text-muted-foreground transition-colors hover:border-multiverse hover:text-foreground"
                    >
                      {q}
                    </button>
                  ))}
                </>
              )}

              {total > 0 && (
                <>
                  <Eyebrow className="mb-1 mt-5">
                    AutoDiscovery hypotheses · {records.length} of {total}
                  </Eyebrow>
                  <p className="mb-2 text-xs text-muted-foreground">
                    Each carries the plan AutoDiscovery wrote for it.
                  </p>
                  <Input
                    className="mb-2"
                    placeholder="Filter hypotheses"
                    value={hypFilter}
                    onChange={(e) => setHypFilter(e.target.value)}
                  />
                  <Card className="max-h-[300px] overflow-y-auto">
                    {records.map((r) => (
                      <button
                        key={r.normalized_id}
                        onClick={() => {
                          setSeed(r);
                          setHypothesis(r.hypothesis);
                        }}
                        className={cn(
                          "block w-full border-b border-border/60 px-3 py-2 text-left last:border-0 transition-colors",
                          seed?.normalized_id === r.normalized_id
                            ? "bg-accent"
                            : "hover:bg-accent/60",
                        )}
                      >
                        <span className="block font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                          {r.normalized_id}
                          {r.level != null && ` · depth ${r.level}`}
                          {!r.success && " · failed"}
                        </span>
                        <span className="mt-0.5 block text-xs leading-relaxed text-muted-foreground">
                          {r.hypothesis}
                        </span>
                      </button>
                    ))}
                    {records.length === 0 && <Empty>No hypotheses match that filter.</Empty>}
                  </Card>
                </>
              )}

              <Eyebrow className="mb-1.5 mt-5">Columns</Eyebrow>
              <div className="flex flex-wrap gap-1">
                {selected.columns.map((c) => (
                  <Tag key={c}>{c}</Tag>
                ))}
              </div>
            </>
          )}

          <div className="mt-6 flex items-center gap-3">
            <Button
              variant="primary"
              disabled={!selected || !hypothesis.trim() || busy}
              onClick={create}
            >
              {busy ? "Creating…" : "Create analysis"}
            </Button>
            {!selected && (
              <span className="text-xs text-muted-foreground">Select a dataset to continue.</span>
            )}
          </div>
        </section>
      </div>
    </>
  );
}
