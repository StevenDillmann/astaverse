/** Small component primitives, shadcn-style: local source, semantic tokens,
 *  no component framework. Kept deliberately few — this interface is a thin
 *  surface over a CLI, not an application, so it needs a table, a button, a
 *  field, and a tag, and very little else.
 */

import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, SelectHTMLAttributes } from "react";
import { ChevronDown } from "lucide-react";
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export const cn = (...parts: unknown[]) => twMerge(clsx(parts));

// -- button ----------------------------------------------------------------

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "outline" | "ghost" | "danger";
  size?: "sm" | "md";
};

const VARIANTS = {
  primary:
    "bg-foreground text-background hover:bg-foreground/85 border border-transparent",
  outline: "border border-input bg-transparent hover:bg-accent",
  ghost: "border border-transparent bg-transparent hover:bg-accent",
  danger: "border border-single/40 text-single bg-transparent hover:bg-single/10",
};

export function Button({ variant = "outline", size = "md", className, ...rest }: ButtonProps) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-1.5 rounded-md font-medium transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 focus-visible:ring-offset-background",
        "disabled:pointer-events-none disabled:opacity-40",
        size === "sm" ? "h-7 px-2.5 text-xs" : "h-8 px-3 text-[13px]",
        VARIANTS[variant],
        className,
      )}
      {...rest}
    />
  );
}

// -- surfaces --------------------------------------------------------------

export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <div className={cn("rounded-lg border border-border bg-card", className)}>{children}</div>
  );
}

export function Tag({
  tone = "neutral",
  className,
  children,
}: {
  tone?: "neutral" | "ok" | "warn" | "single" | "multiverse";
  className?: string;
  children: ReactNode;
}) {
  const tones = {
    neutral: "bg-muted text-muted-foreground",
    ok: "bg-ok/10 text-ok",
    warn: "bg-warn/10 text-warn",
    single: "bg-single/10 text-single",
    multiverse: "bg-multiverse/10 text-multiverse",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center rounded px-1.5 py-0.5 font-mono text-[11px] leading-4",
        tones[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

/** A section label. Uppercase mono, used everywhere a group needs naming. */
export function Eyebrow({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <p
      className={cn(
        "font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground",
        className,
      )}
    >
      {children}
    </p>
  );
}

// -- form ------------------------------------------------------------------

const FIELD =
  "w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-[13px] " +
  "placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 " +
  "focus-visible:ring-ring";

export function Input({ className, ...rest }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cn(FIELD, className)} {...rest} />;
}

export function Select({ className, children, ...rest }: SelectHTMLAttributes<HTMLSelectElement>) {
  // Native appearance is stripped for consistency across platforms, so the
  // chevron has to be drawn back on — without it a select is indistinguishable
  // from a text input, and nobody discovers the options.
  return (
    <div className="relative">
      <select className={cn(FIELD, "appearance-none pr-8", className)} {...rest}>
        {children}
      </select>
      <ChevronDown
        size={13}
        className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground"
      />
    </div>
  );
}

export function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <label className="mb-4 block">
      <span className="mb-1 block text-[13px] font-medium">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs leading-relaxed text-muted-foreground">{hint}</span>}
    </label>
  );
}

export function Checkbox({
  checked,
  onChange,
  label,
  hint,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label: string;
  hint?: string;
}) {
  return (
    <label className="mb-4 flex cursor-pointer items-start gap-2">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="mt-0.5 h-3.5 w-3.5 accent-[hsl(var(--multiverse))]"
      />
      <span>
        <span className="block text-[13px] font-medium">{label}</span>
        {hint && <span className="block text-xs leading-relaxed text-muted-foreground">{hint}</span>}
      </span>
    </label>
  );
}

// -- navigation ------------------------------------------------------------

export function Tabs({
  tabs,
  value,
  onChange,
}: {
  tabs: { id: string; label: string; count?: number }[];
  value: string;
  onChange: (id: string) => void;
}) {
  return (
    <div className="flex items-center gap-1 rounded-lg bg-muted p-1">
      {tabs.map((t) => (
        <button
          key={t.id}
          onClick={() => onChange(t.id)}
          className={cn(
            "rounded-md px-3 py-1.5 text-[13px] transition-colors",
            value === t.id
              ? "bg-background text-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground",
          )}
        >
          {t.label}
          {t.count !== undefined && (
            <span className="ml-1.5 font-mono text-[11px] text-muted-foreground">{t.count}</span>
          )}
        </button>
      ))}
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="py-8 text-center text-[13px] text-muted-foreground">{children}</p>;
}

export function ErrorNote({ children }: { children: ReactNode }) {
  return (
    <div className="mb-4 rounded-md border-l-2 border-single bg-single/5 px-3 py-2 text-xs leading-relaxed text-single">
      {children}
    </div>
  );
}
