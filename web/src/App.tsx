import { useCallback, useEffect, useState } from "react";
import { listClaims } from "./api";
import type { ClaimDetail } from "./api";
import { AnalysisDetail } from "./AnalysisDetail";
import { ClaimList } from "./ClaimList";
import { ClaimView } from "./ClaimView";
import { NewRun } from "./NewRun";
import { TopBar } from "./TopBar";
import { ErrorNote } from "./ui";
import "./index.css";

/** Claim → attempt → stage. Each level answers a different question:
 *  which claims do I have, do my attempts at one agree, and what did a
 *  particular attempt actually do. */
type View =
  | { name: "claims" }
  | { name: "new" }
  | { name: "claim"; id: string }
  | { name: "attempt"; id: string; claimId?: string };

export default function App() {
  const [claims, setClaims] = useState<ClaimDetail[]>([]);
  const [view, setView] = useState<View>({ name: "claims" });
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setClaims(await listClaims());
  }, []);

  useEffect(() => {
    refresh().catch((e) => setError(e.message));
  }, [refresh, view]);

  const claimOf = (attemptId: string) =>
    claims.find((c) => c.attempts.some((a) => a.id === attemptId))?.id;

  return (
    <div className="min-h-full">
      <TopBar />
      <main className="mx-auto w-full max-w-[1400px] px-6 py-6">
        {error && <ErrorNote>{error}</ErrorNote>}

        {view.name === "claims" && (
          <ClaimList
            claims={claims}
            onOpen={(id) => setView({ name: "claim", id })}
            onNew={() => setView({ name: "new" })}
          />
        )}

        {view.name === "new" && (
          <NewRun
            onCancel={() => setView({ name: "claims" })}
            onCreated={async (id) => {
              await refresh();
              setView({ name: "attempt", id });
            }}
          />
        )}

        {view.name === "claim" && (
          <ClaimView
            claimId={view.id}
            onBack={() => setView({ name: "claims" })}
            onOpenAttempt={(id) => setView({ name: "attempt", id, claimId: view.id })}
          />
        )}

        {view.name === "attempt" && (
          <AnalysisDetail
            id={view.id}
            onBack={() => {
              const claimId = view.claimId ?? claimOf(view.id);
              setView(claimId ? { name: "claim", id: claimId } : { name: "claims" });
            }}
          />
        )}
      </main>
    </div>
  );
}
