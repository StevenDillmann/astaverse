/** The knobs, set once, then used by every way of running a stage.
 *
 * These are human decisions about method, not preferences: which extraction
 * strategy to trust, how far to let the grid grow, whether to spend money on
 * an agent. So they are stated up front and saved with the run, and a
 * finished study carries the choices that produced it.
 */

import { useEffect, useState } from "react";
import { STAGES, getConfig, listModes, putConfig } from "./api";
import type { ExtractionModeInfo, RunConfig, Stage } from "./api";

const SPENDS_MONEY = STAGES.indexOf("execute");

export function Config({
  runId,
  onSaved,
}: {
  runId: string;
  onSaved?: (config: RunConfig) => void;
}) {
  const [config, setConfig] = useState<RunConfig | null>(null);
  const [modes, setModes] = useState<ExtractionModeInfo[]>([]);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getConfig(runId).then(setConfig).catch((e) => setError(e.message));
    listModes().then(setModes).catch(() => setModes([]));
  }, [runId]);

  if (!config) return <p className="empty">{error ?? "Loading configuration…"}</p>;

  // Local edit, saved explicitly — a knob that writes on every keystroke
  // makes it impossible to tell what a run was configured with.
  function patch(section: keyof RunConfig, values: Record<string, unknown>) {
    setConfig((c) => (c ? { ...c, [section]: { ...(c[section] as object), ...values } } : c));
    setSaved(false);
  }

  async function save() {
    if (!config) return;
    setSaving(true);
    setError(null);
    try {
      const next = await putConfig(runId, config as unknown as Record<string, unknown>);
      setConfig(next);
      setSaved(true);
      onSaved?.(next);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  }

  const mode = modes.find((m) => m.id === config.decisions.mode);
  const willSpend = STAGES.indexOf(config.through as Stage) >= SPENDS_MONEY;

  return (
    <>
      {error && <div className="error">{error}</div>}

      <div className="cfg-grid">
        <section className="cfg">
          <p className="eyebrow">02 · Plans</p>
          <label className="cfg-row">
            <span>Plans to sample</span>
            <input
              className="field"
              type="number"
              min={1}
              max={12}
              value={config.plans.k}
              onChange={(e) => patch("plans", { k: Number(e.target.value) })}
            />
          </label>
          <label className="cfg-row">
            <span>Model</span>
            <input
              className="field"
              placeholder="default"
              value={config.plans.model ?? ""}
              onChange={(e) => patch("plans", { model: e.target.value || null })}
            />
          </label>
        </section>

        <section className="cfg">
          <p className="eyebrow">03 · Decision extraction</p>
          <label className="cfg-row">
            <span>Mode</span>
            <select
              className="field"
              value={config.decisions.mode}
              onChange={(e) => patch("decisions", { mode: e.target.value })}
            >
              {modes.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.id}
                </option>
              ))}
            </select>
          </label>
          {mode && <p className="cfg-note">{mode.description}</p>}
          <label className="cfg-row">
            <span>Models</span>
            <input
              className="field"
              placeholder="default — comma-separated unions across models"
              value={config.decisions.models.join(", ")}
              onChange={(e) =>
                patch("decisions", {
                  models: e.target.value
                    .split(",")
                    .map((s) => s.trim())
                    .filter(Boolean),
                })
              }
            />
          </label>
          <label className="cfg-row">
            <span>Max decisions</span>
            <input
              className="field"
              type="number"
              min={1}
              max={12}
              value={config.decisions.max_decisions}
              onChange={(e) => patch("decisions", { max_decisions: Number(e.target.value) })}
            />
          </label>
          <label className="cfg-check">
            <input
              type="checkbox"
              checked={config.decisions.critique}
              onChange={(e) => patch("decisions", { critique: e.target.checked })}
            />
            <span>
              Critique pass <em>— a second call asking what the extraction missed</em>
            </span>
          </label>
        </section>

        <section className="cfg">
          <p className="eyebrow">04 · Universes</p>
          <label className="cfg-row">
            <span>Cap</span>
            <input
              className="field"
              type="number"
              min={1}
              max={512}
              value={config.universes.cap}
              onChange={(e) => patch("universes", { cap: Number(e.target.value) })}
            />
          </label>
          <p className="cfg-note">
            Beyond this the grid is sampled by an even stride, never truncated to a prefix,
            and the drop count is reported.
          </p>
          <label className="cfg-row">
            <span>Exclude</span>
            <input
              className="field"
              placeholder="decision ids, comma-separated"
              value={config.universes.exclude.join(", ")}
              onChange={(e) =>
                patch("universes", {
                  exclude: e.target.value
                    .split(",")
                    .map((s) => s.trim())
                    .filter(Boolean),
                })
              }
            />
          </label>
        </section>

        <section className="cfg">
          <p className="eyebrow">06 · Execution</p>
          <label className="cfg-row">
            <span>Agent</span>
            <input
              className="field"
              value={config.execute.agent}
              onChange={(e) => patch("execute", { agent: e.target.value })}
            />
          </label>
          <label className="cfg-row">
            <span>Models</span>
            <input
              className="field"
              placeholder="default — more than one estimates agent bias"
              value={config.execute.models.join(", ")}
              onChange={(e) =>
                patch("execute", {
                  models: e.target.value
                    .split(",")
                    .map((s) => s.trim())
                    .filter(Boolean),
                })
              }
            />
          </label>
          <label className="cfg-check">
            <input
              type="checkbox"
              checked={config.execute.dry_run}
              onChange={(e) => patch("execute", { dry_run: e.target.checked })}
            />
            <span>
              Dry run <em>— print the harbor command, run nothing</em>
            </span>
          </label>
        </section>

        <section className="cfg">
          <p className="eyebrow">08 · Surprisal</p>
          <label className="cfg-row">
            <span>Belief model</span>
            <input
              className="field"
              placeholder="default"
              value={config.surprisal.model ?? ""}
              onChange={(e) => patch("surprisal", { model: e.target.value || null })}
            />
          </label>
          <label className="cfg-row">
            <span>Draws per elicitation</span>
            <input
              className="field"
              type="number"
              min={1}
              max={30}
              value={config.surprisal.n_samples}
              onChange={(e) => patch("surprisal", { n_samples: Number(e.target.value) })}
            />
          </label>
        </section>

        <section className="cfg">
          <p className="eyebrow">Run all — how far</p>
          <label className="cfg-row">
            <span>Through</span>
            <select
              className="field"
              value={config.through}
              onChange={(e) => {
                setConfig({ ...config, through: e.target.value });
                setSaved(false);
              }}
            >
              {STAGES.map((s, i) => (
                <option key={s} value={s}>
                  {String(i + 1).padStart(2, "0")} · {s}
                </option>
              ))}
            </select>
          </label>
          {willSpend ? (
            <p className="cfg-warn">
              This target includes <code>execute</code>, which launches a coding agent in a
              container. It takes minutes and costs money.
            </p>
          ) : (
            <p className="cfg-note">
              Stops before <code>execute</code>, so nothing spends money on an agent.
            </p>
          )}
        </section>
      </div>

      <div className="cfg-actions">
        <button className="run-btn" onClick={save} disabled={saving}>
          {saving ? "Saving…" : "Save configuration"}
        </button>
        {saved && <span className="cfg-saved">Saved — used by every stage from now on.</span>}
      </div>
    </>
  );
}
