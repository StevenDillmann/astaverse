import { ArrowRight, Beaker, CircleAlert, Plus } from "lucide-react";
import { api } from "../api";
import {
  Badge,
  EmptyState,
  ErrorState,
  Loading,
  Metric,
  PageHeader,
  RowLink,
} from "../components";
import { navigate, useAsync } from "../hooks";
import { formatDate, formatPercent } from "../ui";

export function OverviewPage() {
  const { data, error, loading, reload } = useAsync(api.overview, []);
  if (loading) return <Loading />;
  if (error || !data) return <ErrorState message={error || "No overview returned"} retry={reload} />;

  const active = data.experiments.filter((experiment) => experiment.running);
  const completed = data.experiments.filter((experiment) => experiment.support_rate != null);

  return (
    <>
      <PageHeader
        eyebrow="AstaVerse"
        title="Workspace"
        description="Hypotheses, decision spaces, and multiverse experiment results."
        actions={
          <button className="button primary" onClick={() => navigate("/experiments/new")}>
            <Plus size={16} /> New experiment
          </button>
        }
      />

      <section className="instrument-panel overview-instrument">
        <div className="instrument-thesis">
          <span className="section-label">Index</span>
          <h2>
            {data.hypotheses.length || "No"} {data.hypotheses.length === 1 ? "hypothesis" : "hypotheses"}
          </h2>
          <p>{active.length ? `${active.length} currently running.` : "No experiments running."}</p>
          <button className="text-link" onClick={() => navigate("/hypotheses")}>
            Browse hypotheses <ArrowRight size={15} />
          </button>
        </div>
        <div className="branch-summary" aria-label="Workspace summary">
          <div className="branch-trunk" />
          <Metric label="Experiments" value={data.experiments.length} detail={`${active.length} active`} />
          <Metric label="Datasets" value={data.datasets.length} detail="in use" />
          <Metric
            label="Scored"
            value={completed.length}
            detail={completed.length ? "with verdicts" : "awaiting results"}
          />
        </div>
      </section>

      <div className="content-grid">
        <section className="section-block span-2">
          <div className="section-heading">
            <div>
              <span className="section-label">Recent work</span>
              <h2>Experiments</h2>
            </div>
            <button className="text-link" onClick={() => navigate("/experiments")}>
              View all <ArrowRight size={15} />
            </button>
          </div>
          {data.experiments.length ? (
            <div className="list-panel">
              {data.experiments.slice(0, 6).map((experiment) => (
                <RowLink
                  key={experiment.id}
                  href={`/experiments/${experiment.id}`}
                  title={experiment.hypothesis}
                  meta={`${experiment.dataset_name} · ${experiment.config_label} · ${formatDate(experiment.created_at)}`}
                  trailing={
                    experiment.running ? (
                      <Badge tone="multiverse">Running</Badge>
                    ) : experiment.support_rate != null ? (
                      <Badge tone={experiment.support_rate >= 0.5 ? "ok" : "warn"}>
                        {formatPercent(experiment.support_rate)} support
                      </Badge>
                    ) : (
                      <Badge>{experiment.n_complete}/{experiment.n_stages} stages</Badge>
                    )
                  }
                />
              ))}
            </div>
          ) : (
            <EmptyState
              title="No experiments yet"
              description="Couple a hypothesis with a dataset, then choose how to extract its decision space."
              action={
                <button className="button primary" onClick={() => navigate("/experiments/new")}>
                  Create an experiment
                </button>
              }
            />
          )}
        </section>

        <aside className="section-block">
          <div className="section-heading">
            <div>
              <span className="section-label">Attention</span>
              <h2>Review queue</h2>
            </div>
          </div>
          {active.length ? (
            <div className="quiet-list">
              {active.map((experiment) => (
                <button key={experiment.id} onClick={() => navigate(`/experiments/${experiment.id}`)}>
                  <Beaker size={16} />
                  <span>
                    <strong>{experiment.dataset_name}</strong>
                    <small>{experiment.hypothesis}</small>
                  </span>
                </button>
              ))}
            </div>
          ) : (
            <div className="quiet-message">
              <CircleAlert size={18} />
              <p>No experiment needs attention.</p>
            </div>
          )}
        </aside>
      </div>
    </>
  );
}
