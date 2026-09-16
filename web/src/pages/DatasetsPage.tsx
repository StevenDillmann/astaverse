import { Archive, Check, Download, Link2, Plus, Search, Trash2 } from "lucide-react";
import { useState } from "react";
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
import { isVisibleDataset } from "../focus";
import { navigate, useAsync, useSelection } from "../hooks";
import { copyText, downloadText, stamp, toCsv } from "../ui";

export function DatasetsPage() {
  const { data, error, loading, reload } = useAsync(api.datasets, []);
  const [view, setView] = useState<CollectionView>("grid");
  const [query, setQuery] = useState("");

  const { selected, toggle, setMany, clear } = useSelection();
  const [busy, setBusy] = useState(false);
  const [bulkError, setBulkError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);

  const chosen = (data || []).filter((dataset) => selected.has(dataset.name));

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

  // Archiving a dataset hides its hypotheses and their experiments too — the
  // listing filters on the dataset, so nothing has to be archived separately.
  const archiveSelected = () => {
    if (
      !window.confirm(
        `Archive ${selected.size} dataset${selected.size === 1 ? "" : "s"}? ` +
          "Their hypotheses and experiments will also be hidden. You can restore them later.",
      )
    ) return;
    return runBulk(() =>
      api.setArchivedMany("dataset", [...selected], true).then(() => undefined),
    );
  };

  const deleteSelected = () => {
    const withWork = chosen.filter(
      (dataset) => (dataset.n_hypotheses ?? 0) > 0 || (dataset.n_experiments ?? 0) > 0,
    );
    const confirmed = window.confirm(
      `Permanently delete ${selected.size} dataset${selected.size === 1 ? "" : "s"}?` +
        (withWork.length
          ? ` ${withWork.length} still have hypotheses or experiments built on them.`
          : "") +
        " Archiving hides them instead, and can be undone.",
    );
    if (!confirmed) return;
    return runBulk(async () => {
      for (const name of selected) await api.deleteDataset(name);
    });
  };

  const exportSelected = () => {
    downloadText(
      `datasets-${stamp()}.csv`,
      toCsv(
        ["name", "rows", "columns", "hypotheses", "experiments", "description"],
        chosen.map((dataset) => [
          dataset.name,
          dataset.n_rows ?? null,
          dataset.n_columns ?? null,
          dataset.n_hypotheses ?? 0,
          dataset.n_experiments ?? 0,
          dataset.description || "",
        ]),
      ),
    );
    setNote(`Exported ${chosen.length} to CSV`);
  };

  const copySelectedLinks = async () => {
    const links = chosen.map(
      (dataset) =>
        `${window.location.origin}/datasets/${encodeURIComponent(dataset.name)}`,
    );
    setNote((await copyText(links.join("\n"))) ? `Copied ${links.length} links` : "Could not copy");
  };

  if (loading) return <Loading label="Discovering datasets" />;
  if (error || !data) return <ErrorState message={error || "No datasets returned"} retry={reload} />;
  const filtered = data
    .filter(
      (dataset) =>
        isVisibleDataset(dataset.name) &&
        `${dataset.name} ${dataset.description || ""}`
          .toLowerCase()
          .includes(query.toLowerCase()),
    )
    .sort((a, b) => a.name.localeCompare(b.name));

  return (
    <>
      <PageHeader
        title="Datasets"
        description="Datasets contain the evidence used to define and test hypotheses."
        actions={
          <>
            <ViewToggle value={view} onChange={setView} />
            <button className="button create" onClick={() => navigate("/datasets/new")}>
              <Plus size={16} /> New dataset
            </button>
          </>
        }
      />
      {selected.size ? (
        <SelectionBar
          count={selected.size}
          noun="dataset"
          busy={busy}
          error={bulkError}
          note={note}
          onClear={clear}
        >
          {filtered.some((dataset) => !selected.has(dataset.name)) && (
            <SelectionAction
              label="Select all"
              icon={<Check size={15} />}
              busy={busy}
              onClick={() => setMany(filtered.map((dataset) => dataset.name), true)}
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
              placeholder="Search datasets"
            />
          </label>
        </div>
      )}
      {filtered.length ? (
        view === "grid" ? <div className="collection-grid">
          {filtered.map((dataset) => (
            <CollectionCardShell
              key={dataset.name}
              selected={selected.has(dataset.name)}
              onOpen={() => navigate(`/datasets/${encodeURIComponent(dataset.name)}`)}
            >
              <span
                className="collection-card-select"
                onKeyDown={(event) => event.stopPropagation()}
              >
                <SelectRow
                  id={dataset.name}
                  selected={selected}
                  onToggle={toggle}
                  label={dataset.name}
                />
              </span>
              <small className="collection-card-kicker">Dataset</small>
              <h2>{dataset.name}</h2>
              <p>{dataset.description || "No dataset description is available."}</p>
              <dl className="collection-card-metadata">
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
                  <dd>{dataset.n_hypotheses ?? 0}</dd>
                </div>
              </dl>
            </CollectionCardShell>
          ))}
        </div> : (
          <div className="hypothesis-table-wrap">
            <table className="hypothesis-table collection-table datasets-table">
              <thead>
                <tr>
                  <th className="select-cell">
                    <SelectAll
                      ids={filtered.map((dataset) => dataset.name)}
                      selected={selected}
                      onChange={setMany}
                    />
                  </th>
                  <th>DATASET</th>
                  <th className="numeric-cell">ROWS</th>
                  <th className="numeric-cell">COLUMNS</th>
                  <th className="numeric-cell">HYPOTHESES</th>
                  <th className="numeric-cell">EXPERIMENTS</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((dataset) => (
                  <CollectionRow
                    key={dataset.name}
                    selected={selected.has(dataset.name)}
                    onOpen={() => navigate(`/datasets/${encodeURIComponent(dataset.name)}`)}
                  >
                    <td className="select-cell">
                      <SelectRow
                        id={dataset.name}
                        selected={selected}
                        onToggle={toggle}
                        label={dataset.name}
                      />
                    </td>
                    <td>
                      <strong>{dataset.name}</strong>
                    </td>
                    <td className="numeric-cell">{dataset.n_rows?.toLocaleString() || "—"}</td>
                    <td className="numeric-cell">{dataset.n_columns ?? "—"}</td>
                    <td className="numeric-cell">{dataset.n_hypotheses ?? 0}</td>
                    <td className="numeric-cell">{dataset.n_experiments ?? 0}</td>
                  </CollectionRow>
                ))}
              </tbody>
            </table>
          </div>
        )
      ) : (
        <EmptyState
          title="No datasets found"
          description="The selected design datasets are not available."
        />
      )}
    </>
  );
}
