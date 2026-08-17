/** One claim and its attempts, side by side.
 *
 * A claim is a hypothesis about a dataset; an attempt is one run of it under
 * one configuration. This view exists for the question a single run cannot
 * answer: do my attempts agree, and if not, which choice made them differ?
 *
 * Two things are given prominence because they are what a reader has to know
 * before trusting anything else — whether the attempts agree about fragility,
 * and which forks only some of them found. A decision that one strategy sees
 * and another is blind to is the most informative row on the page.
 */

import { useEffect, useState } from "react";
import { ArrowLeft, GitBranch, Plus } from "lucide-react";
import { STAGES, getClaim, newAttempt } from "./api";
import type { Attempt, ClaimDetail } from "./api";
import { Button, Card, Empty, ErrorNote, Eyebrow, Tag, cn } from "./ui";

const fmt = (v: number | null | undefined, d = 3) =>
  v === null || v === undefined ? "—" : v.toFixed(d);
const signed = (v: number | null | undefined, d = 3) =>
  v === null || v === undefined ? "—" : (v >= 0 ? "+" : "") + v.toFixed(d);

/** What this attempt did differently, in as few words as possible. */
function configSummary(a: Attempt): string {
  const bits = [a.mode ?? "default"];
  if (a.critique) bits.push("+critique");
  if (a.models.length) bits.push(a.models.join("/"));
  if (a.cap != null) bits.push(`cap ${a.cap}`);
  if (a.seeded) bits.push("seeded");
  return bits.join(" · ");
}

/** Labels that actually tell attempts apart.
 *
 * Two attempts can share a configuration — most obviously when both predate a
 * knob, so both read "default". A label that fails to distinguish them makes
 * the comparison unreadable, so collisions fall back to the timestamp in the
 * id, which is always unique. */
function labelsFor(attempts: Attempt[]): Record<string, string> {
  const summaries = attempts.map(configSummary);
  const seen = new Map<string, number>();
  summaries.forEach((s) => seen.set(s, (seen.get(s) ?? 0) + 1));

  const out: Record<string, string> = {};
  attempts.forEach((a, i) => {
    const summary = summaries[i];
    out[a.id] = (seen.get(summary) ?? 0) > 1 ? `${summary} · ${a.id.slice(9, 13)}` : summary;
  });
  return out;
}

function Progress({ a }: { a: Attempt }) {
  return (
    <span className="flex items-center gap-[3px]">
      {STAGES.map((s) => (
        <i
          key={s}
          className={cn(
            "h-1.5 w-2.5 rounded-[1px]",
            a.status[s] === "complete"
              ? "bg-ok"
              : a.status[s] === "ready"
                ? a.running
                  ? "animate-pulse bg-multiverse"
                  : "bg-multiverse/40"
                : "bg-border",
          )}
        />
      ))}
    </span>
  );
}

