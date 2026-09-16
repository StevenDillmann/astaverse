import {
  Activity,
  Archive,
  ArrowRight,
  Beaker,
  Check,
  ChevronRight,
  CircleDot,
  Clipboard,
  Database,
  FlaskConical,
  Gauge,
  LayoutGrid,
  List,
  Menu,
  Moon,
  Settings,
  Sun,
  X,
} from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { navigate, useAsync } from "./hooks";
import { api } from "./api";
import type {
  ArchiveKind,
  CommandPreview,
  DatasetColumn,
  Stage,
  StageState,
} from "./types";
import { STAGE_DESCRIPTIONS, STAGE_LABELS } from "./ui";

const NAV = [
  { href: "/", label: "overview", icon: Gauge },
  { href: "/datasets", label: "datasets", icon: Database },
  { href: "/hypotheses", label: "hypotheses", icon: FlaskConical },
  { href: "/experiments", label: "experiments", icon: Beaker },
  { href: "/archive", label: "archive", icon: Archive },
  { href: "/settings", label: "settings", icon: Settings },
];

function NetworkGlyph({ flipped = false }: { flipped?: boolean }) {
  return (
    <svg
      className={flipped ? "network-glyph flipped" : "network-glyph"}
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <rect x="16" y="16" width="6" height="6" rx="1" />
      <rect x="2" y="16" width="6" height="6" rx="1" />
      <rect x="9" y="2" width="6" height="6" rx="1" />
      <path d="M5 16v-3a1 1 0 0 1 1-1h12a1 1 0 0 1 1 1v3" />
      <path d="M12 12V8" />
    </svg>
  );
}

export function AppShell({
  path,
  children,
  action,
}: {
  path: string;
  children: ReactNode;
  action?: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const [theme, setTheme] = useState(() => localStorage.getItem("astaverse-theme") || "system");

  useEffect(() => {
    if (theme === "system") document.documentElement.removeAttribute("data-theme");
    else document.documentElement.dataset.theme = theme;
    localStorage.setItem("astaverse-theme", theme);
  }, [theme]);

  return (
    <div className="app-shell">
      <header className="topbar">
        <button className="menu-button" onClick={() => setOpen(!open)} aria-label="Toggle navigation">
          {open ? <X size={19} /> : <Menu size={19} />}
        </button>
        <button className="wordmark" onClick={() => navigate("/")}>
          <span className="wordmark-mark" aria-hidden="true">
            <NetworkGlyph />
            <NetworkGlyph flipped />
          </span>
          <span>AstaVerse</span>
        </button>
        <nav className={open ? "primary-nav is-open" : "primary-nav"} aria-label="Primary">
          {NAV.map(({ href, label, icon: Icon }) => {
            const active = href === "/" ? path === "/" : path.startsWith(href);
            return (
              <button
                key={href}
                className={active ? "nav-link is-active" : "nav-link"}
                onClick={() => {
                  navigate(href);
                  setOpen(false);
                }}
              >
                <Icon size={16} />
                {label}
              </button>
            );
          })}
        </nav>
        <div className="topbar-actions">
          {action}
          <div className="theme-options" role="group" aria-label="Color theme">
            {[
              { id: "system", label: "System", Icon: CircleDot },
              { id: "light", label: "Light", Icon: Sun },
              { id: "dark", label: "Dark", Icon: Moon },
            ].map(({ id, label, Icon }) => (
              <button
                key={id}
                className={theme === id ? "theme-option selected" : "theme-option"}
                onClick={() => setTheme(id)}
                aria-label={`${label} theme`}
                aria-pressed={theme === id}
                title={label}
              >
                <Icon size={15} />
              </button>
            ))}
          </div>
          <a
            className="github-link"
            href="https://github.com/StevenDillmann/astaverse"
            target="_blank"
            rel="noreferrer"
            aria-label="Open AstaVerse on GitHub"
            title="GitHub"
          >
            <svg viewBox="0 0 24 24" width="24" height="24" aria-hidden="true">
              <path
                fill="currentColor"
                d="M12 .7a12 12 0 0 0-3.79 23.39c.6.11.82-.26.82-.58v-2.23c-3.34.73-4.04-1.42-4.04-1.42-.55-1.39-1.33-1.76-1.33-1.76-1.09-.74.08-.73.08-.73 1.2.09 1.84 1.24 1.84 1.24 1.07 1.83 2.81 1.3 3.5.99.11-.77.42-1.3.76-1.6-2.67-.3-5.47-1.34-5.47-5.93 0-1.31.47-2.38 1.24-3.22-.12-.3-.54-1.52.12-3.18 0 0 1.01-.32 3.3 1.23a11.5 11.5 0 0 1 6 0c2.29-1.55 3.3-1.23 3.3-1.23.66 1.66.24 2.88.12 3.18.77.84 1.24 1.91 1.24 3.22 0 4.6-2.81 5.62-5.48 5.92.43.37.81 1.1.81 2.22v3.29c0 .32.22.7.82.58A12 12 0 0 0 12 .7Z"
              />
            </svg>
          </a>
        </div>
      </header>
      <main className="page">{children}</main>
    </div>
  );
}

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow?: string;
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="page-header">
      <div>
        {eyebrow && <div className="eyebrow">{eyebrow}</div>}
        <h1>{title}</h1>
        {description && <p>{description}</p>}
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </div>
  );
}

