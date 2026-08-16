import { useState } from "react";
import { getTheme, setTheme } from "./theme";
import type { Theme } from "./theme";

const OPTIONS: { id: Theme; label: string }[] = [
  { id: "light", label: "Light" },
  { id: "dark", label: "Dark" },
  { id: "system", label: "System" },
];

export function ThemeSwitch() {
  const [theme, setLocal] = useState<Theme>(getTheme);

  return (
    <div className="theme-switch" role="group" aria-label="Colour theme">
      {OPTIONS.map((o) => (
        <button
          key={o.id}
          aria-pressed={theme === o.id}
          onClick={() => {
            setTheme(o.id);
            setLocal(o.id);
          }}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
