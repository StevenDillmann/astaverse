import {
  ArrowLeft,
  ArrowRight,
  ChevronDown,
  Plus,
  Trash2,
} from "lucide-react";
import { useState } from "react";
import { api } from "../api";
import {
  ArchiveRow,
  DatasetCard,
  ErrorState,
  Loading,
  PageHeader,
} from "../components";
import { isVisibleExperiment } from "../focus";
import { navigate, useAsync, useBackTarget } from "../hooks";
import { formatDate, formatExperimentId } from "../ui";

export function HypothesisDetailPage({ id }: { id: string }) {
  const back = useBackTarget();
  const [datasetOpen, setDatasetOpen] = useState(true);
  const [experimentsOpen, setExperimentsOpen] = useState(true);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const { data: pageData, error, loading, reload } = useAsync(async () => {
    const hypothesis = await api.hypothesis(id);
    const dataset = await api.dataset(hypothesis.dataset_name);
    return { hypothesis, dataset };
  }, [id]);
  if (loading) return <Loading label="Loading hypothesis" />;
  if (error || !pageData) {
    return <ErrorState message={error || "No hypothesis returned"} retry={reload} />;
  }
  const { hypothesis: data, dataset } = pageData;
  const attempts = data.attempts.filter((attempt) => isVisibleExperiment(attempt.id));
  const remove = async () => {
    if (!window.confirm("Permanently delete this hypothesis?")) return;
    setDeleting(true);
    setDeleteError(null);
    try {
      await api.deleteHypothesis(data.id);
      navigate(`/datasets/${encodeURIComponent(data.dataset_name)}`);
    } catch (reason) {
      setDeleteError(reason instanceof Error ? reason.message : String(reason));
      setDeleting(false);
    }
  };

  return (
    <div className="hypothesis-detail-page">
      <button
        className="back-link"
        onClick={() => back.go(`/datasets/${encodeURIComponent(data.dataset_name)}`)}
      >
        <ArrowLeft size={15} /> {back.label ?? data.dataset_name}
      </button>
      <PageHeader
        eyebrow="Hypothesis"
        title={data.hypothesis}
        description={
          <span className="dataset-metadata">
            <small><span>Dataset</span><strong>{data.dataset_name}</strong></small>
            <small><span>Experiments</span><strong>{attempts.length}</strong></small>
          </span>
        }
      />

      {deleteError && <div className="error-block">{deleteError}</div>}

      <div className="hypothesis-content">
        <section className="section-block">
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
          </div>
          {datasetOpen && (
            <div className="section-preview">
              <DatasetCard
                name={dataset.name}
                description={dataset.description}
                nRows={dataset.n_rows}
                nColumns={dataset.n_columns}
                columns={dataset.fields}
                onOpen={() =>
                  navigate(`/datasets/${encodeURIComponent(data.dataset_name)}`)
                }
              />
            </div>
          )}
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
              Experiments ({attempts.length})
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
                  navigate(`/experiments?hypothesis=${encodeURIComponent(data.id)}`)
                }
              >
                View all <ArrowRight size={15} />
              </button>
              <button
                className="button create small"
                onClick={() => navigate(`/experiments/new?hypothesis=${data.id}`)}
              >
                <Plus size={15} /> New experiment
              </button>
            </div>
          </div>
          {experimentsOpen && (
            <div className="section-preview">
              {attempts.length ? (
                <div className="hypothesis-table-wrap">
                  <table className="hypothesis-table preview-table hypothesis-experiments-table">
                    <thead>
                      <tr>
                        <th>EXPERIMENT</th>
                        <th>METHOD</th>
                        <th className="numeric-cell">UNIVERSES</th>
                        <th>CREATED</th>
                      </tr>
                    </thead>
                    <tbody>
                      {attempts.slice(0, 3).map((attempt) => (
                        <tr
                          key={attempt.id}
                          tabIndex={0}
                          onClick={() => navigate(`/experiments/${attempt.id}`)}
                          onKeyDown={(event) => {
                            if (event.key === "Enter" || event.key === " ") {
                              event.preventDefault();
                              navigate(`/experiments/${attempt.id}`);
                            }
                          }}
                        >
                          <td>
                            <strong>{attempt.config_label}</strong>
                            <small className="table-row-id">{formatExperimentId(attempt.id, attempt.number)}</small>
                          </td>
                          <td>{attempt.mode?.replaceAll("_", " ") || "—"}</td>
                          <td className="numeric-cell">{attempt.n_universes ?? "—"}</td>
                          <td className="date-cell">{formatDate(attempt.created_at)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="muted-copy">No experiments have been run for this hypothesis.</p>
              )}
            </div>
          )}
        </section>

      </div>

      <ArchiveRow
        kind="hypothesis"
        id={data.id}
        label="hypothesis"
        note={
          data.attempts.length
            ? "Delete all experiments before deleting this hypothesis."
            : "Deleting permanently removes this hypothesis from its dataset."
        }
      >
        <button
          className="button danger"
          disabled={deleting || data.attempts.length > 0}
          onClick={() => void remove()}
        >
          <Trash2 size={16} /> {deleting ? "Deleting…" : "Delete hypothesis"}
        </button>
      </ArchiveRow>
    </div>
  );
}

