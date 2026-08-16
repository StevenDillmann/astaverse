import { useCallback, useEffect, useState } from "react";
import { STAGES, getRun, listRuns, runStage } from "./api";
import type { RunDetail, RunSummary, Stage } from "./api";
import { Files } from "./Files";
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
  const [view, setView] = useState<"pipeline" | "files" | "new">("pipeline");

  useEffect(() => {
    listRuns()
      .then((r) => {
        setRuns(r);
        if (r.length && !runId) setRunId(r[0].run_id);
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
            key={r.run_id}
            className="run-item"
            aria-current={r.run_id === runId && view !== "new"}
            onClick={() => {
              setRunId(r.run_id);
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
              {r.n_complete}/{STAGES.length} · {r.run_id.slice(0, 13)}
            </span>
          </button>
        ))}
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
              <button aria-current={view === "files"} onClick={() => setView("files")}>
                Artifacts &amp; history
              </button>
            </div>

            {view === "files" ? (
              <section className="panel">
                <div className="panel-body">
                  <Files runId={detail.run_id} />
                </div>
              </section>
            ) : (
              <>
            <nav className="track" aria-label="Pipeline stages">
              {STAGES.map((s, i) => (
                <button
                  key={s}
                  className="node"
                  aria-current={s === stage}
                  onClick={() => setStage(s)}
                >
                  <span className={`dot ${status?.[s] ?? "pending"}`} />
                  <span className="idx">{String(i + 1).padStart(2, "0")}</span>
                  <span className="name">{s}</span>
                </button>
              ))}
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
