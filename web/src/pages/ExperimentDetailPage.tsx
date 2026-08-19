import {
  ArrowLeft,
  Check,
  ChevronDown,
  FileCode2,
  GitBranch,
  Play,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import {
  Badge,
  CommandBlock,
  ErrorState,
  Loading,
  Metric,
  PageHeader,
  StageRail,
} from "../components";
import { navigate, useAsync } from "../hooks";
import type { ExperimentDetail, Stage } from "../types";
import { formatPercent, STAGE_LABELS } from "../ui";

type Tab = "results" | "decisions" | "universes" | "artifacts" | "history";

export function ExperimentDetailPage({ id }: { id: string }) {
  const { data, error, loading, reload } = useAsync(() => api.experiment(id), [id]);
  const [tab, setTab] = useState<Tab>("results");
  const [actionError, setActionError] = useState<string | null>(null);
  const [acting, setActing] = useState(false);
  const [advanced, setAdvanced] = useState(false);

  useEffect(() => {
    if (!data?.progress?.running) return;
    const timer = window.setInterval(() => void reload(), 1800);
    return () => window.clearInterval(timer);
  }, [data?.progress?.running, reload]);

  if (loading || !data) return <Loading label="Loading experiment" />;
  if (error) return <ErrorState message={error} retry={reload} />;

  const runAction = async (action: () => Promise<unknown>) => {
    setActing(true);
    setActionError(null);
    try {
      await action();
      await reload();
    } catch (reason) {
      setActionError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setActing(false);
    }
  };

  const targetIndex = data.stages.indexOf(data.config.through);
  const reviewNeeded =
    data.review_before_execute &&
    !data.decision_reviewed_at &&
    data.status.decisions === "complete" &&
    targetIndex > data.stages.indexOf("decisions");
  const finished = data.status[data.config.through] === "complete";
  const current = data.progress?.current || null;

  return (
    <>
      <button className="back-link" onClick={() => navigate(`/hypotheses/${data.claim_id}`)}>
        <ArrowLeft size={15} /> Hypothesis
      </button>
      <PageHeader
        eyebrow={`${datasetName(data.dataset)} · ${methodLabel(data.config.decisions.mode)}`}
        title={data.hypothesis}
        description={`Experiment ${shortId(data.id)}`}
        actions={
          reviewNeeded ? (
            <button
              className="button primary"
              disabled={acting}
              onClick={() => {
                const confirmed = confirmExecution(data, data.config.through);
                if (confirmed == null) return;
                void runAction(async () => {
                  await api.approve(id);
                  await api.run(id, data.config.through, false, confirmed);
                });
              }}
            >
              <ShieldCheck size={16} /> Approve decisions and continue
            </button>
          ) : !finished && !data.progress?.running ? (
            <button
              className="button primary"
              disabled={acting}
              onClick={() => {
                const confirmed = confirmExecution(data, data.config.through);
                if (confirmed == null) return;
                void runAction(() => api.run(id, data.config.through, false, confirmed));
              }}
            >
              <Play size={16} /> Continue experiment
            </button>
          ) : data.progress?.running ? (
            <Badge tone="multiverse">Running {current ? STAGE_LABELS[current] : "pipeline"}</Badge>
          ) : (
            <Badge tone="ok">
              <Check size={13} /> Complete
            </Badge>
          )
        }
      />

      {actionError && <div className="error-block">{actionError}</div>}
      {data.progress?.failed && (
        <div className="failure-banner">
          <div>
            <strong>Failed at {STAGE_LABELS[data.progress.failed]}</strong>
            <span>{data.progress.error}</span>
          </div>
          <button
            className="button secondary"
            disabled={acting}
            onClick={() => {
              const failed = data.progress!.failed!;
              const confirmed = confirmExecution(data, failed);
              if (confirmed == null) return;
              void runAction(() => api.runStage(id, failed, confirmed));
            }}
          >
            <RefreshCw size={15} /> Retry stage
          </button>
        </div>
      )}

      <section className="experiment-pipeline-panel">
        <div className="pipeline-heading">
          <div>
            <span className="section-label">Pipeline</span>
            <h2>{reviewNeeded ? "Decision space ready for review" : pipelineMessage(data)}</h2>
          </div>
          <span className="mono-note">{data.config.through}</span>
        </div>
        <StageRail stages={data.commands.planned_stages} status={data.status} current={current} compact />
      </section>

      <nav className="subnav" aria-label="Experiment sections">
        {(["results", "decisions", "universes", "artifacts", "history"] as Tab[]).map((item) => (
          <button key={item} className={tab === item ? "active" : ""} onClick={() => setTab(item)}>
            {item}
          </button>
        ))}
      </nav>

      {tab === "results" && <ResultsView experiment={data} />}
      {tab === "decisions" && <DecisionsView artifact={data.artifacts.decisions} reviewNeeded={reviewNeeded} />}
      {tab === "universes" && <UniversesView artifact={data.artifacts.universes} />}
      {tab === "artifacts" && <ArtifactsView id={id} command={data.commands.run} />}
      {tab === "history" && <HistoryView history={data.history} />}

      <section className="advanced-section">
        <button className="advanced-toggle" onClick={() => setAdvanced(!advanced)}>
          <span>
            <strong>Advanced controls</strong>
            <small>Run or reproduce individual stages.</small>
          </span>
          <ChevronDown className={advanced ? "rotated" : ""} size={17} />
        </button>
        {advanced && (
          <div className="advanced-content">
            {data.stages.map((stage) => (
              <div className="stage-command-row" key={stage}>
                <span>
                  <strong>{STAGE_LABELS[stage]}</strong>
                  <small>{data.status[stage]}</small>
                </span>
                <code>{data.commands.stages[stage]}</code>
                <button
                  className="button secondary small"
                  disabled={acting || data.progress?.running}
                  onClick={() => {
                    const confirmed = confirmExecution(data, stage);
                    if (confirmed == null) return;
                    void runAction(() => api.runStage(id, stage, confirmed));
                  }}
                >
                  Run
                </button>
              </div>
            ))}
          </div>
        )}
      </section>
    </>
  );
}

function ResultsView({ experiment }: { experiment: ExperimentDetail }) {
  const verdicts = asRecord(experiment.artifacts.verdicts);
  const results = Array.isArray(verdicts?.results)
    ? verdicts.results.flatMap((value) => {
        const result = asRecord(value);
        return result ? [result] : [];
      })
    : [];
  const usable = results.filter((result) => asRecord(result?.stats)?.estimate_standardized != null);
  const supported = results.filter((result) => result?.verdict === "supported").length;
  const flips = Array.isArray(verdicts?.decision_flips)
    ? verdicts.decision_flips.map(asRecord).filter(Boolean)
    : [];

  if (!results.length) {
    return (
      <div className="empty-result">
        <GitBranch size={23} />
        <h2>Results will collect here</h2>
        <p>The specification curve appears after execution statistics are converted to verdicts.</p>
      </div>
    );
  }

  return (
    <div className="results-layout">
      <section className="section-block span-2">
        <div className="section-heading">
          <div>
            <span className="section-label">Specification curve</span>
            <h2>Standardized estimates across universes</h2>
          </div>
          <Badge tone="multiverse">{usable.length} estimates</Badge>
        </div>
        <SpecificationCurve results={usable} />
        <div className="curve-legend">
          <span><i className="supported-dot" /> Supported</span>
          <span><i className="unsupported-dot" /> Not supported</span>
          <span><i className="default-mark" /> Default universe</span>
        </div>
      </section>
      <aside className="section-block">
        <div className="result-metrics">
          <Metric label="Support rate" value={formatPercent(supported / results.length)} />
          <Metric label="Universes" value={new Set(results.map((result) => result?.universe_id)).size} />
          <Metric label="Verdicts" value={results.length} detail="including post-hoc rules" />
        </div>
        <div className="decision-flips">
          <span className="section-label">Most consequential</span>
          {flips.slice(0, 5).map((flip) => (
            <div key={String(flip?.decision_id)}>
              <span>{String(flip?.decision_id || "").replaceAll("_", " ")}</span>
              <strong>{formatPercent(Number(flip?.flip_rate || 0))}</strong>
            </div>
          ))}
        </div>
      </aside>
    </div>
  );
}

function SpecificationCurve({ results }: { results: Array<Record<string, unknown>> }) {
  const points = useMemo(
    () =>
      results
        .map((result) => ({
          estimate: Number(asRecord(result.stats)?.estimate_standardized),
          verdict: String(result.verdict),
          isDefault: Boolean(result.is_default),
        }))
        .filter((point) => Number.isFinite(point.estimate))
        .sort((a, b) => a.estimate - b.estimate),
    [results],
  );
  const values = points.map((point) => point.estimate);
  const min = Math.min(0, ...values);
  const max = Math.max(0, ...values);
  const span = max - min || 1;
  const x = (index: number) => 34 + (index / Math.max(points.length - 1, 1)) * 732;
  const y = (value: number) => 188 - ((value - min) / span) * 152;
  const zero = y(0);

  return (
    <svg className="spec-curve" viewBox="0 0 800 220" role="img" aria-label="Sorted standardized estimates">
      <line x1="28" x2="772" y1={zero} y2={zero} className="zero-line" />
      {points.map((point, index) => (
        <g key={`${point.estimate}-${index}`}>
          <line x1={x(index)} x2={x(index)} y1={zero} y2={y(point.estimate)} className="stem" />
          <circle
            cx={x(index)}
            cy={y(point.estimate)}
            r={point.isDefault ? 5.5 : 3.4}
            className={`${point.verdict === "supported" ? "point-supported" : "point-unsupported"} ${point.isDefault ? "point-default" : ""}`}
          />
        </g>
      ))}
      <text x="28" y={zero - 7}>0</text>
      <text x="28" y="17">{max.toFixed(2)}</text>
      <text x="28" y="211">{min.toFixed(2)}</text>
    </svg>
  );
}

function DecisionsView({ artifact, reviewNeeded }: { artifact: unknown; reviewNeeded: boolean }) {
  const spec = asRecord(artifact);
  const decisions = asRecord(spec?.decisions);
  if (!decisions) return <Unavailable label="Decision space" />;
  return (
    <section className="section-block">
      <div className="section-heading">
        <div>
          <span className="section-label">ASTRA specification</span>
          <h2>{Object.keys(decisions).length} analytic decisions</h2>
        </div>
        {reviewNeeded && <Badge tone="warn">Review required</Badge>}
      </div>
      <div className="decision-list">
        {Object.entries(decisions).map(([id, raw]) => {
          const decision = asRecord(raw);
          const options = asRecord(decision?.options) || {};
          return (
            <article key={id}>
              <div className="decision-header">
                <div>
                  <code>{id}</code>
                  <h3>{String(decision?.label || id)}</h3>
                </div>
                <Badge>{Object.keys(options).length} options</Badge>
              </div>
              <p>{String(decision?.rationale || "")}</p>
              <div className="option-list">
                {Object.entries(options).map(([optionId, optionRaw]) => {
                  const option = asRecord(optionRaw);
                  return (
                    <div key={optionId} className={decision?.default === optionId ? "default" : ""}>
                      <span>{decision?.default === optionId ? "Default" : "Option"}</span>
                      <strong>{String(option?.label || optionId)}</strong>
                      <small>{String(option?.description || "")}</small>
                    </div>
                  );
                })}
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}

function UniversesView({ artifact }: { artifact: unknown }) {
  const set = asRecord(artifact);
  const universes = Array.isArray(set?.universes) ? set.universes.map(asRecord).filter(Boolean) : [];
  if (!universes.length) return <Unavailable label="Universes" />;
  return (
    <section className="section-block">
      <div className="section-heading">
        <div>
          <span className="section-label">Instantiated grid</span>
          <h2>{universes.length} universes</h2>
        </div>
        <Badge>{Number(set?.n_total_grid || universes.length)} total combinations</Badge>
      </div>
      <div className="universe-table">
        {universes.map((universe) => {
          const choices = asRecord(universe?.decisions) || {};
          return (
            <div key={String(universe?.id)}>
              <code>{String(universe?.id)}</code>
              <span>{Object.entries(choices).map(([key, value]) => `${key}=${String(value)}`).join(" · ")}</span>
              {universe?.is_default ? <Badge tone="single">Default</Badge> : null}
            </div>
          );
        })}
      </div>
    </section>
  );
}

function ArtifactsView({ id, command }: { id: string; command: string }) {
  const { data, error, loading } = useAsync(() => api.files(id), [id]);
  const [selected, setSelected] = useState<string | null>(null);
  const file = useAsync(
    () => (selected ? api.file(id, selected) : Promise.resolve(null)),
    [id, selected],
  );
  return (
    <div className="artifact-layout">
      <section className="section-block">
        <div className="section-heading">
          <div>
            <span className="section-label">Files</span>
            <h2>Experiment artifacts</h2>
          </div>
          <FileCode2 size={18} />
        </div>
        {loading ? (
          <Loading label="Indexing artifacts" />
        ) : error ? (
          <ErrorState message={error} />
        ) : (
          <div className="file-list">
            {(data || []).map((entry) => (
              <button
                key={entry.path}
                className={selected === entry.path ? "selected" : ""}
                onClick={() => setSelected(entry.path)}
              >
                <span>{entry.name}</span>
                <small>{entry.category} · {Math.ceil(entry.bytes / 1024)} KB</small>
              </button>
            ))}
          </div>
        )}
      </section>
      <section className="section-block artifact-preview">
        {selected ? (
          file.loading ? (
            <Loading label="Reading file" />
          ) : file.error ? (
            <ErrorState message={file.error} />
          ) : (
            <>
              <span className="section-label">{selected}</span>
              <pre>{file.data?.content}</pre>
            </>
          )
        ) : (
          <>
            <span className="section-label">Reproduce</span>
            <h2>Exact experiment command</h2>
            <CommandBlock command={command} />
          </>
        )}
      </section>
    </div>
  );
}

function HistoryView({ history }: { history: Array<Record<string, unknown>> }) {
  if (!history.length) return <Unavailable label="Superseded artifact history" />;
  return (
    <section className="section-block">
      <div className="section-heading">
        <div>
          <span className="section-label">Audit trail</span>
          <h2>Superseded artifacts</h2>
        </div>
      </div>
      <pre className="json-preview">{JSON.stringify(history, null, 2)}</pre>
    </section>
  );
}

function Unavailable({ label }: { label: string }) {
  return (
    <div className="empty-result">
      <GitBranch size={22} />
      <h2>{label} not available yet</h2>
      <p>Continue the experiment pipeline to produce this artifact.</p>
    </div>
  );
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function datasetName(path: string) {
  return path.replace(/\/$/, "").split("/").pop() || path;
}

function shortId(id: string) {
  return id.split("__")[0] || id;
}

function methodLabel(method: string) {
  return {
    sample_plans: "Sample plans",
    audit_plan: "Audit one plan",
    direct: "Direct extraction",
  }[method] || method;
}

function pipelineMessage(experiment: ExperimentDetail) {
  if (experiment.progress?.running && experiment.progress.current) {
    return `Running ${STAGE_LABELS[experiment.progress.current].toLowerCase()}`;
  }
  if (experiment.status[experiment.config.through] === "complete") return "Experiment complete";
  return "Ready to continue";
}

function confirmExecution(experiment: ExperimentDetail, target: Stage | string): boolean | null {
  const billable =
    !experiment.config.execute.dry_run &&
    ["execute", "verdicts", "surprisal"].includes(target);
  if (!billable) return false;
  return window.confirm(
    `Continue with up to ${experiment.config.universes.cap} universes using ${experiment.config.execute.agent}? This launches billable coding agents.`,
  )
    ? true
    : null;
}
