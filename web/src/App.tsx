import { useCallback, useEffect, useState } from "react";
import { STAGES, getProgress, getRun, listRuns, runAll, runStage } from "./api";
import type { RunDetail, RunProgress, RunSummary, Stage } from "./api";
import { Config } from "./Config";
import { Files } from "./Files";
import { ThemeSwitch } from "./ThemeSwitch";
import { NewRun } from "./NewRun";
import { StagePanel } from "./StagePanel";
import "./styles.css";

const STAGE_CAPTION: Record<Stage, string> = {
  study: "Hypothesis and dataset",
  plans: "Independently sampled plans",
  decisions: "Where the plans disagree",
  universes: "The decision grid",
  task: "Executable Harbor task",
  execute: "Sweep every universe",
  verdicts: "Verdicts, and which decisions flip them",
  surprisal: "One belief update, plus how fragile it is",
};

export default function App() {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [runId, setRunId] = useState<string | null>(null);
  const [detail, setDetail] = useState<RunDetail | null>(null);
  const [stage, setStage] = useState<Stage>("study");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<"pipeline" | "config" | "files" | "new">("pipeline");
  const [progress, setProgress] = useState<RunProgress | null>(null);

  useEffect(() => {
    listRuns()
      .then((r) => {
        setRuns(r);
        if (r.length && !runId) setRunId(r[0].id);
      })
      .catch((e) => setError(e.message));
  }, [runId]);

  const refresh = useCallback(async (id: string) => {
    const d = await getRun(id);
    setDetail(d);
    return d;
  }, []);

  useEffect(() => {
    if (runId) refresh(runId).catch((e) => setError(e.message));
  }, [runId, refresh]);

  // While a sequential run is in flight, poll for progress and keep the stage
  // panel current — each stage writes its artifact as it completes, so the
  // pipeline fills in as you watch.
  useEffect(() => {
    if (!runId || !progress?.running) return;
    const timer = setInterval(async () => {
      try {
        const p = await getProgress(runId);
        setProgress(p);
        await refresh(runId);
        if (p.finished) {
          setRuns(await listRuns());
          if (p.error) setError(`${p.failed}: ${p.error}`);
        }
      } catch {
        /* transient; the next tick retries */
      }
    }, 2500);
    return () => clearInterval(timer);
  }, [runId, progress?.running, refresh]);

  async function startRunAll() {
    if (!runId || !detail) return;
    const target = String((detail.manifest.config as any)?.through ?? "universes");
    const spends = STAGES.indexOf(target as Stage) >= STAGES.indexOf("execute");
    if (
      spends &&
      !window.confirm(
        `Run all stages through "${target}"?\n\nThis target includes execute, which ` +
          `launches a coding agent in a container. It takes minutes and costs money.`,
      )
    )
      return;
    setError(null);
    try {
      setProgress(await runAll(runId));
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function execute() {
    if (!runId) return;
    // `execute` launches a real agent in a container and bills for it. Every
    // other stage is cheap and idempotent; this one is neither.
    if (stage === "execute") {
      const n = (detail?.artifacts.universes as any)?.universes?.length ?? "?";
      if (
        !window.confirm(
          `Run the Harbor task for real?\n\nThis launches a coding agent in a ` +
            `container to sweep ${n} universes. It takes many minutes and costs money.`,
        )
      )
        return;
    }
    setBusy(true);
    setError(null);
    try {
      await runStage(runId, stage);
      await refresh(runId);
      setRuns(await listRuns());
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const status = detail?.status;
  const state = status?.[stage];
  const isComplete = state === "complete";
  const canRun = state === "complete" || state === "ready";

  return (
    <div className="shell">
      <aside className="rail">
        <div className="brand">
          <h1>Astaverse</h1>
          <span>multiverse</span>
        </div>
        <button
          className="new-btn"
          aria-current={view === "new"}
          onClick={() => setView("new")}
        >
          + New study
        </button>

        <p className="eyebrow">Studies</p>
        {runs.length === 0 && <p className="empty">None yet.</p>}
        {runs.map((r) => (
          <button
            key={r.id}
            className="run-item"
            aria-current={r.id === runId && view !== "new"}
            onClick={() => {
              setRunId(r.id);
              setView("pipeline");
            }}
          >
            <span className="hyp">{r.hypothesis}</span>
            <span className="meta">
              <span className="pips" aria-hidden="true">
                {STAGES.map((s) => (
                  <i key={s} className={r.status[s] === "complete" ? "on" : ""} />
                ))}
              </span>
              {r.n_complete}/{STAGES.length} · {r.id.slice(0, 13)}
            </span>
          </button>
        ))}

        <ThemeSwitch />
      </aside>

      <main className="main">
        {view === "new" ? (
          <NewRun
            onCancel={() => setView("pipeline")}
            onCreated={async (id) => {
              setRuns(await listRuns());
              setRunId(id);
              setStage("study");
              setView("pipeline");
            }}
          />
        ) : detail ? (
          <>
            <h2 className="hypothesis">{String(detail.manifest.hypothesis ?? "")}</h2>
            <p className="dataset-line">{String(detail.manifest.dataset ?? "")}</p>

            <div className="tabs">
              <button
                aria-current={view === "pipeline"}
                onClick={() => setView("pipeline")}
              >
                Pipeline
              </button>
              <button aria-current={view === "config"} onClick={() => setView("config")}>
                Configure
              </button>
              <button aria-current={view === "files"} onClick={() => setView("files")}>
                Artifacts &amp; history
              </button>
            </div>

            {view === "config" ? (
              <section className="panel">
                <div className="panel-body">
                  <Config runId={detail.id} onSaved={() => refresh(detail.id)} />
                </div>
              </section>
            ) : view === "files" ? (
              <section className="panel">
                <div className="panel-body">
                  <Files runId={detail.id} />
                </div>
              </section>
            ) : (
              <>
            <div className="runbar">
              <div>
                <button
                  className="run-btn"
                  onClick={startRunAll}
                  disabled={!!progress?.running}
                >
                  {progress?.running ? "Running…" : "Run all"}
                </button>
                <span className="empty" style={{ marginLeft: 12 }}>
                  through{" "}
                  <code>{String((detail.manifest.config as any)?.through ?? "universes")}</code>,
                  using the saved configuration. Already-complete stages are skipped.
                </span>
              </div>
              {progress && (
                <span className="empty">
                  {progress.running
                    ? `${progress.current ?? "starting"} · ${progress.done?.length ?? 0}/${
                        (progress.done?.length ?? 0) + (progress.pending?.length ?? 0) + 1
                      }`
                    : progress.failed
                      ? `failed at ${progress.failed}`
                      : "finished"}
                </span>
              )}
            </div>

            <nav className="track" aria-label="Pipeline stages">
              {STAGES.map((s, i) => {
                const active = progress?.running && progress.current === s;
                return (
                  <button
                    key={s}
                    className={`node${active ? " is-active" : ""}`}
                    aria-current={s === stage}
                    onClick={() => setStage(s)}
                  >
                    <span
                      className={`dot ${active ? "active" : (status?.[s] ?? "pending")}`}
                    />
                    <span className="idx">{String(i + 1).padStart(2, "0")}</span>
                    <span className="name">{s}</span>
                  </button>
                );
              })}
            </nav>

            <section className="panel">
              <div className="panel-head">
                <div>
                  <h2>{stage}</h2>
                  <p className="empty" style={{ margin: "4px 0 0" }}>
                    {STAGE_CAPTION[stage]}
                  </p>
                </div>
                <button className="run-btn" onClick={execute} disabled={busy || !canRun}>
                  {busy ? "Running…" : isComplete ? "Re-run" : "Run"}
                </button>
              </div>
              <div className="panel-body">
                {error && <div className="error">{error}</div>}
                {isComplete && (
                  <p className="empty" style={{ marginBottom: 12 }}>
                    Re-running discards every stage after this one.
                  </p>
                )}
                <StagePanel stage={stage} artifact={detail.artifacts[stage]} />
              </div>
            </section>
              </>
            )}
          </>
        ) : (
          <p className="empty">{error ?? "Select a study, or create one."}</p>
        )}
      </main>
    </div>
  );
}