export type CollectionView = "grid" | "table";

export function ViewToggle({
  value,
  onChange,
}: {
  value: CollectionView;
  onChange: (view: CollectionView) => void;
}) {
  return (
    <div className="view-toggle" role="group" aria-label="Display style">
      <button
        className={value === "grid" ? "is-active" : ""}
        aria-label="Grid view"
        aria-pressed={value === "grid"}
        onClick={() => onChange("grid")}
      >
        <LayoutGrid size={14} />
        Grid
      </button>
      <button
        className={value === "table" ? "is-active" : ""}
        aria-label="Table view"
        aria-pressed={value === "table"}
        onClick={() => onChange("table")}
      >
        <List size={14} />
        Table
      </button>
    </div>
  );
}

export function Loading({ label = "Reading the workspace" }: { label?: string }) {
  return (
    <div className="state-block">
      <Activity className="spin" size={18} />
      <span>{label}</span>
    </div>
  );
}

export function ErrorState({ message, retry }: { message: string; retry?: () => void }) {
  return (
    <div className="error-block" role="alert">
      <strong>Could not load this view</strong>
      <span>{message}</span>
      {retry && (
        <button className="button secondary" onClick={retry}>
          Try again
        </button>
      )}
    </div>
  );
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty-state">
      <div className="empty-orbit">
        <span />
        <span />
        <span />
      </div>
      <h3>{title}</h3>
      <p>{description}</p>
      {action}
    </div>
  );
}

/** The dataset panel, shared by the hypothesis and experiment pages.
 *
 * The clickable summary card comes from the hypothesis page; the column table
 * comes from the experiment page, where column semantics are what stage 3
 * extraction actually reads. Both pages want both.
 */
