import { ArrowLeft, Check, ChevronDown, FlaskConical, GitBranch, Play, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api";
import {
  CommandBlock,
  ErrorState,
  Loading,
  PageHeader,
  StageRail,
} from "../components";
import { isVisibleHypothesis } from "../focus";
import { navigate, useAsync } from "../hooks";
import type {
  AppSettings,
  CommandPreview,
  ExtractionMethod,
  ExtractionMode,
  HypothesisDetail,
  HypothesisRow,
  RunConfig,
  Stage,
  StageState,
} from "../types";
import { parseCap } from "../ui";

interface FormContext {
  settings: AppSettings;
  hypotheses: HypothesisRow[];
  modes: ExtractionMode[];
  hypothesis: HypothesisDetail | null;
}

const ALL_STAGES: Stage[] = [
  "study",
  "plans",
  "decisions",
  "universes",
  "task",
  "execute",
  "verdicts",
  "conclusion",
];

export function NewExperimentPage() {
  const params = new URLSearchParams(window.location.search);
  const hypothesisId = params.get("hypothesis");
  const datasetName = params.get("dataset");
  const { data, error, loading, reload } = useAsync<FormContext>(
    async () => {
      const [settings, hypotheses, modes, hypothesis] = await Promise.all([
        api.settings(),
        api.hypotheses(),
        api.modes(),
        hypothesisId ? api.hypothesis(hypothesisId) : Promise.resolve(null),
      ]);
      return {
        settings,
        hypotheses: hypotheses.filter(
          (item) =>
            isVisibleHypothesis(item.id) &&
            (!datasetName || item.dataset_name === datasetName),
        ),
        modes,
        hypothesis,
      };
    },
    [datasetName, hypothesisId],
  );

  if (loading || !data) return <Loading label="Preparing experiment controls" />;
  if (error) return <ErrorState message={error} retry={reload} />;

  return <ExperimentForm context={data} />;
}

function ExperimentForm({ context }: { context: FormContext }) {
  const existing = context.hypothesis;
  const [selectedHypothesisId, setSelectedHypothesisId] = useState("");
  const [config, setConfig] = useState<RunConfig>(() =>
    structuredClone(context.settings.default_experiment),
  );
  const [review, setReview] = useState(context.settings.review_before_execute);
  const [preview, setPreview] = useState<CommandPreview | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const previewKey = JSON.stringify(config);

  useEffect(() => {
    let current = true;
    const timer = window.setTimeout(() => {
      api
        .preview(config)
        .then((next) => {
          if (current) {
            setPreview(next);
            setPreviewError(null);
          }
        })
        .catch((reason: unknown) => {
          if (current) setPreviewError(reason instanceof Error ? reason.message : String(reason));
        });
    }, 120);
    return () => {
      current = false;
      window.clearTimeout(timer);
    };
    // previewKey is the stable, deep dependency for this configuration.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [previewKey]);

  const selectedHypothesis =
    existing || context.hypotheses.find((item) => item.id === selectedHypothesisId);
  const plannedStages = preview?.planned_stages || [];
  const previewStatus = Object.fromEntries(
    ALL_STAGES.map((stage) => [
      stage,
      plannedStages.includes(stage)
        ? "ready"
        : config.decisions.mode === "direct" && stage === "plans"
          ? "skipped"
          : "pending",
    ]),
  ) as Partial<Record<Stage, StageState>>;
  const method = config.decisions.mode;
  const valid = Boolean(selectedHypothesis);

  const updateMethod = (next: ExtractionMethod) => {
    setConfig((current) => ({
      ...current,
      decisions: { ...current.decisions, mode: next },
      plans: next === "audit_plan" ? { ...current.plans, k: 1 } : current.plans,
    }));
  };

  const create = async () => {
    if (!valid || submitting) return;
    const billable =
      !review &&
      !config.execute.dry_run &&
      // Every target at or after `execute` runs the agent — surprisal included,
      // which the old list missed.
      ["execute", "verdicts", "surprisal", "conclusion"].includes(config.through);
    if (
      billable &&
      !window.confirm(
        `Run ${
          config.universes.cap == null
            ? "every universe in the grid"
            : `up to ${config.universes.cap} universes`
        } with ${config.execute.agent}? This launches billable coding agents.`,
      )
    ) {
      return;
    }
    setSubmitting(true);
    setSubmitError(null);
    try {
      const result = await api.createExperiment(selectedHypothesis!.id, {
        config,
        review_before_execute: review,
      });
      await api.run(result.run_id, config.through, false, billable);
      navigate(`/experiments/${result.run_id}`);
    } catch (reason) {
      setSubmitError(reason instanceof Error ? reason.message : String(reason));
      setSubmitting(false);
    }
  };

  return (
    <>
      <button
        className="back-link"
        onClick={() =>
          navigate(existing ? `/hypotheses/${existing.id}` : "/experiments")
        }
      >
        <ArrowLeft size={15} /> {existing ? "Hypothesis" : "Experiments"}
      </button>
      <PageHeader
        eyebrow="New experiment"
        title={
          existing
            ? "Test this hypothesis again"
            : "Configure a new experiment"
        }
        description="Choose how analytic decisions are extracted, then inspect the exact pipeline before it runs."
      />

      <div className="experiment-builder">
        <div className="builder-form">
          <section className="form-section">
            <div className="form-section-number">01</div>
            <div className="form-section-body">
              <div className="section-heading">
                <div>
                  <span className="section-label">Research target</span>
                  <h2>Hypothesis and dataset</h2>
                </div>
              </div>
              {existing ? (
                <div className="locked-context">
                  <FlaskConical size={19} />
                  <div>
                    <strong>{existing.hypothesis}</strong>
                    <span>{existing.dataset_name}</span>
                  </div>
                  <Check size={17} />
                </div>
              ) : (
                <label className="field">
                  <span>Hypothesis</span>
                  <select
                    value={selectedHypothesisId}
                    onChange={(event) => setSelectedHypothesisId(event.target.value)}
                  >
                    <option value="" disabled>
                      Select a hypothesis…
                    </option>
                    {context.hypotheses.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.hypothesis}
                      </option>
                    ))}
                  </select>
                  {selectedHypothesis && (
                    <small>Dataset: {selectedHypothesis.dataset_name}</small>
                  )}
                </label>
              )}
            </div>
          </section>

          <section className="form-section">
            <div className="form-section-number">02</div>
            <div className="form-section-body">
              <div className="section-heading">
                <div>
                  <span className="section-label">Decision extraction</span>
                  <h2>Choose a method</h2>
                </div>
              </div>
              <div className="method-grid">
                {context.modes.map((item) => (
                  <button
                    key={item.id}
                    className={method === item.id ? "method-card selected" : "method-card"}
                    onClick={() => updateMethod(item.id)}
                  >
                    <span className="method-radio">{method === item.id && <span />}</span>
                    <strong>{methodLabel(item.id)}</strong>
                    <p>{item.description}</p>
                  </button>
                ))}
              </div>

              <details className="disclosure-panel configuration-disclosure">
                <summary>
                  <div>
                    <strong>Extraction settings</strong>
                    <small>Models, limits, and critique</small>
                  </div>
                  <ChevronDown size={17} />
                </summary>
                <div className="disclosure-content">
                  <div className="form-grid method-options">
                    {method === "sample_plans" && (
                      <>
                        <Field label="Plans to sample">
                          <input
                            type="number"
                            min={2}
                            max={20}
                            value={config.plans.k}
                            onChange={(event) =>
                              setConfig({
                                ...config,
                                plans: { ...config.plans, k: Number(event.target.value) },
                              })
                            }
                          />
                        </Field>
                        <Field label="Sampling temperature">
                          <input
                            type="number"
                            min={0}
                            max={2}
                            step={0.1}
                            value={config.plans.temperature}
                            onChange={(event) =>
                              setConfig({
                                ...config,
                                plans: {
                                  ...config.plans,
                                  temperature: Number(event.target.value),
                                },
                              })
                            }
                          />
                        </Field>
                      </>
                    )}
                    {method === "audit_plan" && (
                      <div className="inline-note span-all">
                        <Sparkles size={16} />
                        <span>
                          AstaVerse will generate one fresh plan using the AutoDiscovery planning
                          constraints, then audit it for analytic decisions.
                        </span>
                      </div>
                    )}
                    <Field label="Decision model" hint="Blank uses ASTAVERSE_DECISION_MODEL">
                      <input
                        value={config.decisions.models[0] || ""}
                        placeholder="Provider default"
                        onChange={(event) =>
                          setConfig({
                            ...config,
                            decisions: {
                              ...config.decisions,
                              models: event.target.value ? [event.target.value] : [],
                            },
                          })
                        }
                      />
                    </Field>
                    <Field label="Maximum decisions">
                      <input
                        type="number"
                        min={1}
                        max={20}
                        value={config.decisions.max_decisions}
                        onChange={(event) =>
                          setConfig({
                            ...config,
                            decisions: {
                              ...config.decisions,
                              max_decisions: Number(event.target.value),
                            },
                          })
                        }
                      />
                    </Field>
                  </div>
                  <label className="switch-row compact-switch">
                    <span>
                      <strong>Critique extraction</strong>
                      <small>Ask a second pass what the first pass missed.</small>
                    </span>
                    <input
                      type="checkbox"
                      checked={config.decisions.critique}
                      onChange={(event) =>
                        setConfig({
                          ...config,
                          decisions: { ...config.decisions, critique: event.target.checked },
                        })
                      }
                    />
                  </label>
                </div>
              </details>
            </div>
          </section>

          <section className="form-section">
            <div className="form-section-number">03</div>
            <div className="form-section-body">
              <div className="section-heading">
                <div>
                  <span className="section-label">Execution budget</span>
                  <h2>Universes and agent</h2>
                </div>
              </div>
              <div className="form-grid">
                <Field
                  label="Maximum universes"
                  hint="Empty runs every combination the constraints allow. A cap samples a pair-balanced subset instead."
                >
                  <input
                    type="number"
                    min={1}
                    max={512}
                    placeholder="No cap — full grid"
                    value={config.universes.cap ?? ""}
                    onChange={(event) =>
                      setConfig({
                        ...config,
                        universes: { ...config.universes, cap: parseCap(event.target.value) },
                      })
                    }
                  />
                </Field>
                <Field
                  label="Run automatically until"
                  hint="Later stages remain available to run manually."
                >
                  <select
                    value={config.through}
                    onChange={(event) =>
                      setConfig({ ...config, through: event.target.value as Stage })
                    }
                  >
                    <option value="decisions">Decision space</option>
                    <option value="universes">Universes</option>
                    <option value="task">Harbor task</option>
                    <option value="verdicts">Verdicts</option>
                    <option value="conclusion">Conclusion</option>
                  </select>
                </Field>
              </div>
              <details className="disclosure-panel configuration-disclosure">
                <summary>
                  <div>
                    <strong>Execution settings</strong>
                    <small>
                      {config.execute.agent} · {config.execute.models[0] || "agent default"}
                    </small>
                  </div>
                  <ChevronDown size={17} />
                </summary>
                <div className="disclosure-content form-grid">
                  <Field label="Harbor agent">
                    <input
                      value={config.execute.agent}
                      onChange={(event) =>
                        setConfig({
                          ...config,
                          execute: { ...config.execute, agent: event.target.value },
                        })
                      }
                    />
                  </Field>
                  <Field label="Execution model" hint="Blank uses the agent default.">
                    <input
                      value={config.execute.models[0] || ""}
                      placeholder="Agent default"
                      onChange={(event) =>
                        setConfig({
                          ...config,
                          execute: {
                            ...config.execute,
                            models: event.target.value ? [event.target.value] : [],
                          },
                        })
                      }
                    />
                  </Field>
                </div>
              </details>
              <label className="switch-row">
                <span>
                  <strong>Review decision space before execution</strong>
                  <small>Recommended. The pipeline pauses after decision extraction.</small>
                </span>
                <input
                  type="checkbox"
                  checked={review}
                  onChange={(event) => setReview(event.target.checked)}
                />
              </label>
            </div>
          </section>

          {submitError && <div className="error-block">{submitError}</div>}
          <button className="button execute run-button" disabled={!valid || submitting} onClick={() => void create()}>
            <Play size={17} />
            {submitting ? "Creating experiment…" : review ? "Run to decision review" : "Run experiment"}
          </button>
        </div>

        <aside className="run-sheet">
          <div className="run-sheet-title">
            <div>
              <span className="section-label">Run sheet</span>
              <h2>Experiment pipeline</h2>
            </div>
            <GitBranch size={19} />
          </div>
          <div className="run-facts">
            <div>
              <span>Method</span>
              <strong>{methodLabel(method)}</strong>
            </div>
            <div>
              <span>Universe budget</span>
              <strong>
                {config.universes.cap == null ? "Full grid" : `≤ ${config.universes.cap}`}
              </strong>
            </div>
            <div>
              <span>Checkpoint</span>
              <strong>{review ? "Decision review" : "Automatic"}</strong>
            </div>
          </div>
          <StageRail stages={ALL_STAGES} status={previewStatus} />
          <details className="disclosure-panel command-disclosure">
            <summary>
              <div>
                <strong>CLI equivalent</strong>
                <small>Generated from this configuration</small>
              </div>
              <ChevronDown size={17} />
            </summary>
            <div className="disclosure-content">
              {preview ? (
                <CommandBlock command={preview.run} />
              ) : previewError ? (
                <div className="error-block">{previewError}</div>
              ) : (
                <div className="command-skeleton" />
              )}
            </div>
          </details>
        </aside>
      </div>
    </>
  );
}

function methodLabel(method: ExtractionMethod) {
  return {
    sample_plans: "Sample plans",
    audit_plan: "Audit one plan",
    direct: "Direct extraction",
  }[method];
}

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
      {hint && <small>{hint}</small>}
    </label>
  );
}
