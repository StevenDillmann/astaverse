import { useCallback, useEffect, useState } from "react";
import { listRuns } from "./api";
import type { RunSummary } from "./api";
import { AnalysisDetail } from "./AnalysisDetail";
import { AnalysisList } from "./AnalysisList";
import { NewRun } from "./NewRun";
import { TopBar } from "./TopBar";
import { ErrorNote } from "./ui";
import "./index.css";

type View = { name: "list" } | { name: "new" } | { name: "detail"; id: string };

export default function App() {
  const [analyses, setAnalyses] = useState<RunSummary[]>([]);
  const [view, setView] = useState<View>({ name: "list" });
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setAnalyses(await listRuns());
  }, []);

  useEffect(() => {
    refresh().catch((e) => setError(e.message));
  }, [refresh, view]);

  return (
    <div className="min-h-full">
      <TopBar />
      <main className="mx-auto w-full max-w-[1400px] px-6 py-6">
        {error && <ErrorNote>{error}</ErrorNote>}

        {view.name === "list" && (
          <AnalysisList
            analyses={analyses}
            onOpen={(id) => setView({ name: "detail", id })}
            onNew={() => setView({ name: "new" })}
          />
        )}

        {view.name === "new" && (
          <NewRun
            onCancel={() => setView({ name: "list" })}
            onCreated={async (id) => {
              await refresh();
              setView({ name: "detail", id });
            }}
          />
        )}

        {view.name === "detail" && (
          <AnalysisDetail id={view.id} onBack={() => setView({ name: "list" })} />
        )}
      </main>
    </div>
  );
}
