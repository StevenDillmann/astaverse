/** The persistent header: identity left, controls right.
 *
 * The theme control is a sun / moon / monitor trio rather than a single
 * toggle, because "follow the system" is a real third choice and a two-state
 * switch cannot express it.
 */

import { Monitor, Moon, Sun, Terminal } from "lucide-react";
import { useState } from "react";
import { getTheme, setTheme } from "./theme";
import type { Theme } from "./theme";
import { cn } from "./ui";

const THEMES: { id: Theme; Icon: typeof Sun; label: string }[] = [
  { id: "light", Icon: Sun, label: "Light" },
  { id: "dark", Icon: Moon, label: "Dark" },
  { id: "system", Icon: Monitor, label: "Follow system" },
];

function ThemeToggle() {
  const [theme, setLocal] = useState<Theme>(getTheme);
  return (
    <div className="flex items-center gap-0.5 rounded-full border border-border p-0.5">
      {THEMES.map(({ id, Icon, label }) => (
        <button
          key={id}
          title={label}
          aria-label={label}
          aria-pressed={theme === id}
          onClick={() => {
            setTheme(id);
            setLocal(id);
          }}
          className={cn(
            "rounded-full p-1.5 transition-colors",
            theme === id
              ? "bg-foreground text-background"
              : "text-muted-foreground hover:text-foreground",
          )}
        >
          <Icon size={13} strokeWidth={2} />
        </button>
      ))}
    </div>
  );
}

export function TopBar({ right }: { right?: React.ReactNode }) {
  return (
    <header className="sticky top-0 z-20 border-b border-border bg-background/85 backdrop-blur">
      <div className="flex items-center gap-4 px-6 py-3">
        <div className="flex items-center gap-2">
          <Terminal size={17} className="text-multiverse" strokeWidth={2.2} />
          <span className="font-mono text-[13px] font-semibold uppercase tracking-[0.16em]">
            Astaverse
          </span>
        </div>
        <p className="hidden text-xs text-muted-foreground md:block">
          Multiverse analysis and robust surprisal
        </p>

        <div className="ml-auto flex items-center gap-3">
          {right}
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}
