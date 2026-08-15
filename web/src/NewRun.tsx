/** Start a study: pick a dataset, then state the hypothesis.
 *
 * Datasets carry their own research questions, so the common case is picking
 * one rather than composing a hypothesis from scratch — but the field stays
 * editable, because the interesting studies are usually a variation on the
 * published question rather than the question itself.
 */

import { useEffect, useState } from "react";
import { createRun, listDatasets } from "./api";
import type { DatasetInfo } from "./api";

export function NewRun({
  onCreated,
  onCancel,
}: {
  onCreated: (runId: string) => void;
  onCancel: () => void;
}) {
  const [datasets, setDatasets] = useState<DatasetInfo[]>([]);
  const [selected, setSelected] = useState<DatasetInfo | null>(null);
  const [hypothesis, setHypothesis] = useState("");
  const [filter, setFilter] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listDatasets().then(setDatasets).catch((e) => setError(e.message));
  }, []);

  const shown = datasets.filter(
    (d) =>
      !filter ||
      d.name.includes(filter.toLowerCase()) ||
      d.research_questions.join(" ").toLowerCase().includes(filter.toLowerCase()),
  );

  async function create() {
    if (!selected || !hypothesis.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const { run_id } = await createRun(hypothesis.trim(), selected.path);
      onCreated(run_id);
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  }

  return (
    <div className="newrun">
      <div className="newrun-head">
        <div>
          <p className="eyebrow" style={{ margin: 0 }}>
            New study
          </p>
          <h2 className="hypothesis" style={{ fontSize: 18, margin: "6px 0 0" }}>
            Pick the data, then say what you think is true of it.
          </h2>
        </div>
        <button className="ghost-btn" onClick={onCancel}>
          Cancel
        </button>
      </div>

      {error && <div className="error">{error}</div>}

      <div className="newrun-grid">
        <section>
          <p className="eyebrow">
            Dataset {datasets.length > 0 && <span>· {shown.length} of {datasets.length}</span>}
          </p>
          <input
            className="field"
            placeholder="Filter by name or research question"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          />
          <div className="ds-list">
            {datasets.length === 0 && !error && <p className="empty">Looking for datasets…</p>}
            {shown.map((d) => (
              <button
                key={d.path}
                className="ds-item"
                aria-current={selected?.path === d.path}
                onClick={() => {
                  setSelected(d);
                  if (!hypothesis.trim() && d.research_questions[0])
                    setHypothesis(d.research_questions[0]);
                }}
              >
                <span className="ds-name">{d.name}</span>
                <span className="ds-meta">
                  {d.n_rows ?? "?"} rows · {d.n_columns} cols · {d.kind}
                </span>
                {d.research_questions[0] && (
                  <span className="ds-rq">{d.research_questions[0]}</span>
                )}
              </button>
            ))}
          </div>
        </section>

        <section>
          <p className="eyebrow">Hypothesis</p>
          <textarea
            className="field"
            rows={5}
            placeholder="A claim the data can bear on, stated so it could turn out false."
            value={hypothesis}
            onChange={(e) => setHypothesis(e.target.value)}
          />

          {selected && (
            <>
              {selected.research_questions.length > 0 && (
                <>
                  <p className="eyebrow" style={{ marginTop: 20 }}>
                    Published research questions
                  </p>
                  {selected.research_questions.map((q, i) => (
                    <button key={i} className="rq-btn" onClick={() => setHypothesis(q)}>
                      {q}
                    </button>
                  ))}
                </>
              )}
              {selected.description && (
                <>
                  <p className="eyebrow" style={{ marginTop: 20 }}>
                    About this dataset
                  </p>
                  <p className="prose" style={{ fontSize: 12 }}>
                    {selected.description}
                  </p>
                </>
              )}
              <p className="eyebrow" style={{ marginTop: 20 }}>
                Columns
              </p>
              <p className="empty" style={{ lineHeight: 1.8 }}>
                {selected.columns.map((c) => (
                  <span className="tag" key={c} style={{ marginRight: 4 }}>
                    {c}
                  </span>
                ))}
              </p>
            </>
          )}

          <button
            className="run-btn"
            style={{ marginTop: 24 }}
            disabled={!selected || !hypothesis.trim() || busy}
            onClick={create}
          >
            {busy ? "Creating…" : "Create study"}
          </button>
          {!selected && (
            <p className="empty" style={{ marginTop: 8 }}>
              Select a dataset to continue.
            </p>
          )}
        </section>
      </div>
    </div>
  );
}
