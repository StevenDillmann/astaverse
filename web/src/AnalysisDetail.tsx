/** One analysis: what it is, how it is configured, and how to run it.
 *
 * The pipeline is the operating surface — this is a tool for running things,
 * so the stages and their state come first. Results live inside the stage
 * that produced them, a click away, rather than dominating the page.
 */

import { useCallback, useEffect, useState } from "react";
import { ArrowLeft, Play, RotateCw } from "lucide-react";
import { STAGES, getProgress, getRun, runAll, runStage } from "./api";
import type { RunDetail, RunProgress, Stage } from "./api";
import { ConfigForm } from "./ConfigForm";
import { Files } from "./Files";
import { StagePanel } from "./StagePanel";
import { Button, Card, Empty, ErrorNote, Tabs, Tag, cn } from "./ui";

const CAPTION: Record<Stage, string> = {
  study: "Hypothesis and dataset",
  plans: "Independently sampled plans",
  decisions: "The analytic forks",
  universes: "The decision grid",
  task: "Executable Harbor task",
  execute: "Sweep every universe",
  verdicts: "Verdicts, and which decisions flip them",
  surprisal: "One belief update, plus how fragile it is",
};

export function AnalysisDetail({ id, onBack }: { id: string; onBack: () => void }) {
  const [detail, setDetail] = useState<RunDetail | null>(null);
  const [stage, setStage] = useState<Stage>("study");
  const [tab, setTab] = useState("pipeline");
  const [progress, setProgress] = useState<RunProgress | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setDetail(await getRun(id));
  }, [id]);

  useEffect(() => {
    refresh().catch((e) => setError(e.message));
  }, [refresh]);

  // Poll only while a sequence is in flight; each stage writes its artifact as
  // it finishes, so the pipeline fills in as you watch.
  useEffect(() => {
    if (!progress?.running) return;
    const timer = setInterval(async () => {
      try {
        const p = await getProgress(id);
        setProgress(p);
        await refresh();
        if (p.finished && p.error) setError(`${p.failed}: ${p.error}`);
      } catch {
        /* transient; the next tick retries */
      }
    }, 2000);
    return () => clearInterval(timer);
  }, [id, progress?.running, refresh]);

  if (!detail) return <Empty>{error ?? "Loading…"}</Empty>;

  const config = (detail.manifest.config as any) ?? {};
  const target = String(config.through ?? "universes");
  const spends = STAGES.indexOf(target as Stage) >= STAGES.indexOf("execute");
  const status = detail.status;
  const state = status[stage];

  async function start() {
    if (
      spends &&
      !window.confirm(
        `Run through "${target}"?\n\nThis target includes execute, which launches a coding ` +
          `agent in a container. It takes minutes and costs money.`,
      )
    )
      return;
    setError(null);
    try {
      setProgress(await runAll(id));
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function runOne() {
    if (
      stage === "execute" &&
      !window.confirm("Run the Harbor task for real? This launches an agent and costs money.")
    )
      return;
    setBusy(true);
    setError(null);
    try {
      await runStage(id, stage);
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="mb-5 flex items-start gap-4">
        <Button variant="ghost" size="sm" onClick={onBack} className="mt-0.5 shrink-0">
          <ArrowLeft size={13} /> Claim
        </Button>
        <div className="min-w-0">
          <h1 className="max-w-[80ch] text-[17px] font-medium leading-snug">
            {String(detail.manifest.hypothesis ?? "")}
          </h1>
          <p className="mt-1 truncate font-mono text-[11px] text-muted-foreground">
            {String(detail.manifest.dataset ?? "")}
          </p>
        </div>
      </div>

      <div className="mb-5 flex flex-wrap items-center gap-3">
        <Tabs
          tabs={[
            { id: "pipeline", label: "Pipeline" },
            { id: "configure", label: "Configure" },
            { id: "artifacts", label: "Artifacts" },
          ]}
          value={tab}
          onChange={setTab}
        />
        <div className="ml-auto flex items-center gap-2">
          <span className="font-mono text-[11px] text-muted-foreground">
            {progress?.running
              ? `${progress.current ?? "starting"}…`
              : `through ${target}`}
          </span>
          <Button variant="primary" onClick={start} disabled={!!progress?.running}>
            <Play size={12} /> {progress?.running ? "Running…" : "Run"}
          </Button>
        </div>
      </div>

      {error && <ErrorNote>{error}</ErrorNote>}

      {tab === "configure" && (
        <Card className="p-5">
          <ConfigForm analysisId={id} onSaved={() => refresh()} />
        </Card>
      )}

      {tab === "artifacts" && (
        <Card className="p-5">
          <Files runId={id} />
        </Card>
      )}

      {tab === "pipeline" && (
        <>
          <nav className="mb-5 flex overflow-x-auto" aria-label="Stages">
            {STAGES.map((s, i) => {
              const active = progress?.running && progress.current === s;
              return (
                <button
                  key={s}
                  onClick={() => setStage(s)}
                  className={cn(
                    "relative min-w-[104px] flex-1 border border-r-0 border-border px-3 py-2.5 text-left transition-colors first:rounded-l-lg last:rounded-r-lg last:border-r",
                    stage === s ? "bg-foreground text-background" : "bg-card hover:bg-accent",
                    active && "ring-1 ring-inset ring-multiverse",
                  )}
                >
                  <span
                    className={cn(
                      "absolute right-2.5 top-2.5 h-1.5 w-1.5 rounded-full",
                      active
                        ? "animate-pulse bg-multiverse"
                        : status[s] === "complete"
                          ? "bg-ok"
                          : status[s] === "ready"
                            ? "bg-multiverse"
                            : "bg-border",
                    )}
                  />
                  <span className="block font-mono text-[10px] opacity-60">
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  <span className="mt-0.5 block font-mono text-[12px]">{s}</span>
                </button>
              );
            })}
          </nav>

          <Card>
            <div className="flex items-center justify-between gap-4 border-b border-border px-5 py-3.5">
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="font-mono text-[13px] font-semibold uppercase tracking-widest">
                    {stage}
                  </h2>
                  {state === "complete" && <Tag tone="ok">complete</Tag>}
                  {state === "ready" && <Tag tone="multiverse">ready</Tag>}
                </div>
                <p className="mt-0.5 text-xs text-muted-foreground">{CAPTION[stage]}</p>
              </div>
              <Button
                onClick={runOne}
                disabled={busy || !!progress?.running || state === "pending"}
              >
                {state === "complete" ? <RotateCw size={12} /> : <Play size={12} />}
                {busy ? "Running…" : state === "complete" ? "Re-run" : "Run stage"}
              </Button>
            </div>
            <div className="p-5">
              {state === "complete" && (
                <p className="mb-3 text-xs text-muted-foreground">
                  Re-running supersedes every stage after this one; the old artifacts move to
                  history rather than being deleted.
                </p>
              )}
              <StagePanel stage={stage} artifact={detail.artifacts[stage]} />
            </div>
          </Card>
        </>
      )}
    </>
  );
}
