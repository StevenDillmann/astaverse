import { ArrowLeft, ArrowRight, ChevronDown, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { api } from "../api";
import {
  ArchiveRow,
  Badge,
  ErrorState,
  Loading,
  PageHeader,
} from "../components";
import { isVisibleExperiment, isVisibleHypothesis } from "../focus";
import { navigate, useAsync, useBackTarget } from "../hooks";
import { DatasetRowsTable } from "../DatasetRowsTable";
import { DatasetSchemaTable } from "../DatasetSchemaTable";
import { formatDate, formatExperimentId, formatPercent } from "../ui";

const PREVIEW_ROWS = 20;

type DatasetView = "schema" | "rows";

export function DatasetDetailPage({ name }: { name: string }) {
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [datasetOpen, setDatasetOpen] = useState(true);
  const [datasetView, setDatasetView] = useState<DatasetView>("schema");
  const [hypothesesOpen, setHypothesesOpen] = useState(false);
  const [experimentsOpen, setExperimentsOpen] = useState(false);
  const back = useBackTarget();
  const { data, error, loading, reload } = useAsync(async () => {
    const [dataset, hypotheses, experiments] = await Promise.all([
      api.dataset(name),
      api.hypotheses(),
      api.experiments(),
    ]);
    return {
      dataset,
      hypotheses: hypotheses.filter(
        (hypothesis) =>
          isVisibleHypothesis(hypothesis.id) &&
          hypothesis.dataset_name.toLowerCase() === dataset.name.toLowerCase(),
      ),
      experiments: experiments.filter(
        (experiment) =>
          isVisibleExperiment(experiment.id) &&
          experiment.dataset_name.toLowerCase() === dataset.name.toLowerCase(),
      ),
    };
  }, [name]);
  const rowsPreview = useAsync(
    () => (datasetView === "rows" ? api.datasetRows(name, PREVIEW_ROWS) : Promise.resolve(null)),
    [name, datasetView],
  );

  if (loading) return <Loading label="Loading dataset" />;
  if (error || !data) {
    return <ErrorState message={error || "No dataset returned"} retry={reload} />;
  }

  const { dataset, hypotheses, experiments } = data;
  const experimentCount = experiments.length;
  const remove = async () => {
    if (!window.confirm(`Permanently delete the dataset “${dataset.name}”?`)) {
      return;
    }
    setDeleting(true);
    setDeleteError(null);
    try {
      await api.deleteDataset(dataset.name);
      navigate("/datasets");
    } catch (reason) {
      setDeleteError(reason instanceof Error ? reason.message : String(reason));
      setDeleting(false);
    }
  };

  return (
    <div className="dataset-detail-page">
      <button className="back-link" onClick={() => back.go("/datasets")}>
        <ArrowLeft size={15} /> {back.label ?? "Datasets"}
      </button>
      <PageHeader
        title={dataset.name}
        description={
          <span className="dataset-description">
            <span>{dataset.description || "No dataset description is available."}</span>
            <span className="dataset-metadata">
              <small><span>Rows</span><strong>{dataset.n_rows?.toLocaleString() || "—"}</strong></small>
              <small><span>Columns</span><strong>{dataset.n_columns ?? "—"}</strong></small>
              <small><span>Hypotheses</span><strong>{hypotheses.length}</strong></small>
            </span>
          </span>
        }
      />

      {deleteError && <div className="error-block">{deleteError}</div>}

      <section className="section-block dataset-section">
        <div
          className="section-heading expandable-heading"
          role="button"
          tabIndex={0}
          aria-expanded={datasetOpen}
          onClick={() => setDatasetOpen((open) => !open)}
          onKeyDown={(event) => {
            if (event.key === "Enter" || event.key === " ") {
              event.preventDefault();
              setDatasetOpen((open) => !open);
            }
          }}
        >
          <h2>
            Dataset
            <ChevronDown className={datasetOpen ? "rotated" : ""} size={17} />
          </h2>
          <div
            className="section-actions"
            onClick={(event) => event.stopPropagation()}
            onKeyDown={(event) => event.stopPropagation()}
          >
            <div className="view-toggle" role="group" aria-label="Dataset view">
              <button
                className={datasetView === "schema" ? "is-active" : ""}
                aria-pressed={datasetView === "schema"}
                onClick={() => setDatasetView("schema")}
              >
                Schema
              </button>
              <button
                className={datasetView === "rows" ? "is-active" : ""}
                aria-pressed={datasetView === "rows"}
                onClick={() => setDatasetView("rows")}
              >
                Rows
              </button>
            </div>
          </div>
        </div>
        {datasetOpen && (
          <div className="section-preview">
            {datasetView === "schema" ? (
              dataset.fields?.length ? (
                <DatasetSchemaTable columns={dataset.fields} />
              ) : dataset.columns?.length ? (
                <div className="column-list">
                  {dataset.columns.map((column) => (
                    <code key={column}>{column}</code>
                  ))}
                </div>
              ) : (
                <p className="muted-copy">No column information is available for this dataset.</p>
              )
            ) : rowsPreview.loading ? (
              <Loading label="Reading rows" />
            ) : rowsPreview.error || !rowsPreview.data ? (
              <ErrorState
                message={rowsPreview.error || "No rows returned"}
                retry={rowsPreview.reload}
              />
            ) : rowsPreview.data.rows.length ? (
              <>
                <DatasetRowsTable
                  columns={rowsPreview.data.columns}
                  rows={rowsPreview.data.rows}
                />
                <p className="muted-copy rows-footnote">
                  Showing the first {rowsPreview.data.rows.length.toLocaleString()}
                  {rowsPreview.data.n_rows != null
                    ? ` of ${rowsPreview.data.n_rows.toLocaleString()}`
                    : ""}{" "}
                  rows.
                </p>
              </>
            ) : (
              <p className="muted-copy">This dataset has no rows.</p>
            )}
          </div>
        )}
      </section>

      <section className="section-block">
        <div
          className="section-heading expandable-heading"
          role="button"
          tabIndex={0}
          aria-expanded={hypothesesOpen}
          onClick={() => setHypothesesOpen((open) => !open)}
          onKeyDown={(event) => {
            if (event.key === "Enter" || event.key === " ") {
              event.preventDefault();
              setHypothesesOpen((open) => !open);
            }
          }}
        >
          <h2>
              Hypotheses ({hypotheses.length})
            <ChevronDown className={hypothesesOpen ? "rotated" : ""} size={17} />
          </h2>
          <div
            className="section-actions"
            onClick={(event) => event.stopPropagation()}
            onKeyDown={(event) => event.stopPropagation()}
          >
            <button
              className="button view small"
              onClick={() =>
                navigate(`/hypotheses?dataset=${encodeURIComponent(dataset.name)}`)
              }
            >
              View all <ArrowRight size={15} />
            </button>
            <button
              className="button create small"
              onClick={() =>
                navigate(`/hypotheses/new?dataset=${encodeURIComponent(dataset.name)}`)
              }
            >
              <Plus size={15} /> New hypothesis
            </button>
          </div>
        </div>
        {hypothesesOpen && <div className="section-preview">
            {hypotheses.length ? (
              <div className="hypothesis-table-wrap">
                <table className="hypothesis-table preview-table hypotheses-preview-table">
                  <thead>
                    <tr>
                      <th>HYPOTHESIS</th>
                      <th className="numeric-cell">EXPERIMENTS</th>
                      <th>STATUS</th>
                    </tr>
                  </thead>
                  <tbody>
                    {hypotheses.slice(0, 3).map((hypothesis) => (
                      <tr
                        key={hypothesis.id}
                        tabIndex={0}
                        onClick={() => navigate(`/hypotheses/${hypothesis.id}`)}
                        onKeyDown={(event) => {
                          if (event.key === "Enter" || event.key === " ") {
                            event.preventDefault();
                            navigate(`/hypotheses/${hypothesis.id}`);
                          }
                        }}
                      >
                        <td><strong>{hypothesis.hypothesis}</strong></td>
                        <td className="numeric-cell">{hypothesis.n_attempts}</td>
                        <td><Badge>{hypothesis.n_attempts ? "Tested" : "Untested"}</Badge></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="muted-copy">No hypotheses have been created for this dataset.</p>
            )}
        </div>}
      </section>

      <section className="section-block">
        <div
          className="section-heading expandable-heading"
          role="button"
          tabIndex={0}
          aria-expanded={experimentsOpen}
          onClick={() => setExperimentsOpen((open) => !open)}
          onKeyDown={(event) => {
            if (event.key === "Enter" || event.key === " ") {
              event.preventDefault();
              setExperimentsOpen((open) => !open);
            }
          }}
        >
          <h2>
              Experiments ({experimentCount})
            <ChevronDown className={experimentsOpen ? "rotated" : ""} size={17} />
          </h2>
          <div
            className="section-actions"
            onClick={(event) => event.stopPropagation()}
            onKeyDown={(event) => event.stopPropagation()}
          >
            <button
              className="button view small"
              onClick={() =>
                navigate(`/experiments?dataset=${encodeURIComponent(dataset.name)}`)
              }
            >
              View all <ArrowRight size={15} />
            </button>
            <button
              className="button create small"
              onClick={() =>
                navigate(`/experiments/new?dataset=${encodeURIComponent(dataset.name)}`)
              }
            >
              <Plus size={15} /> New experiment
            </button>
          </div>
        </div>
        {experimentsOpen && <div className="section-preview">
            {experiments.length ? (
              <div className="hypothesis-table-wrap">
                <table className="hypothesis-table preview-table experiments-preview-table">
                  <thead>
                    <tr>
                      <th>EXPERIMENT</th>
                      <th>HYPOTHESIS</th>
                      <th>STATUS</th>
                      <th>CREATED</th>
                    </tr>
                  </thead>
                  <tbody>
                    {experiments.slice(0, 3).map((experiment) => (
                      <tr
                        key={experiment.id}
                        tabIndex={0}
                        onClick={() => navigate(`/experiments/${experiment.id}`)}
                        onKeyDown={(event) => {
                          if (event.key === "Enter" || event.key === " ") {
                            event.preventDefault();
                            navigate(`/experiments/${experiment.id}`);
                          }
                        }}
                      >
                        <td>
                          <strong>{experiment.config_label}</strong>
                          <small className="table-row-id">
                            {formatExperimentId(experiment.id, experiment.number)}
                          </small>
                        </td>
                        <td className="hypothesis-cell">{experiment.hypothesis}</td>
                        <td>
                          {experiment.running ? (
                            <Badge tone="multiverse">Running</Badge>
                          ) : experiment.support_rate != null ? (
                            <Badge tone={experiment.support_rate >= 0.5 ? "ok" : "multiverse"}>
                              {formatPercent(experiment.support_rate)} support
                            </Badge>
                          ) : (
                            <Badge>In progress</Badge>
                          )}
                        </td>
                        <td className="date-cell">{formatDate(experiment.created_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="muted-copy">No experiments have been run for this dataset.</p>
            )}
        </div>}
      </section>

      <ArchiveRow
        kind="dataset"
        id={dataset.name}
        label="dataset"
        note="Deleting is permanent and available only after its hypotheses have been deleted."
      >
        <button className="button danger" disabled={deleting} onClick={() => void remove()}>
          <Trash2 size={16} /> {deleting ? "Deleting…" : "Delete dataset"}
        </button>
      </ArchiveRow>
    </div>
  );
}

