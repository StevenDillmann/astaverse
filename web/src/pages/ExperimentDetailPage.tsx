import {
  ArrowLeft,
  Check,
  ChevronDown,
  FileCode2,
  GitBranch,
  Play,
  RefreshCw,
  ShieldCheck,
  Trash2,
} from "lucide-react";
import { type ReactNode, useEffect, useMemo, useState } from "react";
import { api } from "../api";
import {
  ArchiveRow,
  Badge,
  CommandBlock,
  DatasetCard,
  ErrorState,
  Loading,
  PageHeader,
  Tabs,
} from "../components";
import { navigate, useAsync, useBackTarget } from "../hooks";
import type { ExperimentDetail, Stage } from "../types";
import {
  formatExperimentId,
  formatPercent,
  STAGE_DESCRIPTIONS,
  STAGE_LABELS,
} from "../ui";

export function ExperimentDetailPage({ id }: { id: string }) {
  const { data, error, loading, reload } = useAsync(() => api.experiment(id), [id]);
  const back = useBackTarget();
  const [actionError, setActionError] = useState<string | null>(null);
  const [acting, setActing] = useState(false);

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
  const remove = async () => {
    if (!window.confirm("Permanently delete this experiment and all of its artifacts?")) {
      return;
    }
    setActing(true);
    setActionError(null);
    try {
      const result = await api.deleteExperiment(id);
      navigate(`/hypotheses/${result.hypothesis_id}`);
    } catch (reason) {
      setActionError(reason instanceof Error ? reason.message : String(reason));
      setActing(false);
    }
  };

  const targetIndex = data.stages.indexOf(data.config.through);
  const finished = data.status[data.config.through] === "complete";
  // The gate only matters while there is something downstream left to run.
  const reviewNeeded =
    data.review_before_execute &&
    !data.decision_reviewed_at &&
    !finished &&
    data.status.decisions === "complete" &&
    targetIndex > data.stages.indexOf("decisions");
  const current = data.progress?.current || null;

  return (
    <div className="experiment-detail-page">
      <button
        className="back-link"
        onClick={() => back.go(`/hypotheses/${data.claim_id}`)}
      >
        <ArrowLeft size={15} /> {back.label ?? "Hypothesis"}
      </button>
      <PageHeader
        eyebrow={`Experiment · ${formatExperimentId(data.id, data.number)}`}
        title={data.hypothesis}
        description={
          <span className="dataset-description">
            <span className="dataset-metadata">
              <small>
                <span>Dataset</span>
                <strong>{datasetName(data.dataset)}</strong>
              </small>
              <small>
                <span>Method</span>
                <strong>{methodLabel(data.config.decisions.mode)}</strong>
              </small>
              <small>
                <span>Critique</span>
                <strong>{data.config.decisions.critique ? "On" : "Off"}</strong>
              </small>
              <small>
                <span>Cap</span>
                <strong>{data.config.universes.cap}</strong>
              </small>
              <small>
                <span>Universes</span>
                <strong>{universeCount(data.artifacts.universes) ?? "—"}</strong>
              </small>
              <small>
                <span>Decisions</span>
                <strong>{decisionCount(data.artifacts.decisions) ?? "—"}</strong>
              </small>
              <small>
                <span>Stages</span>
                <strong>
                  {data.stages.filter((stage) => data.status[stage] === "complete").length}/
                  {data.stages.length}
                </strong>
              </small>
            </span>
          </span>
        }
        actions={
          <>
            {!finished && !data.progress?.running ? (
              <button
                className="button execute"
                disabled={acting}
                onClick={() => {
                  const confirmed = confirmThrough(data, data.config.through);
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
            )}
          </>
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
              const confirmed = confirmStage(data, failed);
              if (confirmed == null) return;
              void runAction(() => api.runStage(id, failed, confirmed));
            }}
          >
            <RefreshCw size={15} /> Retry stage
          </button>
        </div>
      )}

      <Headline experiment={data} />

      <ResultsView experiment={data} />

      <Section
        title="Pipeline"
        defaultOpen
        meta={<span className="mono-note">through {data.config.through}</span>}
      >
        <p className="muted-copy curve-caption">
          {reviewNeeded
            ? "Decision space ready for review. Running past decisions is held until it is approved."
            : pipelineMessage(data)}
        </p>
        {/* One tab per stage: its status, the command that runs it, its own Run
            control, and whatever output that stage produced. */}
        <Tabs
          initial={current || "decisions"}
          tabs={data.stages.map((stage) => ({
            id: stage,
            label: STAGE_LABELS[stage],
            panel: (
              <div className="stage-panel">
                <div className="stage-panel-head">
                  <span className="stage-panel-status">
                    <strong>{STAGE_DESCRIPTIONS[stage]}</strong>
                    <small>{data.status[stage] || "pending"}</small>
                  </span>
                  <button
                    className="button secondary small"
                    disabled={acting || data.progress?.running}
                    onClick={() => {
                      const confirmed = confirmStage(data, stage);
                      if (confirmed == null) return;
                      void runAction(() => api.runStage(id, stage, confirmed));
                    }}
                  >
                    Run {STAGE_LABELS[stage].toLowerCase()}
                  </button>
                </div>
                <code className="stage-panel-command">{data.commands.stages[stage]}</code>
                {stage === "decisions" && reviewNeeded && (
                  <div className="stage-panel-gate">
                    <span>
                      Running past this stage is held until the decision space is approved.
                    </span>
                    <button
                      className="button secondary small"
                      disabled={acting}
                      onClick={() => void runAction(() => api.approve(id))}
                    >
                      <ShieldCheck size={16} /> Approve decision space
                    </button>
                  </div>
                )}
                <StageOutput stage={stage} data={data} reviewNeeded={reviewNeeded} />
              </div>
            ),
          }))}
        />
      </Section>
      <Section title="Artifacts">
        <ArtifactsView id={id} command={data.commands.run} />
      </Section>
      <Section title="History" count={data.history.length || null}>
        <HistoryView history={data.history} />
      </Section>

      <ArchiveRow
        kind="experiment"
        id={data.id}
        label="experiment"
        note="Deleting permanently removes this run and all generated artifacts."
      >
        <button
          className="button danger"
          disabled={acting || Boolean(data.progress?.running)}
          onClick={() => void remove()}
        >
          <Trash2 size={16} /> Delete experiment
        </button>
      </ArchiveRow>
    </div>
  );
}

