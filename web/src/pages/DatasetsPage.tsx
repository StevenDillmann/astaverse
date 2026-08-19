import { Database, Plus, Search } from "lucide-react";
import { useMemo, useState } from "react";
import { api } from "../api";
import { Badge, EmptyState, ErrorState, Loading, PageHeader } from "../components";
import { navigate, useAsync } from "../hooks";

export function DatasetsPage() {
  const { data, error, loading, reload } = useAsync(api.datasets, []);
  const [query, setQuery] = useState("");
  const filtered = useMemo(
    () =>
      (data || []).filter((dataset) =>
        `${dataset.name} ${dataset.description || ""}`.toLowerCase().includes(query.toLowerCase()),
      ),
    [data, query],
  );

  if (loading) return <Loading label="Discovering datasets" />;
  if (error || !data) return <ErrorState message={error || "No datasets returned"} retry={reload} />;

  return (
    <>
      <PageHeader
        eyebrow="Catalogue"
        title="Datasets"
        description="Reusable evidence sources available to hypothesis experiments."
        actions={
          <button className="button primary" onClick={() => navigate("/experiments/new")}>
            <Plus size={16} /> New hypothesis
          </button>
        }
      />
      <div className="toolbar">
        <label className="search-field">
          <Search size={16} />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search datasets"
          />
        </label>
        <span className="result-count">{filtered.length} datasets</span>
      </div>
      {filtered.length ? (
        <div className="dataset-grid">
          {filtered.map((dataset) => (
            <article className="dataset-card" key={dataset.name}>
              <div className="dataset-icon">
                <Database size={19} />
              </div>
              <div className="dataset-title">
                <h2>{dataset.name}</h2>
                <Badge>{dataset.kind || "dataset"}</Badge>
              </div>
              <p>{dataset.description || "No dataset description is available."}</p>
              <dl>
                <div>
                  <dt>Rows</dt>
                  <dd>{dataset.n_rows?.toLocaleString() || "—"}</dd>
                </div>
                <div>
                  <dt>Columns</dt>
                  <dd>{dataset.n_columns ?? "—"}</dd>
                </div>
                <div>
                  <dt>Hypotheses</dt>
                  <dd>{dataset.n_autodiscovery_hypotheses ?? 0}</dd>
                </div>
              </dl>
              <button
                className="button secondary full"
                onClick={() => navigate(`/experiments/new?dataset=${encodeURIComponent(dataset.name)}`)}
              >
                Test a hypothesis
              </button>
            </article>
          ))}
        </div>
      ) : (
        <EmptyState
          title="No datasets found"
          description={
            query
              ? "Try a broader search."
              : "Set ASTAVERSE_DATASETS to a folder containing CSV or BLADE datasets."
          }
        />
      )}
    </>
  );
}
