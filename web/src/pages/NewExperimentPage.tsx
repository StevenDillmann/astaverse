import { ArrowLeft, Check, FlaskConical, GitBranch, Play, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api";
import {
  CommandBlock,
  ErrorState,
  Loading,
  PageHeader,
  StageRail,
} from "../components";
import { navigate, useAsync } from "../hooks";
import type {
  AppSettings,
  CommandPreview,
  DatasetRow,
  ExtractionMethod,
  ExtractionMode,
  HypothesisDetail,
  RunConfig,
  Stage,
} from "../types";

interface FormContext {
  settings: AppSettings;
  datasets: DatasetRow[];
  modes: ExtractionMode[];
  hypothesis: HypothesisDetail | null;
}

export function NewExperimentPage() {
  const params = new URLSearchParams(window.location.search);
  const hypothesisId = params.get("hypothesis");
  const datasetName = params.get("dataset");
  const { data, error, loading, reload } = useAsync<FormContext>(
    async () => {
      const [settings, datasets, modes, hypothesis] = await Promise.all([
        api.settings(),
        api.datasets(),
        api.modes(),
        hypothesisId ? api.hypothesis(hypothesisId) : Promise.resolve(null),
      ]);
      return { settings, datasets, modes, hypothesis };
    },
    [hypothesisId],
  );

  if (loading || !data) return <Loading label="Preparing experiment controls" />;
  if (error) return <ErrorState message={error} retry={reload} />;

  return <ExperimentForm context={data} initialDataset={datasetName} />;
}

function ExperimentForm({
  context,
  initialDataset,
}: {
  context: FormContext;
  initialDataset: string | null;
}) {
  const existing = context.hypothesis;
  const [hypothesis, setHypothesis] = useState(existing?.hypothesis || "");
  const [dataset, setDataset] = useState(
    existing?.dataset_name || initialDataset || context.datasets[0]?.name || "",
  );
  const [config, setConfig] = useState<RunConfig>(() => ({
    ...structuredClone(context.settings.default_experiment),
    through: "verdicts",
  }));
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

  const selectedDataset = context.datasets.find((item) => item.name === dataset);
  const plannedStages = preview?.planned_stages || [];
  const method = config.decisions.mode;
  const methodInfo = context.modes.find((item) => item.id === method);
  const valid = Boolean(existing || (hypothesis.trim() && selectedDataset));

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
      ["execute", "verdicts", "surprisal"].includes(config.through);
    if (
      billable &&
      !window.confirm(
        `Run up to ${config.universes.cap} universes with ${config.execute.agent}? This launches billable coding agents.`,
      )
    ) {
      return;
    }
    setSubmitting(true);
    setSubmitError(null);
    try {
      const result = existing
        ? await api.createExperiment(existing.id, {
            config,
            review_before_execute: review,
          })
        : await api.createHypothesis({
            hypothesis: hypothesis.trim(),
            dataset: selectedDataset?.path || "",
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
        onClick={() => navigate(existing ? `/hypotheses/${existing.id}` : "/experiments")}
      >
        <ArrowLeft size={15} /> {existing ? "Hypothesis" : "Experiments"}
      </button>
      <PageHeader
        eyebrow="New experiment"
        title={existing ? "Test this hypothesis again" : "Map a hypothesis multiverse"}
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
                <div className="stack-fields">
                  <label className="field">
                    <span>Hypothesis</span>
                    <textarea
                      rows={3}
                      value={hypothesis}
                      onChange={(event) => setHypothesis(event.target.value)}
                      placeholder="State the claim the data should test…"
                    />
                  </label>
                  <label className="field">
                    <span>Dataset</span>
                    <select value={dataset} onChange={(event) => setDataset(event.target.value)}>
                      {context.datasets.map((item) => (
                        <option key={item.name} value={item.name}>
                          {item.name} · {item.n_rows?.toLocaleString() || "?"} rows
                        </option>
                      ))}
                    </select>
                    {selectedDataset?.description && <small>{selectedDataset.description}</small>}
                  </label>
                </div>
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
                      AstaVerse will generate one plan, or use the AutoDiscovery plan already
                      attached to this hypothesis.
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
                <Field label="Maximum universes" hint="The full grid is evenly sampled above this cap.">
                  <input
                    type="number"
                    min={1}
                    max={512}
                    value={config.universes.cap}
                    onChange={(event) =>
                      setConfig({
                        ...config,
                        universes: { ...config.universes, cap: Number(event.target.value) },
                      })
                    }
                  />
                </Field>
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
                <Field label="Run through">
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
                    <option value="surprisal">Surprisal</option>
                  </select>
                </Field>
              </div>
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
          <button className="button primary run-button" disabled={!valid || submitting} onClick={() => void create()}>
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
              <strong>≤ {config.universes.cap}</strong>
            </div>
            <div>
              <span>Checkpoint</span>
              <strong>{review ? "Decision review" : "Automatic"}</strong>
            </div>
          </div>
          {methodInfo && <p className="run-method-note">{methodInfo.description}</p>}
          <StageRail stages={plannedStages} />
          {preview ? (
            <CommandBlock command={preview.run} />
          ) : previewError ? (
            <div className="error-block">{previewError}</div>
          ) : (
            <div className="command-skeleton" />
          )}
          <p className="run-sheet-footnote">
            The command is generated from the same configuration the interface will save.
          </p>
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
