import { ArchiveRestore, ArrowRight, Trash2 } from "lucide-react";
import { useState } from "react";
import { api } from "../api";
import {
  EmptyState,
  ErrorState,
  Loading,
  PageHeader,
  SelectAll,
  SelectionAction,
  SelectionBar,
  SelectRow,
} from "../components";
import { navigate, useAsync, useSelection } from "../hooks";
import type { ArchiveKind } from "../types";
import { formatExperimentId } from "../ui";

/** One archived thing, however it is identified. */
type Entry = {
  kind: ArchiveKind;
  id: string;
  title: string;
  detail: string;
  href: string;
};

export function ArchivePage() {
  const [busy, setBusy] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const { selected, toggle, setMany, clear } = useSelection();
  const [restoring, setRestoring] = useState(false);

  // Settings holds only ids, so each list is fetched with archived included to
  // recover the names and hypothesis text that make an entry recognisable.
  const { data, error, loading, reload } = useAsync(async () => {
    const [settings, datasets, hypotheses, experiments] = await Promise.all([
      api.settings(),
      api.datasets(true),
      api.hypotheses(true),
      api.experiments(true),
    ]);
    return { settings, datasets, hypotheses, experiments };
  }, []);

  if (loading || !data) return <Loading label="Reading the archive" />;
  if (error) return <ErrorState message={error} retry={reload} />;

  const { settings } = data;
  const archivedDatasets = settings.archived_datasets.map((name) => name.toLowerCase());

  const datasetEntries: Entry[] = data.datasets
    .filter((dataset) => archivedDatasets.includes(dataset.name.toLowerCase()))
    .map((dataset) => ({
      kind: "dataset" as const,
      id: dataset.name,
      title: dataset.name,
      detail: `${dataset.n_rows?.toLocaleString() ?? "—"} rows · ${dataset.n_columns ?? "—"} columns`,
      href: `/datasets/${encodeURIComponent(dataset.name)}`,
    }));

  const hypothesisEntries: Entry[] = data.hypotheses
    .filter((row) => settings.archived_hypotheses.includes(row.id))
    .map((row) => ({
      kind: "hypothesis" as const,
      id: row.id,
      title: row.hypothesis,
      detail: `${row.dataset_name} · ${row.n_attempts} experiment${row.n_attempts === 1 ? "" : "s"}`,
      href: `/hypotheses/${row.id}`,
    }));

  const experimentEntries: Entry[] = data.experiments
    .filter((row) => settings.archived_experiments.includes(row.id))
    .map((row) => ({
      kind: "experiment" as const,
      id: row.id,
      title: row.config_label || formatExperimentId(row.id, row.number),
      detail: `${row.dataset_name} · ${row.hypothesis}`,
      href: `/experiments/${row.id}`,
    }));

  // An id can outlive the thing it names — a run deleted from disk, say. Those
  // would otherwise be invisible and unrestorable, so list them plainly.
  const found = new Set([
    ...datasetEntries.map((entry) => `dataset:${entry.id.toLowerCase()}`),
    ...hypothesisEntries.map((entry) => `hypothesis:${entry.id}`),
    ...experimentEntries.map((entry) => `experiment:${entry.id}`),
  ]);
  const orphans: Entry[] = [
    ...settings.archived_datasets.map((id) => ({ kind: "dataset" as const, id })),
    ...settings.archived_hypotheses.map((id) => ({ kind: "hypothesis" as const, id })),
    ...settings.archived_experiments.map((id) => ({ kind: "experiment" as const, id })),
  ]
    .filter(
      ({ kind, id }) =>
        !found.has(`${kind}:${kind === "dataset" ? id.toLowerCase() : id}`),
    )
    .map(({ kind, id }) => ({
      kind,
      id,
      title: id,
      detail: `${kind} · no longer present`,
      href: "",
    }));

  const groups: Array<{ label: string; entries: Entry[] }> = [
    { label: "Datasets", entries: datasetEntries },
    { label: "Hypotheses", entries: hypothesisEntries },
    { label: "Experiments", entries: experimentEntries },
    { label: "Missing", entries: orphans },
  ].filter((group) => group.entries.length > 0);

  const total = groups.reduce((sum, group) => sum + group.entries.length, 0);

  // A selection spans the three sections, so entries are keyed by kind and
  // restored one kind at a time — each kind is its own list in settings.
  const byKey = new Map(groups.flatMap((g) => g.entries).map((e) => [`${e.kind}:${e.id}`, e]));

  const restoreSelected = async () => {
    setRestoring(true);
    setActionError(null);
    const grouped = new Map<ArchiveKind, string[]>();
    for (const key of selected) {
      const entry = byKey.get(key);
      if (!entry) continue;
      grouped.set(entry.kind, [...(grouped.get(entry.kind) || []), entry.id]);
    }
    try {
      for (const [kind, ids] of grouped) {
        await api.setArchivedMany(kind, ids, false);
      }
      clear();
      await reload();
    } catch (reason) {
      setActionError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setRestoring(false);
    }
  };

  // Deleting from the archive is the end of the line, so it names what goes.
  const deleteSelected = async () => {
    const entries = [...selected].flatMap((key) => byKey.get(key) || []);
    const confirmed = window.confirm(
      `Permanently delete ${entries.length} item${entries.length === 1 ? "" : "s"}? ` +
        "This removes them from disk; restoring only un-hides them.",
    );
    if (!confirmed) return;
    setRestoring(true);
    setActionError(null);
    try {
      for (const entry of entries) {
        if (entry.kind === "dataset") await api.deleteDataset(entry.id);
        else if (entry.kind === "hypothesis") await api.deleteHypothesis(entry.id);
        else await api.deleteExperiment(entry.id);
      }
      clear();
      await reload();
    } catch (reason) {
      setActionError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setRestoring(false);
    }
  };

  const restore = async (entry: Entry) => {
    setBusy(`${entry.kind}:${entry.id}`);
    setActionError(null);
    try {
      await api.setArchived(entry.kind, entry.id, false);
      await reload();
    } catch (reason) {
      setActionError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="archive-page">
      <PageHeader
        title="Archive"
        description="Hidden from listings in the app and the CLI. Nothing here has been deleted, and every link still works."
      />

      {actionError && !selected.size && <div className="error-block">{actionError}</div>}

      {selected.size > 0 && (
        <SelectionBar
          count={selected.size}
          noun="item"
          busy={restoring}
          error={actionError}
          onClear={clear}
        >
          <SelectionAction
            label="Restore"
            count={selected.size}
            icon={<ArchiveRestore size={15} />}
            busy={restoring}
            onClick={() => void restoreSelected()}
          />
          <SelectionAction
            label="Delete"
            count={selected.size}
            icon={<Trash2 size={15} />}
            busy={restoring}
            danger
            onClick={() => void deleteSelected()}
          />
        </SelectionBar>
      )}

      {!total ? (
        <EmptyState
          title="Nothing archived"
          description="Archive a dataset, hypothesis or experiment from its own page to hide it from listings without deleting it."
        />
      ) : (
        groups.map((group) => (
          <section className="section-block" key={group.label}>
            <div className="section-heading">
              <div>
                <span className="section-label">{group.label}</span>
                <h2>
                  {group.entries.length} archived
                  {group.label === "Missing" ? ", but no longer on disk" : ""}
                </h2>
              </div>
              <SelectAll
                ids={group.entries.map((entry) => `${entry.kind}:${entry.id}`)}
                selected={selected}
                onChange={setMany}
              />
            </div>
            <ul className="archive-list">
              {group.entries.map((entry) => {
                const key = `${entry.kind}:${entry.id}`;
                return (
                  <li key={key}>
                    <SelectRow
                      id={key}
                      selected={selected}
                      onToggle={toggle}
                      label={entry.title}
                    />
                    <div className="archive-entry-copy">
                      <strong>{entry.title}</strong>
                      <small>{entry.detail}</small>
                    </div>
                    <div className="archive-entry-actions">
                      {entry.href && (
                        <button
                          className="button view small"
                          onClick={() => navigate(entry.href)}
                        >
                          Open <ArrowRight size={15} />
                        </button>
                      )}
                      <button
                        className="button secondary small"
                        disabled={busy === key}
                        onClick={() => void restore(entry)}
                      >
                        <ArchiveRestore size={15} />{" "}
                        {busy === key ? "Restoring…" : "Restore"}
                      </button>
                    </div>
                  </li>
                );
              })}
            </ul>
          </section>
        ))
      )}
    </div>
  );
}
