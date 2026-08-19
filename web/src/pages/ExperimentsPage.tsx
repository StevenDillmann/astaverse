import { Plus, Search } from "lucide-react";
import { useMemo, useState } from "react";
import { api } from "../api";
import {
  Badge,
  EmptyState,
  ErrorState,
  Loading,
  PageHeader,
  RowLink,
} from "../components";
import { navigate, useAsync } from "../hooks";
import { formatDate, formatPercent } from "../ui";

export function ExperimentsPage() {
  const { data, error, loading, reload } = useAsync(api.experiments, []);
  const [query, setQuery] = useState("");
  const filtered = useMemo(
    () =>
      (data || []).filter((item) =>
        `${item.hypothesis} ${item.dataset_name} ${item.config_label}`
          .toLowerCase()
          .includes(query.toLowerCase()),
      ),
    [data, query],
  );

  if (loading) return <Loading label="Loading experiments" />;
  if (error || !data) return <ErrorState message={error || "No experiments returned"} retry={reload} />;

  return (
    <>
      <PageHeader
        eyebrow="Pipeline"
        title="Experiments"
        description="Every multiverse verification across every hypothesis."
        actions={
          <button className="button primary" onClick={() => navigate("/experiments/new")}>
            <Plus size={16} /> New experiment
          </button>
        }
      />
      <div className="toolbar">
        <label className="search-field">
          <Search size={16} />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search experiments"
          />
        </label>
        <span className="result-count">{filtered.length} experiments</span>
      </div>
      {filtered.length ? (
        <div className="list-panel">
          {filtered.map((experiment) => (
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
                  <Badge>{experiment.n_complete}/8 stages</Badge>
                )
              }
            />
          ))}
        </div>
      ) : (
        <EmptyState
          title="No experiments yet"
          description="Create one to extract a decision space and instantiate its universes."
          action={
            <button className="button primary" onClick={() => navigate("/experiments/new")}>
              Create an experiment
            </button>
          }
        />
      )}
    </>
  );
}
