import {
  Activity,
  Beaker,
  Check,
  ChevronRight,
  CircleDot,
  Clipboard,
  Database,
  FlaskConical,
  Gauge,
  Menu,
  Moon,
  Settings,
  Sun,
  X,
} from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { navigate } from "./hooks";
import type { CommandPreview, Stage, StageState } from "./types";
import { STAGE_DESCRIPTIONS, STAGE_LABELS } from "./ui";

const NAV = [
  { href: "/", label: "overview", icon: Gauge },
  { href: "/hypotheses", label: "hypotheses", icon: FlaskConical },
  { href: "/datasets", label: "datasets", icon: Database },
  { href: "/experiments", label: "experiments", icon: Beaker },
  { href: "/settings", label: "settings", icon: Settings },
];

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

  const cycleTheme = () => setTheme(theme === "system" ? "dark" : theme === "dark" ? "light" : "system");
  const ThemeIcon = theme === "dark" ? Moon : theme === "light" ? Sun : CircleDot;

  return (
    <div className="app-shell">
      <header className="topbar">
        <button className="menu-button" onClick={() => setOpen(!open)} aria-label="Toggle navigation">
          {open ? <X size={19} /> : <Menu size={19} />}
        </button>
        <button className="wordmark" onClick={() => navigate("/")}>
          <span className="wordmark-mark">A</span>
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
          <button className="icon-button" onClick={cycleTheme} title={`Theme: ${theme}`}>
            <ThemeIcon size={17} />
          </button>
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
  description?: string;
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