function ConclusionEvidence({ artifact }: { artifact: unknown }) {
  const conclusion = asRecord(artifact);
  if (!conclusion) return null;

  const evidence = stringList(conclusion.key_evidence);
  const caveats = stringList(conclusion.caveats);
  const dimensions = stringList(conclusion.refinement_dimensions);
  const suggestions = stringList(conclusion.suggested_hypotheses);
  const requiresRefinement = conclusion.requires_refinement === true;
  if (
    evidence.length === 0 &&
    caveats.length === 0 &&
    !requiresRefinement
  ) {
    return null;
  }

  return (
    <>
      <p className="conclusion-rationale">{String(conclusion.rationale || "")}</p>
      {evidence.length > 0 && (
        <ul className="conclusion-evidence">
          {evidence.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      )}
      {requiresRefinement && (
        <div className="conclusion-refinement">
          <strong>Hypothesis refinement</strong>
          <p>{String(conclusion.refinement_reason || "")}</p>
          {dimensions.length > 0 && (
            <p>
              <strong>Dimensions:</strong> {dimensions.join(", ")}
            </p>
          )}
          {suggestions.length > 0 && (
            <ol>
              {suggestions.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ol>
          )}
        </div>
      )}
      {caveats.length > 0 && (
        <div className="conclusion-caveats">
          <strong>Caveats</strong>
          <ul>
            {caveats.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      )}
    </>
  );
}

/** What a stage produced, for the stage's own tab in the pipeline. */
function StageOutput({
  stage,
  data,
  reviewNeeded,
}: {
  stage: Stage;
  data: ExperimentDetail;
  reviewNeeded: boolean;
}) {
  if (stage === "study")
    return <DatasetView artifact={data.artifacts.study} dataset={data.dataset} />;
  if (stage === "decisions")
    return <DecisionsView artifact={data.artifacts.decisions} reviewNeeded={reviewNeeded} />;
  if (stage === "universes") return <UniversesView artifact={data.artifacts.universes} />;
  if (stage === "conclusion")
    return <ConclusionEvidence artifact={data.artifacts.conclusion} />;
  if (stage === "refinement") return <RefinementView artifact={data.artifacts.refinement} />;
  if (!data.artifacts[stage])
    return <p className="muted-copy">This stage has not produced an artifact yet.</p>;
  return (
    <p className="muted-copy">
      No dedicated view for this stage — its artifact is listed under Artifacts.
    </p>
  );
}

/** Successor hypotheses proposed when the parent combined distinct claims. */
function RefinementView({ artifact }: { artifact: unknown }) {
  const refinement = asRecord(artifact);
  if (!refinement) return null;
  if (!refinement.needed) {
    return (
      <p className="muted-copy">
        No refinement needed — the hypothesis answers a single question.
      </p>
    );
  }
  const hypotheses = Array.isArray(refinement.hypotheses)
    ? refinement.hypotheses.map(asRecord).filter(Boolean)
    : [];
  const dimensions = stringList(refinement.dimensions);
  return (
    <>
      <p className="conclusion-rationale">{String(refinement.reason || "")}</p>
      {dimensions.length > 0 && (
        <p className="muted-copy">
          <strong>Dimensions:</strong> {dimensions.join(" · ")}
        </p>
      )}
      <ol className="refinement-list">
        {hypotheses.map((item, index) => (
          <li key={index}>
            <strong>{String(item?.hypothesis || "")}</strong>
            <p className="muted-copy">{String(item?.rationale || "")}</p>
            <div className="refinement-pins">
              {(Array.isArray(item?.pins) ? item.pins.map(asRecord) : []).map((pin, i) =>
                pin ? (
                  <code key={i}>
                    {String(pin.decision_id)} = {String(pin.option_id)}
                  </code>
                ) : null,
              )}
            </div>
            <small className="muted-copy">
              {item?.directional ? "Directional claim" : "Non-directional claim"}
              {item?.answerable_with_dataset === false
                ? " · needs data this dataset does not carry"
                : ""}
            </small>
          </li>
        ))}
      </ol>
    </>
  );
}

/** The conclusion, before any of the working that produced it. */
export function Headline({ experiment }: { experiment: ExperimentDetail }) {
  const verdicts = asRecord(experiment.artifacts.verdicts);
  const conclusion = asRecord(experiment.artifacts.conclusion);
  const summary = asRecord(verdicts?.curve_summary);
  const rawResults = Array.isArray(verdicts?.results) ? verdicts.results : [];
  const results = oneResultPerUniverse(
    rawResults.flatMap((value) => {
      const result = asRecord(value);
      return result ? [result] : [];
    }),
  );
  if (!results.length) return null;

  let positiveSignificant = 0;
  let negativeSignificant = 0;
  let notSignificant = 0;
  // Universes that produced no test: `untested` still has an estimate (a
  // descriptive quantity with no null hypothesis), `failed` produced nothing.
  let untested = 0;
  let failed = 0;
  results.forEach((result) => {
    const stats = asRecord(result.stats);
    const estimate =
      finiteNumber(stats?.estimate_standardized) ?? finiteNumber(stats?.estimate);
    const pValue = finiteNumber(stats?.p_value);
    if (stats?.converged === false || estimate == null) {
      failed += 1;
    } else if (pValue == null) {
      untested += 1;
    } else if (pValue >= significanceThreshold(String(result.verdict_rule || "")) || estimate === 0) {
      notSignificant += 1;
    } else if (estimate > 0) {
      positiveSignificant += 1;
    } else {
      negativeSignificant += 1;
    }
  });
  const total = results.length;
  // Shares are of the testable set: a universe that was never tested is not
  // evidence either way, so including it in the denominator understates every
  // share by the coverage rate.
  const testable = positiveSignificant + negativeSignificant + notSignificant;
  const sensitiveDecisions = (
    Array.isArray(verdicts?.decision_sensitivity)
      ? verdicts.decision_sensitivity.map(asRecord).filter(Boolean)
      : []
  )
    .filter(
      (row) =>
        Number(row?.n_pairs || 0) > 0 &&
        finiteNumber(row?.normalized_effect_change) != null,
    )
    .sort(
      (a, b) =>
        (finiteNumber(b?.normalized_effect_change) ?? 0) -
        (finiteNumber(a?.normalized_effect_change) ?? 0),
    )
    .slice(0, 3);
  return (
    <section className="headline-strip">
      <div className="headline-metric headline-positive">
        <strong>{formatPercent(positiveSignificant / testable)}</strong>
        <small>Positive significant</small>
      </div>
      <div className="headline-metric headline-negative">
        <strong>{formatPercent(negativeSignificant / testable)}</strong>
        <small>Negative significant</small>
      </div>
      <div className="headline-metric headline-neutral">
        <strong>{formatPercent(notSignificant / testable)}</strong>
        <small>Not significant</small>
      </div>
      <div className="headline-metric">
        <strong>{formatEstimate(summary?.median)}</strong>
        <small>median effect</small>
      </div>
      <div className="headline-metric headline-sensitive">
        <div className="headline-sensitive-values">
          {sensitiveDecisions.length > 0 ? (
            sensitiveDecisions.map((row) => {
              const id = String(row?.decision_id || "");
              return (
                <span key={id}>
                  <span>{id.replaceAll("_", " ")}</span>
                  <strong>{formatSensitivity(row?.normalized_effect_change)}×</strong>
                </span>
              );
            })
          ) : (
            <span className="headline-sensitive-empty">—</span>
          )}
        </div>
        <small>Most sensitive decisions</small>
      </div>
      {(untested > 0 || failed > 0) && (
        <p className="headline-coverage">
          <strong>{testable}</strong> of {total} universes testable
          {untested > 0 && <> · {untested} estimated but not tested</>}
          {failed > 0 && <> · {failed} produced no estimate</>}
        </p>
      )}
      {conclusion && (
        <div className="headline-conclusion">
          <div>
            <small>Conclusion</small>
            <strong
              className={`conclusion-status status-${String(
                conclusion.evidence_status || "inconclusive",
              )}`}
            >
              {String(conclusion.evidence_status || "inconclusive").replaceAll(
                "_",
                " ",
              )}
            </strong>
          </div>
          <p>{String(conclusion.answer || "")}</p>
        </div>
      )}
    </section>
  );
}

/** The collapsible block the dataset and hypothesis pages are built from. */
function Section({
  title,
  count,
  meta,
  defaultOpen = false,
  children,
}: {
  title: string;
  count?: number | null;
  meta?: ReactNode;
  defaultOpen?: boolean;
  children: ReactNode;
}) {
  // Always open: the page is two areas — Results and Pipeline — and each uses
  // tabs internally, so a second layer of collapsing only hid things.
  void defaultOpen;
  return (
    <section className="section-block">
      <div className="section-heading">
        <h2>
          {title}
          {count == null ? "" : ` (${count})`}
        </h2>
        {meta && <div className="section-actions">{meta}</div>}
      </div>
      <div className="section-preview">{children}</div>
    </section>
  );
}

function decisionCount(artifact: unknown) {
  const decisions = asRecord(asRecord(artifact)?.decisions);
  return decisions ? Object.keys(decisions).length : null;
}

function universeCount(artifact: unknown) {
  const universes = asRecord(artifact)?.universes;
  return Array.isArray(universes) ? universes.length : null;
}

function ResultsView({ experiment }: { experiment: ExperimentDetail }) {
  const verdicts = asRecord(experiment.artifacts.verdicts);
  const results = Array.isArray(verdicts?.results)
    ? verdicts.results.flatMap((value) => {
        const result = asRecord(value);
        return result ? [result] : [];
      })
    : [];
  const specifications = oneResultPerUniverse(results);
  const artifactSummary = asRecord(verdicts?.curve_summary);
  const candidates = specifications.filter(
    (result) =>
      finiteNumber(asRecord(result.stats)?.estimate_standardized) != null ||
      finiteNumber(asRecord(result.stats)?.estimate) != null,
  );
  const usesStandardized =
    artifactSummary?.scale === "standardized" ||
    (!artifactSummary &&
      candidates.length > 0 &&
      candidates.every(
        (result) => finiteNumber(asRecord(result.stats)?.estimate_standardized) != null,
      ));
  const curveScale: CurveScale = usesStandardized ? "standardized" : "raw";
  const summary = artifactSummary || summarizeCurve(specifications, curveScale);
  const sensitivities = Array.isArray(verdicts?.decision_sensitivity)
    ? verdicts.decision_sensitivity.map(asRecord).filter(Boolean)
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

  const curvePanel = (
    <>
      <p className="muted-copy curve-caption">
          {usesStandardized ? "Standardized estimates" : "Raw estimates"} across universes,
          sorted, with the analytic choices behind each one.{" "}
          <span className="curve-hint">
            Click a universe to pin it, shift-click to compare up to three.
          </span>
        </p>
        {!usesStandardized && (
          <p className="muted-copy">
            This legacy run mixes raw estimate scales; compare direction and inference,
            not vertical magnitude.
          </p>
        )}
        <SpecificationCurve
          results={specifications}
          valueLabel={usesStandardized ? "standardized estimate" : "estimate"}
          scale={curveScale}
        />
        <div className="curve-legend">
          <span><i className="ci-mark" /> 95% confidence interval</span>
          <span><i className="supported-dot" /> Positive significant</span>
          <span><i className="unsupported-dot" /> Negative significant</span>
          <span><i className="indeterminate-dot" /> Not significant</span>
          <span><i className="unavailable-dot" /> Not tested</span>
          <span><i className="default-mark" /> Default universe</span>
        </div>
        <p className="muted-copy curve-density-note">
          The distribution on the right counts universes in the designed grid, not draws
          from a sampling distribution: a decision with more options contributes more
          mass, so read it as the shape of analytic disagreement, never as a probability
          that the effect takes a given value. Bar lengths use a square-root scale, so
          a bar twice as long holds four times as many universes, and the overlaid line
          is a Gaussian kernel density estimate on the same scale — a smoothed reading of
          the bars, not extra evidence.
        </p>
        <p className="muted-copy curve-spread">
          Middle 50% {formatEstimate(summary?.q25)} to {formatEstimate(summary?.q75)} ·{" "}
          {Number(summary?.n_significant_positive || 0)} significant one way,{" "}
          {Number(summary?.n_significant_negative || 0)} the other,{" "}
          {Number(summary?.n_indeterminate || 0)} not significant
      </p>
    </>
  );

  return (
    <Section title="Results" defaultOpen>
      <Tabs
        tabs={[
          { id: "curve", label: "Specification curve", panel: curvePanel },
          {
            id: "sensitivity",
            label: "Decision sensitivity",
            count: sensitivities.filter(Boolean).length || null,
            panel: (
              <DecisionSensitivitySection
                sensitivities={sensitivities}
                unit={usesStandardized ? "SD" : ""}
              />
            ),
          },
          {
            id: "conclusion",
            label: "Conclusion",
            panel: experiment.artifacts.conclusion ? (
              <ConclusionEvidence artifact={experiment.artifacts.conclusion} />
            ) : null,
          },
          {
            id: "refinement",
            label: "Refinement",
            panel: experiment.artifacts.refinement ? (
              <RefinementView artifact={experiment.artifacts.refinement} />
            ) : null,
          },
        ]}
      />
    </Section>
  );
}

type CurveScale = "standardized" | "raw";

/** Beyond three pinned universes the panel stops being readable as a diff. */
const MAX_PINS = 3;

function SpecificationCurve({
  results,
  valueLabel,
  scale,
}: {
  results: Array<Record<string, unknown>>;
  valueLabel: string;
  scale: CurveScale;
}) {
  const points = useMemo(
    () =>
      results
        .map((result) => {
          const estimate = curveEstimate(result, scale);
          const interval = curveInterval(result, scale, estimate);
          return {
            id: String(result.universe_id),
            // Number(null) is 0, which would pin every universe that produced no
            // estimate onto the zero line and read as a null result rather than a
            // missing one. NaN instead, so the filter below drops it.
            estimate: estimate ?? Number.NaN,
            ciLow: interval?.[0] ?? null,
            ciHigh: interval?.[1] ?? null,
            verdict: String(result.verdict),
            pValue: Number(asRecord(result.stats)?.p_value ?? Number.NaN),
            verdictRule: String(result.verdict_rule),
            isDefault: Boolean(result.is_default),
            decisions: Object.fromEntries(
              Object.entries(asRecord(result.decisions) || {}).filter(
                ([decision]) => decision !== "verdict_rule",
              ),
            ),
          };
        })
        .filter((point) => Number.isFinite(point.estimate))
        .sort((a, b) => a.estimate - b.estimate),
    [results, scale],
  );
  const [hovered, setHovered] = useState<number | null>(null);
  // Pinned universes, in click order. Plain click pins one, shift-click adds up
  // to MAX_PINS so specifications can be compared against each other.
  const [pinned, setPinned] = useState<number[]>([]);
  useEffect(() => {
    const close = (event: KeyboardEvent) => {
      if (event.key === "Escape") setPinned([]);
    };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, []);
  if (!points.length) {
    return <p className="muted-copy">No standardized estimates are available.</p>;
  }
  const decisionIds = Array.from(
    points.reduce((set, point) => {
      Object.keys(point.decisions).forEach((decision) => set.add(decision));
      return set;
    }, new Set<string>()),
  );
  const rows: Array<
    | { kind: "header"; decision: string }
    | { kind: "option"; decision: string; option: string }
  > = [];
  decisionIds.forEach((decision) => {
    rows.push({ kind: "header", decision });
    const options = Array.from(
      points.reduce((set, point) => {
        const option = point.decisions[decision];
        if (option != null) set.add(String(option));
        return set;
      }, new Set<string>()),
    ).sort();
    options.forEach((option) => rows.push({ kind: "option", decision, option }));
  });

  const width = 900;
  const labelWidth = 190;
  const padding = 18;
  const curveHeight = 170;
  const rowHeight = 18;
  const matrixTop = padding + curveHeight + 42;
  const height = matrixTop + rows.length * rowHeight + padding;
  const axisX = labelWidth + padding;
  // A marginal distribution shares the value axis on the right. The curve's own
  // x-axis is rank order, so the vertical spread is the finding; this makes its
  // shape — especially multimodality — readable without inferring it from where
  // the sorted line goes flat.
  const densityWidth = 64;
  const densityGap = 16;
  const plotWidth = width - labelWidth - padding * 2 - densityWidth - densityGap;
  const densityX = axisX + plotWidth + densityGap;
  const step = plotWidth / Math.max(points.length, 1);
  const x = (index: number) => axisX + step * (index + 0.5);
  // Thin ticks, as on a conventional specification curve; narrower when dense.
  const markWidth = Math.min(1.2, Math.max(0.5, step * 0.8));
  const estimates = points.map((point) => point.estimate);
  const domainValues = points.flatMap((point) => [
    point.estimate,
    ...(point.ciLow == null ? [] : [point.ciLow]),
    ...(point.ciHigh == null ? [] : [point.ciHigh]),
  ]);
  const min = Math.min(0, ...domainValues);
  const max = Math.max(0, ...domainValues);
  const span = max - min || 1;
  const y = (value: number) =>
    padding + curveHeight - ((value - min) / span) * curveHeight;
  const zero = y(0);
  const median =
    estimates.length % 2
      ? estimates[Math.floor(estimates.length / 2)]
      : (estimates[estimates.length / 2 - 1] + estimates[estimates.length / 2]) / 2;
  // Histogram, not a KDE: the estimates come from a discrete grid of analytic
  // choices, so the distribution is genuinely clumpy and a bandwidth would
  // smooth away the clusters that matter.
  // The value axis spans the CI bounds, which are wider than the estimates, so
  // bin finer than sqrt(n) or the estimates collapse into a couple of bars —
  // but never finer than MIN_BIN_HEIGHT, or the bars become invisible slivers
  // however many universes there are.
  const MIN_BIN_HEIGHT = 6;
  const binCount = Math.min(
    Math.floor(curveHeight / MIN_BIN_HEIGHT),
    Math.max(12, Math.ceil(Math.sqrt(points.length) * 1.8)),
  );
  const binSpan = span / binCount;
  const bins = Array.from({ length: binCount }, () => ({
    "point-supported": 0,
    "point-unsupported": 0,
    "point-indeterminate": 0,
    "point-unavailable": 0,
  }) as Record<string, number>);
  points.forEach((point) => {
    const index = Math.min(
      binCount - 1,
      Math.max(0, Math.floor((point.estimate - min) / binSpan)),
    );
    const key = effectPointClass(point.estimate, point.pValue, point.verdictRule);
    bins[index][key] += 1;
  });
  const binMax = Math.max(1, ...bins.map((bin) => Object.values(bin).reduce((a, b) => a + b, 0)));
  const DENSITY_ORDER = [
    "point-supported",
    "point-unsupported",
    "point-indeterminate",
    "point-unavailable",
  ];

  // A smoothed overlay on the bars. Silverman bandwidth, and the same sqrt
  // transform the bars use, so the curve traces their tops rather than floating
  // on a second scale. Shape only — the underlying design is discrete.
  const kdePath = (() => {
    const values = points.map((point) => point.estimate);
    const n = values.length;
    if (n < 4) return null;
    const mean = values.reduce((a, b) => a + b, 0) / n;
    const sd = Math.sqrt(values.reduce((a, b) => a + (b - mean) ** 2, 0) / Math.max(1, n - 1));
    const sorted = [...values].sort((a, b) => a - b);
    const at = (q: number) => sorted[Math.min(n - 1, Math.max(0, Math.round(q * (n - 1))))];
    const iqr = at(0.75) - at(0.25);
    const candidates = [sd, iqr > 0 ? iqr / 1.34 : Infinity].filter((v) => v > 0 && Number.isFinite(v));
    const spread = candidates.length ? Math.min(...candidates) : span / 10;
    const bandwidth = 0.9 * spread * n ** (-1 / 5);
    if (!(bandwidth > 0)) return null;
    const SAMPLES = 96;
    const grid: Array<{ value: number; density: number }> = [];
    for (let i = 0; i < SAMPLES; i += 1) {
      const value = min + (span * i) / (SAMPLES - 1);
      let density = 0;
      for (const observed of values) {
        const z = (value - observed) / bandwidth;
        density += Math.exp(-0.5 * z * z);
      }
      grid.push({ value, density: density / (n * bandwidth * Math.sqrt(2 * Math.PI)) });
    }
    const peak = Math.max(...grid.map((row) => row.density));
    if (!(peak > 0)) return null;
    return grid
      .map(
        (row, index) =>
          `${index === 0 ? "M" : "L"}${(densityX + Math.sqrt(row.density / peak) * densityWidth).toFixed(2)},${y(row.value).toFixed(2)}`,
      )
      .join(" ");
  })();

  const ticks = niceTicks(min, max);
  const tickStep = ticks.length > 1 ? ticks[1] - ticks[0] : span;
  // Hover traces a specification; the detail box only opens on click.
  // Hover previews while nothing is pinned; once pinned, the panel holds still
  // and hover only traces the guide line.
  const preview = pinned.length === 0 ? hovered : null;
  const shownIndexes = pinned.length ? pinned : preview == null ? [] : [preview];
  const shown = shownIndexes.map((index) => points[index]);
  const lit = new Set<number>(pinned);
  if (hovered != null) lit.add(hovered);
  const togglePin = (index: number, additive: boolean) =>
    setPinned((current) => {
      if (current.includes(index)) return current.filter((pin) => pin !== index);
      if (!additive) return [index];
      const next = [...current, index];
      return next.length > MAX_PINS ? next.slice(next.length - MAX_PINS) : next;
    });

  return (
    <div className="curve-layout">
    <div className="spec-curve-wrap" onMouseLeave={() => setHovered(null)}>
    <svg
      className={`spec-curve${lit.size ? " has-hover" : ""}`}
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label={`Sorted ${valueLabel}s with aligned analytic decisions`}
    >
      <line
        x1={axisX}
        x2={axisX}
        y1={padding}
        y2={padding + curveHeight}
        className="value-axis"
      />
      {ticks.map((tick) => (
        <g key={`tick-${tick}`}>
          <line
            x1={axisX - 4}
            x2={axisX}
            y1={y(tick)}
            y2={y(tick)}
            className="value-axis"
          />
          <text x={axisX - 8} y={y(tick) + 3} textAnchor="end" className="tick-label">
            {formatTick(tick, tickStep)}
          </text>
        </g>
      ))}
      <text
        className="curve-axis-title"
        textAnchor="middle"
        transform={`rotate(-90 ${padding + 4} ${padding + curveHeight / 2})`}
        x={padding + 4}
        y={padding + curveHeight / 2}
      >
        {valueLabel.toUpperCase()}
      </text>
      <line
        x1={axisX}
        x2={width - padding}
        y1={zero}
        y2={zero}
        className="zero-line"
      />
      <line
        x1={axisX}
        x2={width - padding}
        y1={y(median)}
        y2={y(median)}
        className="median-line"
      />

      <text x={axisX} y={padding + curveHeight + 12} className="curve-axis-title">
        UNIVERSES, SORTED BY {valueLabel.toUpperCase()}
      </text>
      {points.map((point, index) => (
        <g key={point.id} className={`curve-point${lit.has(index) ? " is-hovered" : ""}`}>
          {point.ciLow != null && point.ciHigh != null && (
            <>
              <line
                x1={x(index)}
                x2={x(index)}
                y1={y(point.ciLow)}
                y2={y(point.ciHigh)}
                className={`curve-ci ${effectPointClass(point.estimate, point.pValue, point.verdictRule)}`}
              />
              <line
                x1={x(index) - 2.5}
                x2={x(index) + 2.5}
                y1={y(point.ciLow)}
                y2={y(point.ciLow)}
                className={`curve-ci ${effectPointClass(point.estimate, point.pValue, point.verdictRule)}`}
              />
              <line
                x1={x(index) - 2.5}
                x2={x(index) + 2.5}
                y1={y(point.ciHigh)}
                y2={y(point.ciHigh)}
                className={`curve-ci ${effectPointClass(point.estimate, point.pValue, point.verdictRule)}`}
              />
            </>
          )}
          <circle
            cx={x(index)}
            cy={y(point.estimate)}
            r={point.isDefault ? 3.4 : 2.1}
            className={`${effectPointClass(point.estimate, point.pValue, point.verdictRule)} ${point.isDefault ? "point-default" : ""}`}
          />
        </g>
      ))}
      {rows.map((row, rowIndex) => {
        const rowY = matrixTop + rowIndex * rowHeight;
        if (row.kind === "header") {
          return (
            <g key={`header-${row.decision}`}>
              <line
                x1={padding}
                x2={width - padding}
                y1={rowY - rowHeight / 2}
                y2={rowY - rowHeight / 2}
                className="decision-rule"
              />
              <text x={padding} y={rowY + 4} className="decision-heading">
                {row.decision.replaceAll("_", " ").toUpperCase()}
              </text>
            </g>
          );
        }
        return (
          <g key={`${row.decision}-${row.option}`}>
            <text x={labelWidth} y={rowY + 4} textAnchor="end" className="option-label">
              {row.option.replaceAll("_", " ")}
            </text>
            {points.map((point, pointIndex) =>
              String(point.decisions[row.decision]) === row.option ? (
                <line
                  key={point.id}
                  x1={x(pointIndex)}
                  x2={x(pointIndex)}
                  y1={rowY - rowHeight * 0.36}
                  y2={rowY + rowHeight * 0.36}
                  strokeWidth={point.isDefault ? 2.5 : markWidth}
                  className={`${effectPointClass(
                    point.estimate,
                    point.pValue,
                    point.verdictRule,
                  )} decision-mark ${point.isDefault ? "default" : ""} ${
                    lit.has(pointIndex) ? "is-hovered" : ""
                  }`}
                />
              ) : null,
            )}
          </g>
        );
      })}
      {bins.map((bin, index) => {
        const top = y(min + binSpan * (index + 1));
        const bottom = y(min + binSpan * index);
        const barHeight = Math.max(1, bottom - top - 1);
        let offset = densityX;
        return (
          <g key={`bin-${index}`}>
            {DENSITY_ORDER.map((key) => {
              const count = bin[key];
              if (!count) return null;
              // Square-root scale: with hundreds of universes the distribution is
              // usually concentrated, and on a linear scale every bin outside the
              // mode collapses to a sliver. Sqrt keeps the ordering and the mode
              // while making the tails readable.
              const barWidth = Math.max(1.5, Math.sqrt(count / binMax) * densityWidth);
              const x0 = offset;
              offset += barWidth;
              return (
                <rect
                  key={key}
                  x={x0}
                  y={top}
                  width={barWidth}
                  height={barHeight}
                  className={`density-bar ${key}`}
                />
              );
            })}
          </g>
        );
      })}
      {kdePath && <path d={kdePath} className="density-curve" />}
      <text x={densityX} y={padding + curveHeight + 12} className="curve-axis-title">
        DISTRIBUTION
      </text>
      <text x={densityX} y={padding + curveHeight + 24} className="median-label">
        {`MEDIAN ${formatEstimate(median)}`}
      </text>
      {/* Full-height hit columns: the dots are ~2px, far too small to aim at, so
          the whole universe column — curve and decision marks — is the target. */}
      {points.map((point, index) => (
        <rect
          key={`hit-${point.id}`}
          x={x(index) - step / 2}
          y={padding}
          width={step}
          height={height - padding * 2}
          fill="transparent"
          className="curve-hit"
          onMouseEnter={() => setHovered(index)}
          onClick={(event) => togglePin(index, event.shiftKey)}
        />
      ))}
      {[...lit].map((index) => {
        const pin = pinned.indexOf(index);
        return (
          <g key={`guide-${index}`} className="curve-guide-group">
            <line
              x1={x(index)}
              x2={x(index)}
              y1={padding}
              y2={height - padding}
              className={`curve-guide${pin >= 0 ? " is-pinned" : ""}`}
            />
            {pin >= 0 && (
              <>
                <circle cx={x(index)} cy={padding - 1} r={6.5} className="curve-badge" />
                <text x={x(index)} y={padding + 2} className="curve-badge-label">
                  {pin + 1}
                </text>
              </>
            )}
          </g>
        );
      })}
    </svg>
    </div>
    <aside className="curve-detail" data-compare={shown.length > 1 ? "true" : undefined}>
      {shown.length === 0 ? (
        <p className="curve-detail-empty">
          Hover the curve to trace a specification. Click to pin it, shift-click to
          pin up to {MAX_PINS} and compare them.
        </p>
      ) : shown.length === 1 ? (
        <div className="curve-detail-body">
          {pinned.length > 0 && (
            <button
              className="curve-detail-close"
              onClick={() => setPinned([])}
              aria-label="Clear pinned universe"
            >
              ×
            </button>
          )}
          <div className="curve-detail-head">
            <strong>{shown[0].id}</strong>
            <span
              className={`curve-detail-verdict ${effectPointClass(
                shown[0].estimate,
                shown[0].pValue,
                shown[0].verdictRule,
              )}`}
            >
              {inferenceLabel(shown[0])}
            </span>
          </div>
          <dl className="curve-detail-stats">
            <div>
              <dt>Estimate</dt>
              <dd>{shown[0].estimate.toFixed(4)}</dd>
            </div>
            <div>
              <dt>95% CI</dt>
              <dd>{formatCi(shown[0].ciLow, shown[0].ciHigh)}</dd>
            </div>
            <div>
              <dt>p-value</dt>
              <dd>{formatP(shown[0].pValue)}</dd>
            </div>
          </dl>
          {Object.keys(shown[0].decisions).length > 0 && (
            <dl className="curve-detail-decisions">
              {Object.entries(shown[0].decisions).map(([decision, option]) => (
                <div key={decision}>
                  <dt>{decision.replaceAll("_", " ")}</dt>
                  <dd>{String(option).replaceAll("_", " ")}</dd>
                </div>
              ))}
            </dl>
          )}
          {shown[0].isDefault && <p className="curve-detail-note">Default universe</p>}
          <p className="curve-detail-note">
            {pinned.length
              ? "Shift-click another universe to compare."
              : "Click to pin this universe."}
          </p>
        </div>
      ) : (
        <CurveComparison points={shown} onClear={() => setPinned([])} />
      )}
    </aside>
    </div>
  );
}

type CurvePoint = {
  id: string;
  estimate: number;
  ciLow: number | null;
  ciHigh: number | null;
  verdict: string;
  pValue: number;
  verdictRule: string;
  isDefault: boolean;
  decisions: Record<string, unknown>;
};

function formatCi(low: number | null, high: number | null) {
  return low != null && high != null
    ? `[${low.toFixed(4)}, ${high.toFixed(4)}]`
    : "unavailable";
}

function formatP(value: number) {
  if (!Number.isFinite(value)) return "unavailable";
  // Exactly 0 is underflow, never a real p-value: the normal tail drops below
  // the smallest double around z = 38. Saying "< 1e-308" states what is known.
  if (value === 0) return "< 1e-308";
  if (value < 0.0001) return value.toExponential(2);
  return value.toFixed(5);
}

/**
 * Two or three pinned universes, reduced to what actually differs between them:
 * the shared choices are the uninteresting part, so they collapse to a count.
 */
/**
 * Short, but scale-aware: three significant digits. Fixed decimals crowd the
 * columns on large effects and collapse small ones — a 0.0228 estimate with a
 * [0.0224, 0.0231] interval must not all render as "0.03".
 */
function compactNumber(value: number | null) {
  if (value == null || !Number.isFinite(value)) return "—";
  if (value === 0) return "0";
  if (Math.abs(value) >= 1) return value.toFixed(2);
  return value.toPrecision(3);
}

function CurveComparison({
  points,
  onClear,
}: {
  points: CurvePoint[];
  onClear: () => void;
}) {
  const [openDiffering, setOpenDiffering] = useState(true);
  const [openShared, setOpenShared] = useState(true);
  const keys = Array.from(
    new Set(points.flatMap((point) => Object.keys(point.decisions))),
  ).sort();
  const valueOf = (point: CurvePoint, key: string) =>
    point.decisions[key] == null ? "—" : String(point.decisions[key]).replaceAll("_", " ");
  const differing = keys.filter(
    (key) => new Set(points.map((point) => valueOf(point, key))).size > 1,
  );
  const shared = keys.filter((key) => !differing.includes(key));
  const span = points.length + 1;

  const groupHeading = (label: string, open: boolean, toggle: () => void) => (
    <tr>
      <th scope="colgroup" colSpan={span}>
        <button className="curve-compare-group-toggle" onClick={toggle} aria-expanded={open}>
          <span className="curve-compare-caret" aria-hidden="true">
            {open ? "▾" : "▸"}
          </span>
          {label}
        </button>
      </th>
    </tr>
  );

  return (
    <div className="curve-detail-body curve-compare">
      <button className="curve-detail-close" onClick={onClear} aria-label="Clear pinned universes">
        ×
      </button>
      <table className="curve-compare-table">
        {/* One table, so every section stays on the same column grid. */}
        <thead>
          <tr>
            <td />
            {points.map((point, index) => (
              <th key={point.id} scope="col">
                <span className="curve-compare-pin">
                  <span className="curve-compare-badge">{index + 1}</span>
                  <span className="curve-compare-id">{point.id.replace("universe_", "u")}</span>
                </span>
                <span
                  className={`curve-compare-verdict ${effectPointClass(
                    point.estimate,
                    point.pValue,
                    point.verdictRule,
                  )}`}
                >
                  {inferenceLabel(point)}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          <tr>
            <th scope="row">Estimate</th>
            {points.map((point) => (
              <td key={point.id} className="is-number">
                {compactNumber(point.estimate)}
              </td>
            ))}
          </tr>
          <tr>
            <th scope="row">95% CI</th>
            {points.map((point) => (
              <td key={point.id} className="is-number">
                {point.ciLow != null && point.ciHigh != null
                  ? `${compactNumber(point.ciLow)} – ${compactNumber(point.ciHigh)}`
                  : "—"}
              </td>
            ))}
          </tr>
          <tr>
            <th scope="row">p-value</th>
            {points.map((point) => (
              <td key={point.id} className="is-number">
                {formatP(point.pValue)}
              </td>
            ))}
          </tr>
        </tbody>
        <tbody className="curve-compare-group">
          {groupHeading(
            differing.length
              ? `${differing.length} differing choice${differing.length === 1 ? "" : "s"}`
              : "No differing choices",
            openDiffering,
            () => setOpenDiffering(!openDiffering),
          )}
          {openDiffering &&
            differing.map((key) => (
              <tr key={key}>
                <th scope="row">{key.replaceAll("_", " ")}</th>
                {points.map((point) => (
                  <td key={point.id}>{valueOf(point, key)}</td>
                ))}
              </tr>
            ))}
        </tbody>
        {shared.length > 0 && (
          <tbody className="curve-compare-group is-shared">
            {groupHeading(
              `${shared.length} identical choice${shared.length === 1 ? "" : "s"}`,
              openShared,
              () => setOpenShared(!openShared),
            )}
            {openShared &&
              shared.map((key) => (
                <tr key={key}>
                  <th scope="row">{key.replaceAll("_", " ")}</th>
                  <td colSpan={points.length}>{valueOf(points[0], key)}</td>
                </tr>
              ))}
          </tbody>
        )}
      </table>
      <p className="curve-detail-note">Shift-click to add another, Escape to clear.</p>
    </div>
  );
}

/** Tick values on a 1/2/5 x 10^n lattice, so labels read as round numbers. */
function niceTicks(min: number, max: number, count = 5) {
  if (!Number.isFinite(min) || !Number.isFinite(max) || max === min) return [min];
  const rough = (max - min) / count;
  const magnitude = 10 ** Math.floor(Math.log10(rough));
  const normalized = rough / magnitude;
  const step =
    (normalized < 1.5 ? 1 : normalized < 3 ? 2 : normalized < 7 ? 5 : 10) * magnitude;
  const epsilon = step * 1e-9;
  const ticks: number[] = [];
  for (
    let value = Math.ceil(min / step) * step;
    value <= max + epsilon;
    value += step
  ) {
    ticks.push(Math.abs(value) < epsilon ? 0 : value);
  }
  return ticks;
}

/** Enough decimals to distinguish neighbouring ticks, and no more. */
function formatTick(value: number, step: number) {
  if (!Number.isFinite(value)) return "";
  const magnitude = Math.abs(value);
  if (magnitude >= 1e5 || (magnitude > 0 && magnitude < 1e-4)) {
    return value.toExponential(1);
  }
  const decimals =
    !Number.isFinite(step) || step <= 0 || step >= 1
      ? 0
      : Math.min(4, Math.ceil(-Math.log10(step)));
  return value.toFixed(decimals);
}

function oneResultPerUniverse(results: Array<Record<string, unknown>>) {
  const selected = new Map<string, Record<string, unknown>>();
  const priority = (result: Record<string, unknown>) => {
    const rule = String(result.verdict_rule);
    if (rule === "alpha_05_directional") return 3;
    if (rule === "alpha_05_two_sided") return 2;
    return 1;
  };
  results.forEach((result) => {
    const id = String(result.universe_id);
    const current = selected.get(id);
    if (!current || priority(result) > priority(current)) selected.set(id, result);
  });
  return [...selected.values()];
}

const INFERENCE_LABEL: Record<string, string> = {
  "point-supported": "Positive significant",
  "point-unsupported": "Negative significant",
  "point-indeterminate": "Not significant",
  "point-unavailable": "Not tested",
};

/** The phrase matching a universe's dot colour, so panel and legend agree. */
function inferenceLabel(point: {
  estimate: number;
  pValue: number;
  verdictRule: string;
}) {
  return INFERENCE_LABEL[effectPointClass(point.estimate, point.pValue, point.verdictRule)];
}

function effectPointClass(
  estimate: number,
  pValue: number,
  verdictRule: string,
) {
  if (!Number.isFinite(pValue)) return "point-unavailable";
  if (pValue >= significanceThreshold(verdictRule)) return "point-indeterminate";
  return estimate >= 0 ? "point-supported" : "point-unsupported";
}

function significanceThreshold(verdictRule: string) {
  return verdictRule.includes("alpha_01") ? 0.01 : 0.05;
}

function finiteNumber(value: unknown): number | null {
  if (value == null || value === "") return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function curveEstimate(result: Record<string, unknown>, scale: CurveScale) {
  const stats = asRecord(result.stats);
  return finiteNumber(
    scale === "standardized" ? stats?.estimate_standardized : stats?.estimate,
  );
}

function curveInterval(
  result: Record<string, unknown>,
  scale: CurveScale,
  estimate: number | null,
): [number, number] | null {
  if (estimate == null) return null;
  const stats = asRecord(result.stats);
  if (!stats) return null;
  if (scale === "standardized") {
    const directLow = finiteNumber(stats.ci_low_standardized);
    const directHigh = finiteNumber(stats.ci_high_standardized);
    if (directLow != null && directHigh != null && directLow <= directHigh) {
      return [directLow, directHigh];
    }
    let standardError = finiteNumber(stats.std_error_standardized);
    if (standardError == null) {
      const rawEstimate = finiteNumber(stats.estimate);
      const rawStandardError = finiteNumber(stats.std_error);
      if (rawEstimate != null && rawEstimate !== 0 && rawStandardError != null) {
        standardError = Math.abs(rawStandardError * estimate / rawEstimate);
      }
    }
    return standardError == null
      ? null
      : [estimate - 1.96 * Math.abs(standardError), estimate + 1.96 * Math.abs(standardError)];
  }
  const standardError = finiteNumber(stats.std_error);
  return standardError == null
    ? null
    : [estimate - 1.96 * Math.abs(standardError), estimate + 1.96 * Math.abs(standardError)];
}

function summarizeCurve(
  results: Array<Record<string, unknown>>,
  scale: CurveScale,
): Record<string, unknown> | null {
  const usable = results.flatMap((result) => {
    const estimate = curveEstimate(result, scale);
    return estimate == null ? [] : [{ result, estimate }];
  });
  if (!usable.length) return null;
  const values = usable.map(({ estimate }) => estimate).sort((a, b) => a - b);
  const classes = usable.map(({ result, estimate }) =>
    effectPointClass(
      estimate,
      Number(asRecord(result.stats)?.p_value ?? Number.NaN),
      String(result.verdict_rule),
    ),
  );
  return {
    scale,
    n_universes: results.length,
    n_estimates: values.length,
    n_with_ci: usable.filter(
      ({ result, estimate }) => curveInterval(result, scale, estimate) != null,
    ).length,
    minimum: values[0],
    q25: quantile(values, 0.25),
    median: quantile(values, 0.5),
    q75: quantile(values, 0.75),
    maximum: values[values.length - 1],
    n_significant_positive: classes.filter((value) => value === "point-supported").length,
    n_significant_negative: classes.filter((value) => value === "point-unsupported").length,
    n_indeterminate: classes.filter((value) => value === "point-indeterminate").length,
    n_unavailable: classes.filter((value) => value === "point-unavailable").length,
  };
}

function quantile(values: number[], probability: number) {
  if (values.length === 1) return values[0];
  const position = (values.length - 1) * probability;
  const lower = Math.floor(position);
  const upper = Math.ceil(position);
  const weight = position - lower;
  return values[lower] * (1 - weight) + values[upper] * weight;
}

/** What moved the effect: one ranked row per decision.
 *
 * The option-level effect breakdown lives behind each row's disclosure; the
 * ranking is the only part that belongs on the page by default.
 */
function DecisionSensitivitySection({
  sensitivities,
  unit,
}: {
  sensitivities: Array<Record<string, unknown> | null>;
  unit: string;
}) {
  const present = <T,>(items: Array<T | null>) => items.filter((item): item is T => item != null);
  const sensitivityRows = present(sensitivities);
  if (!sensitivityRows.length) return null;

  const rows: Array<Record<string, unknown>> = sensitivityRows
    .slice()
    .sort((a, b) => {
      const unknown = (row: Record<string, unknown>) =>
        Number(row.n_pairs || 0) === 0 ||
        finiteNumber(row.normalized_effect_change) == null;
      if (unknown(a) !== unknown(b)) return unknown(a) ? 1 : -1;
      return (
        (finiteNumber(b.normalized_effect_change) ?? 0) -
        (finiteNumber(a.normalized_effect_change) ?? 0)
      );
    });
  // 1.0 x IQR means "this decision alone moves the estimate as much as the
  // middle half of the whole curve spans" — a fixed, cross-experiment anchor.
  // The track runs to twice that, so 1.0 sits mid-track and can be marked.
  // 1.0x IQR is the definitional reference and, empirically, the 90th
  // percentile across every run so far. 0.30 flips sits in a real gap in the
  // distribution — the same 18 decisions clear 0.20 and 0.30.
  // 1.0x IQR is the reference for effect movement and the 90th percentile
  // across every run so far. A sign reversal needs no threshold: 97 of 108
  // decisions across every run are exactly zero, so any of it is notable.
  const MOVES_ESTIMATE = 1.0;
  const withUnit = (value: string) => (unit && value !== "—" ? `${value} ${unit}` : value);

  return (
    <>
      <p className="muted-copy curve-caption">
        Each decision, ranked by how often changing it changes the conclusion.
        The bar is the share of matched pairs whose inference changes — a rate,
        so it means the same thing in every experiment. The darker segment is the
        share that <strong>reverses sign</strong>: one option significantly
        positive, the other significantly negative. That is the strongest signal
        here, and it is rare.
      </p>
      <ul className="sensitivity-list">
        {rows.map((row) => {
          const id = String(row.decision_id || "");
          const normalized = finiteNumber(row.normalized_effect_change);
          const flipRate = finiteNumber(row.inference_flip_rate);
          const reversal = finiteNumber(row.sign_reversal_rate);
          const optionPairs = Array.isArray(row.option_pairs)
            ? present(row.option_pairs.map(asRecord))
            : [];
          const medians = asRecord(row.option_medians) || {};
          const unpaired = Number(row.n_pairs || 0) === 0;
          return (
            <li key={id}>
              <details>
                <summary>
                  <span className="sensitivity-name">
                    {id.replaceAll("_", " ")}
                    {(reversal ?? 0) > 0 && (
                      <em
                        className="sensitivity-tag reverses"
                        title={
                          `In ${formatOptionalPercent(reversal)} of matched pairs one ` +
                          "option is significantly positive and the other significantly negative"
                        }
                      >
                        reverses sign
                      </em>
                    )}
                    {(normalized ?? 0) >= MOVES_ESTIMATE && (
                      <em
                        className="sensitivity-tag high-leverage"
                        title="Moves the estimate by at least the curve's interquartile spread"
                      >
                        high leverage
                      </em>
                    )}
                  </span>
                  <span className="sensitivity-bar" aria-hidden="true">
                    <i style={{ width: `${(flipRate ?? 0) * 100}%` }} />
                    {(reversal ?? 0) > 0 && (
                      <u
                        className="sensitivity-reversal"
                        style={{ width: `${(reversal ?? 0) * 100}%` }}
                      />
                    )}
                  </span>
                  <span
                    className={`sensitivity-figure${unpaired ? " unidentified" : ""}`}
                  >
                    {unpaired
                      ? "not identifiable"
                      : flipRate == null
                        ? "—"
                        : `${formatOptionalPercent(flipRate)} flip`}
                  </span>
                  <span className="sensitivity-figure muted">
                    {unpaired || normalized == null
                      ? "—"
                      : `${formatSensitivity(normalized)}× IQR`}
                  </span>
                  <ChevronDown size={15} />
                </summary>
                <div className="sensitivity-detail">
                  {unpaired && (
                    <p className="unidentified-note">
                      No two universes differ in this decision alone — another decision
                      is nested inside it by a <code>requires</code> constraint — so
                      matched-pair sensitivity cannot separate its effect. This is not
                      evidence that it does not matter; check the curve's spread.
                    </p>
                  )}
                  <p className="muted-copy">
                    {Number(row.n_pairs || 0).toLocaleString()} matched pairs
                    {finiteNumber(row.median_abs_effect_change) == null
                      ? ""
                      : ` · typical change ${withUnit(formatEstimate(row.median_abs_effect_change))}`}
                    {finiteNumber(row.variance_share_total) == null
                      ? ""
                      : ` · ${formatOptionalPercent(row.variance_share_total)} of variance`}
                  </p>
                  {Object.keys(medians).length > 0 && (
                    <ul className="option-medians-list">
                      {Object.entries(medians)
                        .sort(([, a], [, b]) => Number(b) - Number(a))
                        .map(([option, median]) => (
                          <li key={option}>
                            <span>{option.replaceAll("_", " ")}</span>
                            <strong>{formatEstimate(median)}</strong>
                          </li>
                        ))}
                    </ul>
                  )}
                  {optionPairs.length > 0 && (
                    <ul className="option-pairs-list">
                      {optionPairs.map((pair) => (
                        <li key={`${String(pair.option_a)}-${String(pair.option_b)}`}>
                          <span className="pair-label">
                            {String(pair.option_a).replaceAll("_", " ")} →{" "}
                            {String(pair.option_b).replaceAll("_", " ")}
                          </span>
                          <span className="pair-shift">
                            {withUnit(formatSigned(pair.median_shift))}
                          </span>
                          <span className="pair-detail">
                            {Number(pair.n_pairs || 0).toLocaleString()} pairs
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </details>
            </li>
          );
        })}
      </ul>
    </>
  );
}

function formatEstimate(value: unknown) {
  const number = finiteNumber(value);
  if (number == null) return "—";
  return new Intl.NumberFormat("en-US", {
    maximumSignificantDigits: 3,
  }).format(number);
}

function formatSigned(value: unknown) {
  const number = finiteNumber(value);
  if (number == null) return "—";
  const text = formatEstimate(Math.abs(number));
  return number > 0 ? `+${text}` : number < 0 ? `−${text}` : text;
}

function formatSensitivity(value: unknown) {
  const number = finiteNumber(value);
  return number == null ? "—" : number.toFixed(2);
}

function formatOptionalPercent(value: unknown) {
  const number = finiteNumber(value);
  return number == null ? "—" : formatPercent(number);
}

/** What the run was actually pointed at — the input, near the bottom. */
function DatasetView({ artifact, dataset }: { artifact: unknown; dataset: string }) {
  const study = asRecord(artifact);
  if (!study) return <Unavailable label="dataset profile" />;
  const columns = Array.isArray(study.columns)
    ? present(study.columns.map(asRecord)).map((column) => ({
        name: String(column.name),
        dtype: String(column.dtype || ""),
        description: column.description == null ? null : String(column.description),
      }))
    : [];
  const name = String(study.dataset_name || datasetName(dataset));

  return (
    <DatasetCard
      name={name}
      description={
        study.dataset_description == null ? null : String(study.dataset_description)
      }
      nRows={finiteNumber(study.n_rows)}
      nColumns={columns.length}
      columns={columns}
      onOpen={() => navigate(`/datasets/${encodeURIComponent(name)}`)}
    />
  );
}

function DecisionsView({ artifact, reviewNeeded }: { artifact: unknown; reviewNeeded: boolean }) {
  const spec = asRecord(artifact);
  const decisions = asRecord(spec?.decisions);
  if (!decisions) return <Unavailable label="Decision space" />;
  const entries = Object.entries(decisions);
  return (
    <>
      <p className="muted-copy">
        {entries.length} analytic decisions. The default option is the one a single
        analysis would have taken; every other option is a fork the multiverse explores.
        {reviewNeeded ? " Review required before running past this stage." : ""}
      </p>
      {/* A plain list: decision, then its options indented under it. */}
      <dl className="decision-outline">
        {entries.map(([id, raw]) => {
          const decision = asRecord(raw);
          const options = Object.entries(asRecord(decision?.options) || {});
          return (
            <div key={id}>
              <dt>
                <code>{id}</code>
                <span>{String(decision?.label || id)}</span>
                <small>{options.length} options</small>
              </dt>
              <dd>
                <ul>
                  {options.map(([optionId, optionRaw]) => {
                    const option = asRecord(optionRaw);
                    const isDefault = decision?.default === optionId;
                    return (
                      <li key={optionId} className={isDefault ? "is-default" : ""}>
                        <code>{optionId}</code>
                        {isDefault && <em>default</em>}
                        <span>{String(option?.label || optionId)}</span>
                      </li>
                    );
                  })}
                </ul>
              </dd>
            </div>
          );
        })}
      </dl>
    </>
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

function present<T>(items: Array<T | null>): T[] {
  return items.filter((item): item is T => item != null);
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function stringList(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string" && item.length > 0)
    : [];
}

function datasetName(path: string) {
  return path.replace(/\/$/, "").split("/").pop() || path;
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

function askExecuteConfirmation(experiment: ExperimentDetail): boolean | null {
  return window.confirm(
    `Continue with up to ${experiment.config.universes.cap} universes using ${experiment.config.execute.agent}? This launches billable coding agents.`,
  )
    ? true
    : null;
}

/**
 * Running one stage spends money only when that stage is `execute`. Verdicts,
 * surprisal and conclusion are pure functions of stats already on disk, so
 * warning about billable agents there is a false alarm that trains people to
 * click through the dialog that does matter.
 */
function confirmStage(experiment: ExperimentDetail, stage: Stage | string): boolean | null {
  if (experiment.config.execute.dry_run || stage !== "execute") return false;
  return askExecuteConfirmation(experiment);
}

/** Running *through* a target spends money if execute is in the path and unfinished. */
function confirmThrough(experiment: ExperimentDetail, target: Stage | string): boolean | null {
  const order = experiment.stages;
  const reaches = order.indexOf(target as Stage) >= order.indexOf("execute" as Stage);
  const billable =
    !experiment.config.execute.dry_run &&
    reaches &&
    experiment.status.execute !== "complete";
  if (!billable) return false;
  return askExecuteConfirmation(experiment);
}