export function DatasetCard({
  name,
  description,
  nRows,
  nColumns,
  columns = [],
  onOpen,
}: {
  name: string;
  description?: string | null;
  nRows?: number | null;
  nColumns?: number | null;
  columns?: DatasetColumn[];
  onOpen: () => void;
}) {
  return (
    <>
      <button className="linked-entity-preview" onClick={onOpen}>
        <span className="linked-entity-copy">
          <strong>{name}</strong>
          <small>{description || "No dataset description is available."}</small>
        </span>
        <span className="dataset-metadata">
          <small>
            <span>Rows</span>
            <strong>{nRows?.toLocaleString() || "—"}</strong>
          </small>
          <small>
            <span>Columns</span>
            <strong>{nColumns ?? columns.length ?? "—"}</strong>
          </small>
        </span>
        <ArrowRight size={17} />
      </button>
      {columns.length > 0 && (
        <div className="hypothesis-table-wrap dataset-columns">
          <table className="hypothesis-table preview-table">
            <thead>
              <tr>
                <th>COLUMN</th>
                <th>TYPE</th>
                <th>DESCRIPTION</th>
              </tr>
            </thead>
            <tbody>
              {columns.map((column) => (
                <tr key={column.name}>
                  <td>
                    <strong>{column.name}</strong>
                  </td>
                  <td className="dataset-cell">{column.dtype || "—"}</td>
                  <td className="hypothesis-cell">{column.description || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

/** Archive or restore one item — non-destructive, so it sits above Delete. */
export function ArchiveRow({
  kind,
  id,
  label,
  children,
  note,
}: {
  kind: ArchiveKind;
  id: string;
  label: string;
  /** Further management actions, shown beside Archive — typically Delete. */
  children?: ReactNode;
  /** What those extra actions do, and any precondition on them. */
  note?: ReactNode;
}) {
  const field = (
    {
      dataset: "archived_datasets",
      hypothesis: "archived_hypotheses",
      experiment: "archived_experiments",
    } as const
  )[kind];
  const { data, reload } = useAsync(api.settings, []);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const archivedIds: string[] = data ? (data[field] as string[]) : [];
  const archived =
    kind === "dataset"
      ? archivedIds.some((name) => name.toLowerCase() === id.toLowerCase())
      : archivedIds.includes(id);

  const toggle = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.setArchived(kind, id, !archived);
      await reload();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="management-area">
      <div>
        <strong>
          {archived ? "Restore" : "Archive"} or delete {label}
        </strong>
        <small>
          {archived
            ? `This ${label} is hidden from listings. Restoring brings it back everywhere.`
            : "Archiving hides it from listings in the app and the CLI; nothing is deleted and the link keeps working."}
          {note ? <> {note}</> : null}
        </small>
        {error && <small className="archive-error">{error}</small>}
      </div>
      <div className="management-actions">
        <button className="button secondary" disabled={busy || !data} onClick={() => void toggle()}>
          <Archive size={16} />{" "}
          {busy ? "Saving…" : archived ? `Restore ${label}` : `Archive ${label}`}
        </button>
        {children}
      </div>
    </section>
  );
}

/**
 * Tabs within a section. Panels that belong to one question — the curve, the
 * sensitivity table, the written conclusion — read better switched than stacked
 * as separate collapsible sections down the page.
 */
export function Tabs({
  tabs,
  initial,
}: {
  tabs: Array<{ id: string; label: string; count?: number | null; panel: ReactNode }>;
  initial?: string;
}) {
  const available = tabs.filter((tab) => tab.panel != null);
  const [active, setActive] = useState(initial || available[0]?.id);
  const current = available.find((tab) => tab.id === active) || available[0];
  if (!current) return null;
  return (
    <>
      <div className="tab-strip" role="tablist">
        {available.map((tab) => (
          <button
            key={tab.id}
            role="tab"
            aria-selected={tab.id === current.id}
            className={tab.id === current.id ? "tab is-active" : "tab"}
            onClick={() => setActive(tab.id)}
          >
            {tab.label}
            {tab.count != null && <span className="tab-count">{tab.count}</span>}
          </button>
        ))}
      </div>
      <div role="tabpanel">{current.panel}</div>
    </>
  );
}

/** The header checkbox: on when every row is chosen, dashed when only some are. */
export function SelectAll({
  ids,
  selected,
  onChange,
}: {
  ids: string[];
  selected: ReadonlySet<string>;
  onChange: (ids: string[], on: boolean) => void;
}) {
  const chosen = ids.filter((id) => selected.has(id)).length;
  const all = ids.length > 0 && chosen === ids.length;
  return (
    <input
      type="checkbox"
      className="row-select"
      aria-label={all ? "Clear selection" : "Select all"}
      checked={all}
      ref={(node) => {
        if (node) node.indeterminate = chosen > 0 && !all;
      }}
      onChange={() => onChange(ids, !all)}
      onClick={(event) => event.stopPropagation()}
    />
  );
}

/** A row's checkbox. Stops propagation so ticking a row does not open it. */
export function SelectRow({
  id,
  selected,
  onToggle,
  label,
}: {
  id: string;
  selected: ReadonlySet<string>;
  onToggle: (id: string) => void;
  label: string;
}) {
  return (
    <input
      type="checkbox"
      className="row-select"
      aria-label={`Select ${label}`}
      checked={selected.has(id)}
      onChange={() => onToggle(id)}
      onClick={(event) => event.stopPropagation()}
    />
  );
}

/** Shared selectable collection card used by all three collection screens. */
export function CollectionCardShell({
  selected,
  onOpen,
  children,
}: {
  selected: boolean;
  onOpen: () => void;
  children: ReactNode;
}) {
  return (
    <article
      className={`collection-card${selected ? " is-selected" : ""}`}
      role="link"
      tabIndex={0}
      onClick={onOpen}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onOpen();
        }
      }}
    >
      {children}
    </article>
  );
}

/** Shared selectable table row used by all three collection screens. */
export function CollectionRow({
  selected,
  onOpen,
  children,
}: {
  selected: boolean;
  onOpen: () => void;
  children: ReactNode;
}) {
  return (
    <tr
      className={selected ? "is-selected" : undefined}
      tabIndex={0}
      onClick={onOpen}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onOpen();
        }
      }}
    >
      {children}
    </tr>
  );
}

/**
 * The bar that appears once something is selected.
 *
 * It replaces the toolbar rather than stacking under it, so the row of
 * filters cannot be mistaken for part of the action about to be taken.
 */
export function SelectionBar({
  count,
  noun,
  busy,
  error,
  note,
  onClear,
  children,
}: {
  count: number;
  noun: string;
  busy?: boolean;
  error?: string | null;
  note?: string | null;
  onClear: () => void;
  children: ReactNode;
}) {
  return (
    <div className="selection-bar" role="status">
      <strong>
        {count} {noun}
        {count === 1 ? "" : "s"} selected
      </strong>
      {error && <span className="selection-error">{error}</span>}
      {!error && note && <span className="selection-note">{note}</span>}
      <div className="selection-actions">
        {children}
        <button className="button ghost small" disabled={busy} onClick={onClear}>
          Clear
        </button>
      </div>
    </div>
  );
}

/** One button in a selection bar, so every bulk action looks the same. */
export function SelectionAction({
  label,
  icon,
  count,
  busy,
  danger,
  onClick,
}: {
  label: string;
  icon: ReactNode;
  count?: number;
  busy?: boolean;
  danger?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      className={danger ? "button danger small" : "button secondary small"}
      disabled={busy}
      onClick={onClick}
    >
      {icon} {busy ? "Working…" : count == null ? label : `${label} ${count}`}
    </button>
  );
}

export function Badge({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: "neutral" | "ok" | "warn" | "multiverse" | "single";
}) {
  return <span className={`badge ${tone}`}>{children}</span>;
}

export function StageRail({
  stages,
  status,
  current,
  compact = false,
}: {
  stages: Stage[];
  status?: Partial<Record<Stage, StageState>>;
  current?: Stage | null;
  compact?: boolean;
}) {
  return (
    <ol className={compact ? "stage-rail compact" : "stage-rail"}>
      {stages.map((stage, index) => {
        const state = current === stage ? "running" : status?.[stage] || "pending";
        return (
          <li key={stage} className={`stage-node ${state}`}>
            <span className="stage-index">
              {state === "complete" ? <Check size={12} /> : String(index + 1).padStart(2, "0")}
            </span>
            <span className="stage-copy">
              <strong>{STAGE_LABELS[stage]}</strong>
              {!compact && <small>{STAGE_DESCRIPTIONS[stage]}</small>}
            </span>
            {index < stages.length - 1 && <span className="stage-line" />}
          </li>
        );
      })}
    </ol>
  );
}

export function CommandBlock({
  command,
  label = "CLI equivalent",
}: {
  command: string;
  label?: string;
}) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    await navigator.clipboard.writeText(command);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1600);
  };
  return (
    <div className="command-block">
      <div className="command-header">
        <span>{label}</span>
        <button onClick={copy}>
          {copied ? <Check size={14} /> : <Clipboard size={14} />}
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <code>{command}</code>
    </div>
  );
}

export function ExperimentCommands({ commands }: { commands: CommandPreview }) {
  return <CommandBlock command={commands.run} />;
}

export function Metric({
  label,
  value,
  detail,
}: {
  label: string;
  value: ReactNode;
  detail?: string;
}) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
      {detail && <small>{detail}</small>}
    </div>
  );
}

export function RowLink({
  title,
  meta,
  href,
  trailing,
}: {
  title: string;
  meta: string;
  href: string;
  trailing?: ReactNode;
}) {
  return (
    <button className="row-link" onClick={() => navigate(href)}>
      <span className="row-copy">
        <strong>{title}</strong>
        <small>{meta}</small>
      </span>
      <span className="row-trailing">
        {trailing}
        <ChevronRight size={16} />
      </span>
    </button>
  );
}

