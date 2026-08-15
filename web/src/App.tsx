import { useCallback, useEffect, useState } from "react";
import { STAGES, getRun, listRuns, runStage } from "./api";
import type { RunDetail, RunSummary, Stage } from "./api";
import { StagePanel } from "./StagePanel";
import "./styles.css";

const STAGE_CAPTION: Record<Stage, string> = {
  study: "Hypothesis and dataset",
  plans: "Independently sampled plans",
  decisions: "Where the plans disagree",
  universes: "The decision grid",
  task: "Executable Harbor task",
  execute: "Sweep every universe",
  verdicts: "Statistics become verdicts",
  surprisal: "Surprisal as a distribution",
};

export default function App() {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [runId, setRunId] = useState<string | null>(null);
  const [detail, setDetail] = useState<RunDetail | null>(null);
  const [stage, setStage] = useState<Stage>("study");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
        <p className="eyebrow">Runs</p>
        {runs.length === 0 && (
          <p className="empty">
            No runs yet. Create one with <code>astaverse new</code>.
          </p>
        )}
        {runs.map((r) => (
          <button
            key={r.run_id}
            className="run-item"
            aria-current={r.run_id === runId}
            onClick={() => setRunId(r.run_id)}
          >
            <span className="hyp">{r.hypothesis}</span>
            <span className="meta">
              {r.n_complete}/{STAGES.length} stages · {r.run_id.slice(0, 13)}
            </span>
          </button>
        ))}
      </aside>

      <main className="main">
        {detail ? (
          <>
            <h2 className="hypothesis">{String(detail.manifest.hypothesis ?? "")}</h2>
            <p className="dataset-line">{String(detail.manifest.dataset ?? "")}</p>

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
        ) : (
          <p className="empty">{error ?? "Select a run."}</p>
        )}
      </main>
    </div>
  );
}
