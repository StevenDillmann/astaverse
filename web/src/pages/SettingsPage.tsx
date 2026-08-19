import { Check, Circle, Save } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api";
import { ErrorState, Loading, PageHeader } from "../components";
import { useAsync } from "../hooks";
import type { AppSettings, ExtractionMethod, RunConfig } from "../types";

export function SettingsPage() {
  const { data, error, loading, reload, setData } = useAsync(api.settings, []);
  const [draft, setDraft] = useState<AppSettings | null>(null);
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (data) setDraft(structuredClone(data));
  }, [data]);

  if (loading || !draft) return <Loading label="Loading defaults" />;
  if (error || !data) return <ErrorState message={error || "No settings returned"} retry={reload} />;

  const config = draft.default_experiment;
  const updateConfig = (next: RunConfig) => setDraft({ ...draft, default_experiment: next });
  const save = async () => {
    setSaving(true);
    try {
      const result = await api.updateSettings({
        default_experiment: draft.default_experiment,
        review_before_execute: draft.review_before_execute,
      });
      const merged = { ...result, providers: draft.providers };
      setData(merged);
      setDraft(merged);
      setSaved(true);
      window.setTimeout(() => setSaved(false), 1600);
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <PageHeader
        eyebrow="Application"
        title="Settings"
        description="Defaults are copied into new experiments. Existing experiments never change."
        actions={
          <button className="button primary" onClick={() => void save()} disabled={saving}>
            {saved ? <Check size={16} /> : <Save size={16} />}
            {saved ? "Saved" : saving ? "Saving…" : "Save defaults"}
          </button>
        }
      />

      <div className="settings-layout">
        <section className="form-section">
          <div className="section-heading">
            <div>
              <span className="section-label">Readiness</span>
              <h2>Integrations</h2>
            </div>
          </div>
          <div className="provider-list">
            {Object.entries(draft.providers).map(([provider, ready]) => (
              <div key={provider}>
                <span className={ready ? "provider-dot ready" : "provider-dot"}>
                  {ready ? <Check size={12} /> : <Circle size={10} />}
                </span>
                <strong>{provider}</strong>
                <small>{ready ? "Ready" : "Not configured"}</small>
              </div>
            ))}
          </div>
        </section>

        <section className="form-section">
          <div className="section-heading">
            <div>
              <span className="section-label">New experiments</span>
              <h2>Method defaults</h2>
            </div>
          </div>
          <div className="form-grid">
            <Field label="Extraction method">
              <select
                value={config.decisions.mode}
                onChange={(event) =>
                  updateConfig({
                    ...config,
                    decisions: {
                      ...config.decisions,
                      mode: event.target.value as ExtractionMethod,
                    },
                  })
                }
              >
                <option value="sample_plans">Sample plans</option>
                <option value="audit_plan">Audit one plan</option>
                <option value="direct">Direct</option>
              </select>
            </Field>
            <Field label="Plans">
              <input
                type="number"
                min={1}
                max={20}
                value={config.plans.k}
                onChange={(event) =>
                  updateConfig({
                    ...config,
                    plans: { ...config.plans, k: Number(event.target.value) },
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
                  updateConfig({
                    ...config,
                    decisions: {
                      ...config.decisions,
                      max_decisions: Number(event.target.value),
                    },
                  })
                }
              />
            </Field>
            <Field label="Universe cap">
              <input
                type="number"
                min={1}
                max={512}
                value={config.universes.cap}
                onChange={(event) =>
                  updateConfig({
                    ...config,
                    universes: { ...config.universes, cap: Number(event.target.value) },
                  })
                }
              />
            </Field>
          </div>
        </section>

        <section className="form-section">
          <div className="section-heading">
            <div>
              <span className="section-label">Models</span>
              <h2>Execution defaults</h2>
            </div>
          </div>
          <div className="form-grid">
            <Field label="Plan model" hint="Blank uses ASTAVERSE_PLAN_MODEL">
              <input
                value={config.plans.model || ""}
                placeholder="Provider default"
                onChange={(event) =>
                  updateConfig({
                    ...config,
                    plans: { ...config.plans, model: event.target.value || null },
                  })
                }
              />
            </Field>
            <Field label="Decision model" hint="One model identifier">
              <input
                value={config.decisions.models[0] || ""}
                placeholder="Provider default"
                onChange={(event) =>
                  updateConfig({
                    ...config,
                    decisions: {
                      ...config.decisions,
                      models: event.target.value ? [event.target.value] : [],
                    },
                  })
                }
              />
            </Field>
            <Field label="Harbor agent">
              <input
                value={config.execute.agent}
                onChange={(event) =>
                  updateConfig({
                    ...config,
                    execute: { ...config.execute, agent: event.target.value },
                  })
                }
              />
            </Field>
            <Field label="Execution model" hint="Blank uses the agent default">
              <input
                value={config.execute.models[0] || ""}
                placeholder="Agent default"
                onChange={(event) =>
                  updateConfig({
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
          <label className="switch-row">
            <span>
              <strong>Review decision space before execution</strong>
              <small>Pause after extraction so invalid axes do not consume agent budget.</small>
            </span>
            <input
              type="checkbox"
              checked={draft.review_before_execute}
              onChange={(event) =>
                setDraft({ ...draft, review_before_execute: event.target.checked })
              }
            />
          </label>
        </section>
      </div>
    </>
  );
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