export function ClaimView({
  claimId,
  onBack,
  onOpenAttempt,
}: {
  claimId: string;
  onBack: () => void;
  onOpenAttempt: (id: string) => void;
}) {
  const [claim, setClaim] = useState<ClaimDetail | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getClaim(claimId).then(setClaim).catch((e) => setError(e.message));
  }, [claimId]);

  if (!claim) return <Empty>{error ?? "Loading…"}</Empty>;

  const unique = Object.entries(claim.unique_decisions);
  const labels = labelsFor(claim.attempts);
  const withResults = claim.attempts.filter((a) => a.fragility != null);

  async function addAttempt() {
    setBusy(true);
    setError(null);
    try {
      const { id } = await newAttempt(claimId);
      onOpenAttempt(id);
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  }

  return (
    <>
      <div className="mb-5 flex items-start gap-4">
        <Button variant="ghost" size="sm" onClick={onBack} className="mt-0.5 shrink-0">
          <ArrowLeft size={13} /> All claims
        </Button>
        <div className="min-w-0">
          <h1 className="max-w-[80ch] text-[17px] font-medium leading-snug">{claim.hypothesis}</h1>
          <p className="mt-1 flex items-center gap-2 font-mono text-[11px] text-muted-foreground">
            <Tag>{claim.dataset_name}</Tag>
            {claim.n_attempts} attempt{claim.n_attempts === 1 ? "" : "s"}
          </p>
        </div>
        <Button variant="primary" onClick={addAttempt} disabled={busy} className="ml-auto shrink-0">
          <Plus size={13} /> {busy ? "Creating…" : "New attempt"}
        </Button>
      </div>

      {error && <ErrorNote>{error}</ErrorNote>}

      {/* Do the attempts agree? This gates how much any single number is worth. */}
      {claim.agreement && (
        <div
          className={cn(
            "mb-5 rounded-lg border-l-[3px] p-4",
            claim.agreement === "disagree"
              ? "border-single bg-single/5"
              : "border-ok bg-ok/5",
          )}
        >
          <Eyebrow className="mb-1">Across attempts</Eyebrow>
          {claim.agreement === "disagree" ? (
            <p className="text-[13px] leading-relaxed">
              The attempts <strong>disagree</strong> about whether this claim is fragile
              {claim.fragility_range &&
                ` (fragility ${fmt(claim.fragility_range.min)} to ${fmt(claim.fragility_range.max)})`}
              . That indicts the method rather than the data — compare the decision spaces below
              before trusting either number.
            </p>
          ) : (
            <p className="text-[13px] leading-relaxed">
              The attempts <strong>agree</strong> about fragility
              {claim.fragility_range &&
                ` (${fmt(claim.fragility_range.min)} to ${fmt(claim.fragility_range.max)} across ${claim.fragility_range.n})`}
              . A conclusion that survives different extraction strategies is worth more than one
              that only survives its own.
            </p>
          )}
        </div>
      )}

      {/* The most informative comparison: forks only some strategies saw. */}
      {unique.length > 0 && (
        <Card className="mb-5 p-4">
          <div className="mb-1 flex items-center gap-2">
            <GitBranch size={13} className="text-muted-foreground" />
            <Eyebrow>Decisions found by only some attempts</Eyebrow>
          </div>
          <p className="mb-3 text-xs leading-relaxed text-muted-foreground">
            A fork one attempt found and another missed is either a false positive or a blind
            spot. Either way it is the first thing to look at.
            {claim.shared_decisions.length > 0 && (
              <> {claim.shared_decisions.length} decision(s) were found by every attempt.</>
            )}
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr>
                  <th className="border-b border-border pb-2 pr-3">
                    <Eyebrow>Decision</Eyebrow>
                  </th>
                  <th className="border-b border-border pb-2">
                    <Eyebrow>Found by</Eyebrow>
                  </th>
                </tr>
              </thead>
              <tbody>
                {unique.map(([decision, finders]) => (
                  <tr key={decision}>
                    <td className="border-b border-border/50 py-1.5 pr-3 font-mono">{decision}</td>
                    <td className="border-b border-border/50 py-1.5">
                      {finders.map((f) => (
                        <button
                          key={f}
                          onClick={() => onOpenAttempt(f)}
                          className="mr-1.5 font-mono text-multiverse hover:underline"
                        >
                          {labels[f] ?? f.slice(0, 13)}
                        </button>
                      ))}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      <Eyebrow className="mb-2">Attempts</Eyebrow>
      <Card>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-border">
                {[
                  "Configuration",
                  "Progress",
                  "Decisions",
                  "Universes",
                  "Verdicts",
                  "Joint",
                  "Fragility",
                  "Most flips",
                ].map((h) => (
                  <th key={h} className="px-3 py-2.5">
                    <Eyebrow>{h}</Eyebrow>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {claim.attempts.map((a) => (
                <tr
                  key={a.id}
                  onClick={() => onOpenAttempt(a.id)}
                  className="cursor-pointer border-b border-border/60 last:border-0 hover:bg-accent/60"
                >
                  <td className="px-3 py-3">
                    <span className="block font-mono text-[12px]">{labels[a.id]}</span>
                    <span className="mt-0.5 block font-mono text-[10px] text-muted-foreground">
                      {a.id.slice(0, 13)}
                    </span>
                  </td>
                  <td className="px-3 py-3">
                    <div className="flex items-center gap-2">
                      <Progress a={a} />
                      <span className="tabular font-mono text-[10px] text-muted-foreground">
                        {a.n_complete}/{STAGES.length}
                      </span>
                    </div>
                  </td>
                  <td className="tabular px-3 py-3">{a.decisions.length || "—"}</td>
                  <td className="tabular px-3 py-3">
                    {a.n_universes ?? "—"}
                    {a.coverage != null && a.coverage < 1 && (
                      <span
                        className="ml-1 text-warn"
                        title={`only ${Math.round(a.coverage * 100)}% of the grid ran`}
                      >
                        {Math.round(a.coverage * 100)}%
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-3">
                    {Object.keys(a.verdicts).length === 0
                      ? "—"
                      : Object.entries(a.verdicts).map(([v, n]) => (
                          <span key={v} className="mr-1 whitespace-nowrap">
                            <span className="tabular">{n}</span>{" "}
                            <span className="text-muted-foreground">{v.replace(/_/g, " ")}</span>
                          </span>
                        ))}
                  </td>
                  <td className="tabular px-3 py-3">{signed(a.joint_surprisal)}</td>
                  <td
                    className={cn(
                      "tabular px-3 py-3",
                      (a.fragility ?? 0) > 0.1 && "text-single",
                    )}
                  >
                    {fmt(a.fragility)}
                  </td>
                  <td className="px-3 py-3 font-mono">
                    {a.top_flip ? (
                      <>
                        {a.top_flip}{" "}
                        <span className="text-muted-foreground">
                          {((a.top_flip_rate ?? 0) * 100).toFixed(1)}%
                        </span>
                      </>
                    ) : (
                      "—"
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {withResults.length < 2 && (
        <p className="mt-3 text-xs text-muted-foreground">
          Comparison gets useful with two or more attempts carried through to surprisal. Use{" "}
          <span className="font-mono">New attempt</span>, change one thing, and run it — or{" "}
          <span className="font-mono">astaverse again &lt;id&gt; --decisions.mode schema_lint</span>.
        </p>
      )}
    </>
  );
}
