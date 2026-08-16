/** Light / dark / system.
 *
 * "system" is the default and deliberately sets no attribute — the CSS media
 * query handles it, so the page follows the OS live, including when the OS
 * flips at sunset while the tab is open. An explicit choice stamps
 * `data-theme` on the root element, which wins over the media query in both
 * directions.
 */

export type Theme = "light" | "dark" | "system";

const KEY = "astaverse-theme";

export function getTheme(): Theme {
  const stored = localStorage.getItem(KEY);
  return stored === "light" || stored === "dark" ? stored : "system";
}

export function applyTheme(theme: Theme): void {
  const root = document.documentElement;
  if (theme === "system") root.removeAttribute("data-theme");
  else root.setAttribute("data-theme", theme);
}

export function setTheme(theme: Theme): void {
  if (theme === "system") localStorage.removeItem(KEY);
  else localStorage.setItem(KEY, theme);
  applyTheme(theme);
}

/** Apply before first paint, so the page never flashes the wrong theme. */
export function initTheme(): Theme {
  const theme = getTheme();
  applyTheme(theme);
  return theme;
}
