import { Archive, Check, Download, Link2, Plus, Search, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";
import { api } from "../api";
import {
  CollectionCardShell,
  CollectionRow,
  EmptyState,
  ErrorState,
  Loading,
  PageHeader,
  SelectAll,
  SelectionAction,
  SelectionBar,
  SelectRow,
  ViewToggle,
  type CollectionView,
} from "../components";
import { isVisibleExperiment, isVisibleHypothesis } from "../focus";
import { navigate, useAsync, useSelection } from "../hooks";
import {
  copyText,
  downloadText,
  formatDate,
  formatExperimentId,
  stamp,
  toCsv,
} from "../ui";

export function ExperimentsPage() {
  const { data, error, loading, reload } = useAsync(api.experiments, []);
  const [view, setView] = useState<CollectionView>("table");
  const [query, setQuery] = useState("");
  const [dataset, setDataset] = useState(
    () => new URLSearchParams(window.location.search).get("dataset") || "all",
  );
  const [hypothesis, setHypothesis] = useState(
    () => new URLSearchParams(window.location.search).get("hypothesis") || "all",
  );
  // An experiment becomes readable once verdicts produce its specification
  // curve; conclusion is the immediate interpretation step after that.
  const [status, setStatus] = useState(
    () => new URLSearchParams(window.location.search).get("status") || "complete",
  );
  const focused = useMemo(
    () =>
      (data || []).filter(
        (item) =>
          isVisibleHypothesis(item.claim_id) &&
          isVisibleExperiment(item.id),
      ),
    [data],
  );
  const datasets = useMemo(
    () => [...new Set(focused.map((item) => item.dataset_name))].sort(),
    [focused],
  );
  const hypotheses = useMemo(
    () =>
      [...new Map(focused.map((item) => [item.claim_id, item.hypothesis])).entries()],
    [focused],
  );
  const filtered = useMemo(
    () =>
      focused.filter(
        (item) =>
          (dataset === "all" || item.dataset_name === dataset) &&
          (hypothesis === "all" || item.claim_id === hypothesis) &&
          (status === "all" ||
            (status === "complete") === (item.status.verdicts === "complete")) &&
          `${item.hypothesis} ${item.dataset_name} ${item.config_label} ${item.id}`
            .toLowerCase()
            .includes(query.toLowerCase()),
      ),
    [dataset, focused, hypothesis, query, status],
  );

  const { selected, toggle, setMany, clear } = useSelection();
  const [busy, setBusy] = useState(false);
  const [bulkError, setBulkError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);

  const chosen = (data || []).filter((experiment) => selected.has(experiment.id));

  const runBulk = async (work: () => Promise<void>) => {
    setBusy(true);
    setBulkError(null);
    setNote(null);
    try {
      await work();
      clear();
      await reload();
    } catch (reason) {
      setBulkError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(false);
    }
  };

  // Restoring lives on the archive page; this list only ever hides things.
  const archiveSelected = () => {
    if (
      !window.confirm(
        `Archive ${selected.size} experiment${selected.size === 1 ? "" : "s"}? ` +
          "You can restore them later.",
      )
    ) return;
    return runBulk(() =>
      api.setArchivedMany("experiment", [...selected], true).then(() => undefined),
    );
  };

  // Deletion is irreversible and archiving is not, so the confirm says which
  // is which rather than just asking whether the user is sure.
  const deleteSelected = () => {
    const confirmed = window.confirm(
      `Permanently delete ${selected.size} experiment${selected.size === 1 ? "" : "s"}, ` +
        "including every artifact on disk? Archiving hides them instead, and can be undone.",
    );
    if (!confirmed) return;
    return runBulk(async () => {
      for (const id of selected) await api.deleteExperiment(id);
    });
  };

  const exportSelected = () => {
    downloadText(
      `experiments-${stamp()}.csv`,
      toCsv(
        ["id", "short_id", "hypothesis", "dataset", "config", "extraction", "cap", "universes", "support_rate", "created_at"],
        chosen.map((experiment) => [
          experiment.id,
          formatExperimentId(experiment.id, experiment.number),
          experiment.hypothesis,
          experiment.dataset_name,
          experiment.config_label,
          experiment.mode,
          experiment.cap,
          experiment.n_universes,
          experiment.support_rate,
          experiment.created_at,
        ]),
      ),
    );
    setNote(`Exported ${chosen.length} to CSV`);
  };

  const copySelectedLinks = async () => {
    const links = chosen.map(
      (experiment) =>
        `${window.location.origin}/experiments/${encodeURIComponent(experiment.id)}`,
    );
    setNote((await copyText(links.join("\n"))) ? `Copied ${links.length} links` : "Could not copy");
  };

  if (loading) return <Loading label="Loading experiments" />;
  if (error || !data) {
    return <ErrorState message={error || "No experiments returned"} retry={reload} />;
  }

  const createExperiment = () => navigate("/experiments/new");

  return (
    <>
      <PageHeader
        title="Experiments"
        description="Multiverse analyses that test hypotheses across valid analytic choices."
        actions={
          <>
            <ViewToggle value={view} onChange={setView} />
            <button className="button create" onClick={createExperiment}>
              <Plus size={16} /> New experiment
            </button>
          </>
        }
      />

      {selected.size ? (
        <SelectionBar
          count={selected.size}
          noun="experiment"
          busy={busy}
          error={bulkError}
          note={note}
          onClear={clear}
        >
          {filtered.some((experiment) => !selected.has(experiment.id)) && (
            <SelectionAction
              label="Select all"
              icon={<Check size={15} />}
              busy={busy}
              onClick={() => setMany(filtered.map((experiment) => experiment.id), true)}
            />
          )}
          <SelectionAction
            label="Archive"
            count={selected.size}
            icon={<Archive size={15} />}
            busy={busy}
            onClick={() => void archiveSelected()}
          />
          <SelectionAction
            label="Export CSV"
            icon={<Download size={15} />}
            busy={busy}
            onClick={exportSelected}
          />
          <SelectionAction
            label="Copy links"
            icon={<Link2 size={15} />}
            busy={busy}
            onClick={() => void copySelectedLinks()}
          />
          <SelectionAction
            label="Delete"
            count={selected.size}
            icon={<Trash2 size={15} />}
            busy={busy}
            danger
            onClick={() => void deleteSelected()}
          />
        </SelectionBar>
      ) : (
      <div className="table-toolbar">
        <label className="search-field">
          <Search size={16} />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search experiments"
          />
        </label>
        <label className="filter-field">
          <span>Dataset</span>
          <select value={dataset} onChange={(event) => setDataset(event.target.value)}>
            <option value="all">All datasets</option>
            {datasets.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </label>
        <label className="filter-field">
          <span>Status</span>
          <select value={status} onChange={(event) => setStatus(event.target.value)}>
            <option value="complete">Completed</option>
            <option value="in-progress">In progress</option>
            <option value="all">All statuses</option>
          </select>
        </label>
        <label className="filter-field hypothesis-filter">
          <span>Hypothesis</span>
          <select
            value={hypothesis}
            onChange={(event) => setHypothesis(event.target.value)}
          >
            <option value="all">All hypotheses</option>
            {hypotheses.map(([id, label]) => (
              <option key={id} value={id}>
                {label}
              </option>
            ))}
          </select>
        </label>
      </div>
      )}

      {filtered.length ? (
        view === "grid" ? (
          <div className="collection-grid">
            {filtered.map((experiment) => (
              <CollectionCardShell
                key={experiment.id}
                selected={selected.has(experiment.id)}
                onOpen={() => navigate(`/experiments/${experiment.id}`)}
              >
                <span
                  className="collection-card-select"
                  onKeyDown={(event) => event.stopPropagation()}
                >
                  <SelectRow
                    id={experiment.id}
                    selected={selected}
                    onToggle={toggle}
                    label={formatExperimentId(experiment.id, experiment.number)}
                  />
                </span>
                <small className="collection-card-kicker">
                  Experiment · {experiment.dataset_name} · {formatExperimentId(experiment.id, experiment.number)}
                </small>
                <h2>{experiment.hypothesis}</h2>
                <dl className="collection-card-metadata experiment-card-metadata">
                  <div>
                    <dt>Method</dt>
                    <dd>{methodLabel(experiment.mode)}</dd>
                  </div>
                  <div>
                    <dt>Cap</dt>
                    <dd>{experiment.cap ?? "—"}</dd>
                  </div>
                  <div>
                    <dt>Universes</dt>
                    <dd>{experiment.n_universes ?? "—"}</dd>
                  </div>
                </dl>
              </CollectionCardShell>
            ))}
          </div>
        ) : <div className="hypothesis-table-wrap">
          <table className="hypothesis-table collection-table experiments-table">
            <thead>
              <tr>
                <th className="select-cell">
                  <SelectAll
                    ids={filtered.map((experiment) => experiment.id)}
                    selected={selected}
                    onChange={setMany}
                  />
                </th>
                <th>ID</th>
                <th>HYPOTHESIS</th>
                <th>DATASET</th>
                <th>EXTRACTION</th>
                <th className="numeric-cell">CAP</th>
                <th className="numeric-cell">UNIVERSES</th>
                <th>CREATED</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((experiment) => (
                <CollectionRow
                  key={experiment.id}
                  selected={selected.has(experiment.id)}
                  onOpen={() => navigate(`/experiments/${experiment.id}`)}
                >
                  <td className="select-cell">
                    <SelectRow
                      id={experiment.id}
                      selected={selected}
                      onToggle={toggle}
                      label={experiment.hypothesis}
                    />
                  </td>
                  <td className="experiment-id-cell">{formatExperimentId(experiment.id, experiment.number)}</td>
                  <td className="hypothesis-cell">
                    <strong>{experiment.hypothesis}</strong>
                  </td>
                  <td className="dataset-cell">{experiment.dataset_name}</td>
                  <td className="config-cell">
                    {experiment.mode?.replaceAll("_", " ") || "—"}
                    {experiment.critique ? (
                      <small className="config-flag">+critique</small>
                    ) : null}
                  </td>
                  <td className="numeric-cell">{experiment.cap ?? "—"}</td>
                  <td className="numeric-cell">{experiment.n_universes ?? "—"}</td>
                  <td className="date-cell">{formatDate(experiment.created_at)}</td>
                </CollectionRow>
              ))}
            </tbody>
          </table>
        </div>
      ) : focused.length ? (
        <EmptyState
          title="No experiments match these filters"
          description={
            status === "complete"
              ? "These experiments have not produced verdicts yet. Widen the status filter to see them."
              : "Nothing here under the current filters."
          }
          action={
            <button
              className="button primary"
              onClick={() => {
                setStatus("all");
                setDataset("all");
                setHypothesis("all");
                setQuery("");
              }}
            >
              Show all experiments
            </button>
          }
        />
      ) : (
        <EmptyState
          title="No experiments yet"
          description="Create one to extract a decision space and instantiate its universes."
          action={
            <button className="button primary" onClick={createExperiment}>
              Create an experiment
            </button>
          }
        />
      )}
    </>
  );
}

function methodLabel(method: string | null | undefined) {
  return {
    sample_plans: "Sample plans",
    audit_plan: "Audit one plan",
    direct: "Direct",
  }[method || ""] || method?.replaceAll("_", " ") || "—";
}
