import { ArrowLeft, GitCompareArrows, Plus } from "lucide-react";
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

export function HypothesisDetailPage({ id }: { id: string }) {
  const { data, error, loading, reload } = useAsync(() => api.hypothesis(id), [id]);
  if (loading) return <Loading label="Loading hypothesis" />;
  if (error || !data) return <ErrorState message={error || "No hypothesis returned"} retry={reload} />;

  return (
    <>
      <button className="back-link" onClick={() => navigate("/hypotheses")}>
        <ArrowLeft size={15} /> Hypotheses
      </button>
      <PageHeader
        eyebrow={data.dataset_name}
        title={data.hypothesis}
        description="One hypothesis, tested through multiple multiverse experiments."
        actions={
          <button className="button primary" onClick={() => navigate(`/experiments/new?hypothesis=${data.id}`)}>
            <Plus size={16} /> New experiment
          </button>
        }
      />

      <section className="metric-strip">
        <Metric
          label="Experiments"
          value={data.attempts.length}
          detail={`${data.support.n_scored} scored`}
        />
        <Metric
          label="Support"
          value={data.support.verdict?.replace("_", " ") || "Unscored"}
          detail={
            data.support.rate_min == null
              ? "No verdicts yet"
              : `${formatPercent(data.support.rate_min)}–${formatPercent(data.support.rate_max)}`
          }
        />
        <Metric
          label="Shared decisions"
          value={data.shared_decisions.length}
          detail={`${Object.keys(data.unique_decisions).length} method-specific`}
        />
        <Metric
          label="Agreement"
          value={data.agreement || "—"}
          detail={data.support.corroborated ? "corroborated" : "needs another experiment"}
        />
      </section>

      <div className="content-grid">
        <section className="section-block span-2">
          <div className="section-heading">
            <div>
              <span className="section-label">History</span>
              <h2>Experiments</h2>
            </div>
          </div>
          {data.attempts.length ? (
            <div className="list-panel">
              {data.attempts.map((attempt) => (
                <RowLink
                  key={attempt.id}
                  href={`/experiments/${attempt.id}`}
                  title={attempt.config_label}
                  meta={`${attempt.n_complete}/8 stages · ${attempt.n_universes ?? "—"} universes · ${formatDate(attempt.created_at)}`}
                  trailing={
                    attempt.running ? (
                      <Badge tone="multiverse">Running</Badge>
                    ) : attempt.support_rate != null ? (
                      <Badge tone={attempt.support_rate >= 0.5 ? "ok" : "warn"}>
                        {formatPercent(attempt.support_rate)} support
                      </Badge>
                    ) : (
                      <Badge>In progress</Badge>
                    )
                  }
                />
              ))}
            </div>
          ) : (
            <EmptyState
              title="No experiments"
              description="Choose an extraction method to map this hypothesis’s decision space."
            />
          )}
        </section>

        <aside className="section-block">
          <div className="section-heading">
            <div>
              <span className="section-label">Method comparison</span>
              <h2>Decision coverage</h2>
            </div>
            <GitCompareArrows size={18} />
          </div>
          {data.shared_decisions.length ? (
            <>
              <div className="decision-group">
                <small>Found by every experiment</small>
                {data.shared_decisions.map((decision) => (
                  <span key={decision}>{decision.replaceAll("_", " ")}</span>
                ))}
              </div>
              <div className="decision-group">
                <small>Found by some methods</small>
                {Object.keys(data.unique_decisions).map((decision) => (
                  <span key={decision}>{decision.replaceAll("_", " ")}</span>
                ))}
              </div>
            </>
          ) : (
            <p className="muted-copy">Complete two experiments to compare extraction coverage.</p>
          )}
        </aside>
      </div>
    </>
  );
}
