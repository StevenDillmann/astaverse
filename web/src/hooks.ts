import { useCallback, useEffect, useState } from "react";

export function useAsync<T>(loader: () => Promise<T>, dependencies: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await loader());
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setLoading(false);
    }
    // The caller owns dependency stability, like React's built-in effects.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, dependencies);

  useEffect(() => {
    void reload();
  }, [reload]);

  return { data, error, loading, reload, setData };
}

export function usePath() {
  const [path, setPath] = useState(() => window.location.pathname + window.location.search);
  useEffect(() => {
    const update = () => setPath(window.location.pathname + window.location.search);
    window.addEventListener("popstate", update);
    return () => window.removeEventListener("popstate", update);
  }, []);
  return path;
}

type HistoryState = { from?: string } | null;

function currentPath() {
  return window.location.pathname + window.location.search;
}

export function navigate(to: string) {
  // Record where we came from, so a back link can return there instead of to a
  // hardcoded parent — and can tell an in-app hop from a cold page load.
  window.history.pushState({ from: currentPath() }, "", to);
  window.dispatchEvent(new PopStateEvent("popstate"));
  window.scrollTo({ top: 0, behavior: "instant" });
}

/** Where "back" should actually go.
 *
 * With in-app history behind us, back means back — the page you were on, at the
 * scroll position you left it. On a cold load there is no such page, so the
 * caller supplies its own parent and `label` is null for the caller to name.
 */
export function useBackTarget() {
  const read = () => (window.history.state as HistoryState)?.from ?? null;
  const [origin, setOrigin] = useState<string | null>(read);
  useEffect(() => {
    const update = () => setOrigin(read());
    window.addEventListener("popstate", update);
    return () => window.removeEventListener("popstate", update);
  }, []);

  const go = useCallback(
    (fallbackPath: string) => {
      if (origin) window.history.back();
      else navigate(fallbackPath);
    },
    [origin],
  );

  return { label: origin ? routeLabel(origin) : null, go };
}

/** A short name for a route, for use as a back-link label. */
export function routeLabel(path: string) {
  const [segment, rest] = path.split("?")[0].replace(/^\//, "").split("/");
  if (!segment) return "Overview";
  const named: Record<string, string> = {
    datasets: "Datasets",
    hypotheses: "Hypotheses",
    experiments: "Experiments",
    settings: "Settings",
  };
  if (!rest) return named[segment] || segment;
  if (rest === "new") return named[segment] || segment;
  // A dataset is addressed by name, so it can label itself; ids cannot.
  if (segment === "datasets") return decodeURIComponent(rest);
  if (segment === "hypotheses") return "Hypothesis";
  if (segment === "experiments") return "Experiment";
  return named[segment] || segment;
}

/**
 * Which rows a bulk action applies to.
 *
 * Selection is held as ids rather than rows so it survives refiltering: hiding
 * a row with a search box must not silently drop it from the set the user has
 * already chosen, and reordering must not scramble it.
 */
export function useSelection() {
  const [selected, setSelected] = useState<ReadonlySet<string>>(new Set());

  const toggle = (id: string) =>
    setSelected((current) => {
      const next = new Set(current);
      if (!next.delete(id)) next.add(id);
      return next;
    });

  const setMany = (ids: string[], on: boolean) =>
    setSelected((current) => {
      const next = new Set(current);
      for (const id of ids) {
        if (on) next.add(id);
        else next.delete(id);
      }
      return next;
    });

  const clear = () => setSelected(new Set());

  return { selected, toggle, setMany, clear };
}
