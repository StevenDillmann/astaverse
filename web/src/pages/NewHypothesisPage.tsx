import { ArrowLeft, Plus } from "lucide-react";
import { useState } from "react";
import { api } from "../api";
import { ErrorState, Loading, PageHeader } from "../components";
import { isVisibleDataset } from "../focus";
import { navigate, useAsync } from "../hooks";

export function NewHypothesisPage() {
  const params = new URLSearchParams(window.location.search);
  const initialDataset = params.get("dataset") || "";
  const { data, error, loading, reload } = useAsync(api.datasets, []);
  const [hypothesis, setHypothesis] = useState("");
  const [dataset, setDataset] = useState(initialDataset);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  if (loading) return <Loading label="Loading datasets" />;
  if (error || !data) {
    return <ErrorState message={error || "No datasets returned"} retry={reload} />;
  }

  const datasets = data.filter((item) => isVisibleDataset(item.name));
  const selectedDataset = dataset || datasets[0]?.name || "";

  const create = async () => {
    if (!hypothesis.trim() || !selectedDataset || submitting) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const created = await api.createHypothesis({
        hypothesis: hypothesis.trim(),
        dataset: selectedDataset,
      });
      navigate(`/hypotheses/${created.id}`);
    } catch (reason) {
      setSubmitError(reason instanceof Error ? reason.message : String(reason));
      setSubmitting(false);
    }
  };

  return (
    <>
      <button className="back-link" onClick={() => navigate("/hypotheses")}>
        <ArrowLeft size={15} /> Hypotheses
      </button>
      <PageHeader
        title="New hypothesis"
        description="Define a testable claim for one dataset. Experiments are configured separately."
      />

      <div className="builder-form hypothesis-create-form">
        <section className="form-section">
          <div className="section-heading">
            <div>
              <span className="section-label">Research target</span>
              <h2>Hypothesis and dataset</h2>
            </div>
          </div>
          <div className="stack-fields">
            <label className="field">
              <span>Hypothesis</span>
              <textarea
                rows={4}
                value={hypothesis}
                onChange={(event) => setHypothesis(event.target.value)}
                placeholder="State the relationship the data should test…"
              />
            </label>
            <label className="field">
              <span>Dataset</span>
              <select
                value={selectedDataset}
                onChange={(event) => setDataset(event.target.value)}
              >
                {datasets.map((item) => (
                  <option key={item.name} value={item.name}>
                    {item.name} · {item.n_rows?.toLocaleString() || "?"} rows
                  </option>
                ))}
              </select>
            </label>
          </div>
        </section>

        {submitError && <div className="error-block">{submitError}</div>}
        <button
          className="button primary hypothesis-create-button"
          disabled={!hypothesis.trim() || !selectedDataset || submitting}
          onClick={() => void create()}
        >
          <Plus size={16} />
          {submitting ? "Creating…" : "Create hypothesis"}
        </button>
      </div>
    </>
  );
}
