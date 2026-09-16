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
import { isVisibleHypothesis } from "../focus";
import { navigate, useAsync, useSelection } from "../hooks";
import { copyText, downloadText, stamp, toCsv } from "../ui";

export function HypothesesPage() {
  const { data, error, loading, reload } = useAsync(api.hypotheses, []);
  const [view, setView] = useState<CollectionView>("grid");
  const [query, setQuery] = useState("");
  const [dataset, setDataset] = useState(
    () => new URLSearchParams(window.location.search).get("dataset") || "all",
  );
  const focused = useMemo(
    () => (data || []).filter((item) => isVisibleHypothesis(item.id)),
    [data],
  );

  const datasets = useMemo(
    () => [...new Set(focused.map((item) => item.dataset_name))].sort(),
    [focused],
  );
  const filtered = useMemo(
    () =>
      focused.filter(
        (item) =>
          (dataset === "all" || item.dataset_name === dataset) &&
          `${item.hypothesis} ${item.dataset_name}`
            .toLowerCase()
            .includes(query.toLowerCase()),
      ),
    [focused, dataset, query],
  );

  const { selected, toggle, setMany, clear } = useSelection();
  const [busy, setBusy] = useState(false);
  const [bulkError, setBulkError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);

  const chosen = (data || []).filter((item) => selected.has(item.id));

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

  const archiveSelected = () => {
    if (
      !window.confirm(
        `Archive ${selected.size} hypothes${selected.size === 1 ? "is" : "es"}? ` +
          "You can restore them later.",
      )
    ) return;
    return runBulk(() =>
      api.setArchivedMany("hypothesis", [...selected], true).then(() => undefined),
    );
  };

  // The API refuses a hypothesis that still has experiments, so say so up front
  // rather than letting the first refusal abort a half-applied loop.
  const deleteSelected = () => {
    const blocked = chosen.filter((item) => item.n_attempts > 0);
    if (blocked.length) {
      setBulkError(
        `${blocked.length} of these still have experiments. Delete or archive those first.`,
      );
      return;
    }
    const confirmed = window.confirm(
      `Permanently delete ${selected.size} hypothes${selected.size === 1 ? "is" : "es"}? ` +
        "Archiving hides them instead, and can be undone.",
    );
    if (!confirmed) return;
    return runBulk(async () => {
      for (const id of selected) await api.deleteHypothesis(id);
    });
  };

  const exportSelected = () => {
    downloadText(
      `hypotheses-${stamp()}.csv`,
      toCsv(
        ["id", "hypothesis", "dataset", "experiments"],
        chosen.map((item) => [item.id, item.hypothesis, item.dataset_name, item.n_attempts]),
      ),
    );
    setNote(`Exported ${chosen.length} to CSV`);
  };

  const copySelectedLinks = async () => {
    const links = chosen.map(
      (item) => `${window.location.origin}/hypotheses/${encodeURIComponent(item.id)}`,
    );
    setNote((await copyText(links.join("\n"))) ? `Copied ${links.length} links` : "Could not copy");
  };

  if (loading) return <Loading label="Loading hypotheses" />;
  if (error || !data) {
    return <ErrorState message={error || "No hypotheses returned"} retry={reload} />;
  }

  return (
    <>
      <PageHeader
        title="Hypotheses"
        description="Claims linked to datasets, whether tested or not."
        actions={
          <>
            <ViewToggle value={view} onChange={setView} />
            <button
              className="button create"
              onClick={() => navigate("/hypotheses/new")}
            >
              <Plus size={16} /> New hypothesis
            </button>
          </>
        }
      />

      {selected.size ? (
        <SelectionBar
          count={selected.size}
          noun="hypothesis"
          busy={busy}
          error={bulkError}
          note={note}
          onClear={clear}
        >
          {filtered.some((item) => !selected.has(item.id)) && (
            <SelectionAction
              label="Select all"
              icon={<Check size={15} />}
              busy={busy}
              onClick={() => setMany(filtered.map((item) => item.id), true)}
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
            placeholder="Search hypotheses"
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
      </div>
      )}

      {filtered.length ? (
        view === "grid" ? (
          <div className="collection-grid">
            {filtered.map((item) => (
              <CollectionCardShell
                key={item.id}
                selected={selected.has(item.id)}
                onOpen={() => navigate(`/hypotheses/${item.id}`)}
              >
                <span
                  className="collection-card-select"
                  onKeyDown={(event) => event.stopPropagation()}
                >
                  <SelectRow
                    id={item.id}
                    selected={selected}
                    onToggle={toggle}
                    label={item.hypothesis}
                  />
                </span>
                <small className="collection-card-kicker">
                  Hypothesis · {item.dataset_name}
                </small>
                <h2>{item.hypothesis}</h2>
                <dl className="collection-card-metadata">
                  <div>
                    <dt>Experiments</dt>
                    <dd>{item.n_attempts}</dd>
                  </div>
                </dl>
              </CollectionCardShell>
            ))}
          </div>
        ) : <div className="hypothesis-table-wrap">
          <table className="hypothesis-table collection-table hypotheses-table">
            <thead>
              <tr>
                <th className="select-cell">
                  <SelectAll
                    ids={filtered.map((item) => item.id)}
                    selected={selected}
                    onChange={setMany}
                  />
                </th>
                <th>HYPOTHESIS</th>
                <th>DATASET</th>
                <th className="numeric-cell">EXPERIMENTS</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((item) => (
                <CollectionRow
                  key={item.id}
                  selected={selected.has(item.id)}
                  onOpen={() => navigate(`/hypotheses/${item.id}`)}
                >
                  <td className="select-cell">
                    <SelectRow
                      id={item.id}
                      selected={selected}
                      onToggle={toggle}
                      label={item.hypothesis}
                    />
                  </td>
                  <td>
                    <strong>{item.hypothesis}</strong>
                  </td>
                  <td className="dataset-cell">{item.dataset_name}</td>
                  <td className="numeric-cell">{item.n_attempts}</td>
                </CollectionRow>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <EmptyState
          title="No matching hypotheses"
          description="Change the dataset filter or search phrase."
        />
      )}
    </>
  );
}

