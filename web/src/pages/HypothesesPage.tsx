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
import { formatDate } from "../ui";

export function HypothesesPage() {
  const { data, error, loading, reload } = useAsync(api.hypotheses, []);
  const [query, setQuery] = useState("");
  const filtered = useMemo(
    () =>
      (data || []).filter((item) =>
        `${item.hypothesis} ${item.dataset_name}`.toLowerCase().includes(query.toLowerCase()),
      ),
    [data, query],
  );

  if (loading) return <Loading label="Loading hypotheses" />;
  if (error || !data) return <ErrorState message={error || "No hypotheses returned"} retry={reload} />;

  return (
    <>
      <PageHeader
        eyebrow="Research"
        title="Hypotheses"
        description="Each hypothesis is coupled to the dataset used to test it."
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
            placeholder="Search hypotheses or datasets"
          />
        </label>
        <span className="result-count">{filtered.length} hypotheses</span>
      </div>
      {filtered.length ? (
        <div className="list-panel hypothesis-list">
          {filtered.map((item) => (
            <RowLink
              key={item.id}
              href={`/hypotheses/${item.id}`}
              title={item.hypothesis}
              meta={`${item.dataset_name} · ${item.n_attempts} experiment${item.n_attempts === 1 ? "" : "s"} · updated ${formatDate(item.updated_at)}`}
              trailing={
                item.running ? (
                  <Badge tone="multiverse">Running</Badge>
                ) : item.support.verdict ? (
                  <Badge tone={item.support.verdict === "supported" ? "ok" : "warn"}>
                    {item.support.verdict.replace("_", " ")}
                  </Badge>
                ) : (
                  <Badge>Unscored</Badge>
                )
              }
            />
          ))}
        </div>
      ) : (
        <EmptyState
          title={query ? "No matching hypotheses" : "No hypotheses yet"}
          description={
            query
              ? "Try a broader phrase or dataset name."
              : "Start with a claim you want to test and the dataset that bears on it."
          }
          action={
            !query ? (
              <button className="button primary" onClick={() => navigate("/experiments/new")}>
                New hypothesis
              </button>
            ) : undefined
          }
        />
      )}
    </>
  );
}
