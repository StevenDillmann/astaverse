/** Per-stage artifact views. Each stage shows the thing it actually produced. */

import { SpecCurve } from "./SpecCurve";
import type { Stage } from "./api";

const fmt = (v: number | null | undefined, digits = 3) =>
  v === null || v === undefined ? "—" : v.toFixed(digits);

const signed = (v: number | null | undefined, digits = 3) =>
  v === null || v === undefined ? "—" : (v >= 0 ? "+" : "") + v.toFixed(digits);

export function StagePanel({ stage, artifact }: { stage: Stage; artifact: any }) {
  if (!artifact) {
    return <p className="text-[13px] text-muted-foreground">Not run yet. Run this stage to see its output.</p>;
  }

  switch (stage) {
    case "study":
      return <Study a={artifact} />;
    case "plans":
      return <Plans a={artifact} />;
    case "decisions":
      return <Decisions a={artifact} />;
    case "universes":
      return <Universes a={artifact} />;
    case "task":
      return <Task a={artifact} />;
    case "execute":
      return <Execute a={artifact} />;
    case "verdicts":
      return <Verdicts a={artifact} />;
    case "surprisal":
      return <Surprisal a={artifact} />;
    default:
      return <pre className="overflow-x-auto whitespace-pre-wrap break-words rounded-md border border-border bg-muted/40 p-3 font-mono text-[11px] leading-relaxed">{JSON.stringify(artifact, null, 2)}</pre>;
  }
}

function Study({ a }: { a: any }) {
  return (
    <>
      <p className="max-w-[70ch] text-[13px] leading-relaxed text-muted-foreground">{a.dataset_description || "No dataset description available."}</p>
      <p className="text-[13px] text-muted-foreground" style={{ margin: "16px 0" }}>
        {a.n_rows} rows · {a.columns.length} columns · {a.dataset_path}
      </p>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead>
            <tr>
              <th className="border-b border-border px-0 pb-2 pr-3 font-mono text-[10px] font-normal uppercase tracking-wider text-muted-foreground">column</th>
              <th className="border-b border-border px-0 pb-2 pr-3 font-mono text-[10px] font-normal uppercase tracking-wider text-muted-foreground">type</th>
              <th className="border-b border-border px-0 pb-2 pr-3 font-mono text-[10px] font-normal uppercase tracking-wider text-muted-foreground">range</th>
              <th className="border-b border-border px-0 pb-2 pr-3 font-mono text-[10px] font-normal uppercase tracking-wider text-muted-foreground">description</th>
            </tr>
          </thead>
          <tbody>
            {a.columns.map((c: any) => (
              <tr key={c.name}>
                <td className="border-b border-border/50 py-2 pr-3 align-top">{c.name}</td>
                <td className="border-b border-border/50 py-2 pr-3 align-top">{c.dtype}</td>
                <td className="tabular border-b border-border/50 py-2 pr-3 align-top">
                  {c.min !== null && c.max !== null ? `${c.min} – ${c.max}` : "—"}
                </td>
                <td className="border-b border-border/50 py-2 pr-3 align-top text-muted-foreground">{c.description || ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

function Plans({ a }: { a: any }) {
  return (
    <>
      <p className="text-[13px] text-muted-foreground" style={{ marginBottom: 16 }}>
        {a.plans.length} plans sampled from {a.model} at temperature {a.temperature}. Where these
        disagree is what stage 3 extracts.
      </p>
      {a.plans.map((p: any) => (
        <div className="mb-3 rounded-md border border-border p-4" key={p.id}>
          <h3 className="mb-1 font-mono text-[13px]">
            {p.id} <span className="ml-1 inline-flex items-center rounded bg-muted px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">plan</span>
          </h3>
          <p className="mb-3 text-xs leading-relaxed text-muted-foreground">{p.objective}</p>
          <details>
            <summary className="cursor-pointer text-[11px] text-muted-foreground">
              steps, deliverables, rationale
            </summary>
            <pre style={{ marginTop: 8 }}>
              {`STEPS\n${p.steps}\n\nDELIVERABLES\n${p.deliverables}\n\nRATIONALE\n${p.rationale ?? ""}`}
            </pre>
          </details>
        </div>
      ))}
    </>
  );
}

function Decisions({ a }: { a: any }) {
  const decisions: Record<string, any> = a.decisions ?? {};
  return (
    <>
      <p className="text-[13px] text-muted-foreground" style={{ marginBottom: 16 }}>
        {Object.keys(decisions).length} decisions. Each is a point where the sampled plans diverged
        or left a choice unstated.
      </p>
      {Object.entries(decisions).map(([id, d]: [string, any]) => {
        const ext = d.x_astaverse ?? {};
        return (
          <div className="mb-3 rounded-md border border-border p-4" key={id}>
            <h3 className="mb-1 font-mono text-[13px]">
              {id} <span className="ml-1 inline-flex items-center rounded bg-muted px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">{ext.kind ?? "decision"}</span>
              {ext.post_hoc && <span className="ml-1 inline-flex items-center rounded bg-muted px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wider text-muted-foreground"> post-hoc</span>}
            </h3>
            <p className="mb-3 text-xs leading-relaxed text-muted-foreground">{d.rationale || d.label}</p>
            <ul className="m-0 list-none p-0">
              {Object.entries(d.options ?? {}).map(([oid, o]: [string, any]) => (
                <li key={oid} className="grid grid-cols-[160px_1fr] gap-3 border-t border-dotted border-border py-2">
                  <span className="font-mono text-multiverse">
                    {oid}
                    {oid === d.default && (
                      <span className="ml-1 text-[10px] uppercase tracking-wider text-muted-foreground">default</span>
                    )}
                  </span>
                  <span className="border-b border-border/50 py-2 pr-3 align-top text-muted-foreground">{o.description || o.label}</span>
                </li>
              ))}
            </ul>
          </div>
        );
      })}
    </>
  );
}

function Universes({ a }: { a: any }) {
  const ids = a.universes.length
    ? Object.keys(a.universes[0].decisions)
    : ([] as string[]);
  return (
    <>
      <p className="text-[13px] text-muted-foreground" style={{ marginBottom: 16 }}>
        {a.universes.length} universes to execute, from a grid of {a.n_total_grid}.
        {a.n_dropped_constraints > 0 && ` ${a.n_dropped_constraints} ruled out by constraints.`}
      </p>
      {a.n_dropped_cap > 0 && (
        <div className="mb-4 rounded-md border-l-2 border-single bg-single/5 px-3 py-2 text-xs leading-relaxed text-single">
          {a.n_dropped_cap} universes dropped by the cap of {a.cap}. The reported distribution
          covers only what ran.
        </div>
      )}
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead>
            <tr>
              <th className="border-b border-border px-0 pb-2 pr-3 font-mono text-[10px] font-normal uppercase tracking-wider text-muted-foreground">universe</th>
              {ids.map((d) => (
                <th key={d}>{d}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {a.universes.map((u: any) => (
              <tr key={u.id}>
                <td className="border-b border-border/50 py-2 pr-3 align-top">
                  {u.id}
                  {u.is_default && (
                    <span className="text-single"> ← single-universe baseline</span>
                  )}
                </td>
                {ids.map((d) => (
                  <td key={d}>{u.decisions[d]}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

function Task({ a }: { a: any }) {
  return (
    <>
      <p className="text-[13px] text-muted-foreground" style={{ marginBottom: 16 }}>
        {a.task_name} · {a.n_universes} universes · {a.files.length} files
      </p>
      <pre className="overflow-x-auto whitespace-pre-wrap break-words rounded-md border border-border bg-muted/40 p-3 font-mono text-[11px] leading-relaxed">{a.files.join("\n")}</pre>
      <p className="text-[13px] text-muted-foreground" style={{ marginTop: 16 }}>
        {a.task_dir}
      </p>
    </>
  );
}

function Execute({ a }: { a: any }) {
  return (
    <>
      {a.dry_run && <p className="text-[13px] text-muted-foreground">Dry run — nothing was executed.</p>}
      {a.jobs.map((j: any) => (
        <div className="mb-3 rounded-md border border-border p-4" key={j.job_name}>
          <h3 className="mb-1 font-mono text-[13px]">
            {j.job_name}{" "}
            <span className="ml-1 inline-flex items-center rounded bg-muted px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">{j.returncode === 0 ? "ok" : `exit ${j.returncode ?? "—"}`}</span>
          </h3>
          <p className="mb-3 text-xs leading-relaxed text-muted-foreground">
            {j.agent}
            {j.model ? ` · ${j.model}` : ""}
          </p>
          <pre className="overflow-x-auto whitespace-pre-wrap break-words rounded-md border border-border bg-muted/40 p-3 font-mono text-[11px] leading-relaxed">{j.command.join(" ")}</pre>
        </div>
      ))}
    </>
  );
}

function Verdicts({ a }: { a: any }) {
  const counts: Record<string, number> = {};
  a.results.forEach((r: any) => (counts[r.verdict] = (counts[r.verdict] ?? 0) + 1));

  // The classic specification curve: the effect estimate per specification.
  // Uses the standardized estimand, since raw coefficients across different
  // outcome scales are not comparable and would plot unit changes as spread.
  const points = a.results
    .filter((r: any) => (r.stats.estimate_standardized ?? r.stats.estimate) != null)
    .map((r: any) => ({
      universe_id: `${r.universe_id} · ${r.verdict_rule}`,
      decisions: r.decisions,
      verdict: r.verdict,
      value: r.stats.estimate_standardized ?? r.stats.estimate,
      is_default: r.is_default,
    }));
  const standardized = a.results.some((r: any) => r.stats.estimate_standardized != null);
  const sortedVals = points.map((p: any) => p.value).sort((x: number, y: number) => x - y);
  const median = sortedVals.length
    ? sortedVals[Math.floor(sortedVals.length / 2)]
    : 0;

  return (
    <>
      {a.missing_universe_ids?.length > 0 && (
        <div className="mb-4 rounded-md border-l-2 border-single bg-single/5 px-3 py-2 text-xs leading-relaxed text-single">
          Incomplete: {a.missing_universe_ids.length} universes were never reported (
          {a.missing_universe_ids.slice(0, 6).join(", ")}). Everything below covers only what
          came back.
        </div>
      )}
      <div className="mb-6 grid grid-cols-2 gap-px overflow-hidden rounded-md border border-border bg-border sm:grid-cols-3 lg:grid-cols-5">
        {Object.entries(counts).map(([verdict, n]) => (
          <div className="bg-card p-4" key={verdict}>
            <span className="mb-1 block font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground">{verdict.replace(/_/g, " ")}</span>
            <span className="tabular text-[22px] tracking-tight">{n}</span>
          </div>
        ))}
      </div>
      <p className="text-[13px] text-muted-foreground" style={{ marginBottom: 16 }}>
        Verdict rules applied: {a.verdict_rules.join(", ")}. Assigned here from the reported
        statistics — the agent never saw a verdict field.
      </p>

      {a.decision_flips?.length > 0 && (
        <>
          <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground" style={{ marginTop: 28 }}>
            Which decisions flip the verdict
          </p>
          <p className="text-[13px] text-muted-foreground" style={{ marginBottom: 10 }}>
            Over matched pairs — two specifications identical except for this one choice. A high
            rate means the conclusion turns on an analytic decision rather than on the data.
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr>
                  <th className="border-b border-border px-0 pb-2 pr-3 font-mono text-[10px] font-normal uppercase tracking-wider text-muted-foreground">decision</th>
                  <th className="border-b border-border px-0 pb-2 pr-3 font-mono text-[10px] font-normal uppercase tracking-wider text-muted-foreground">flips</th>
                  <th className="border-b border-border px-0 pb-2 pr-3 font-mono text-[10px] font-normal uppercase tracking-wider text-muted-foreground">matched pairs</th>
                  <th />
                  <th className="border-b border-border px-0 pb-2 pr-3 font-mono text-[10px] font-normal uppercase tracking-wider text-muted-foreground">which swaps flip it</th>
                </tr>
              </thead>
              <tbody>
                {a.decision_flips.map((f: any) => (
                  <tr key={f.decision_id}>
                    <td className="border-b border-border/50 py-2 pr-3 align-top">{f.decision_id}</td>
                    <td className="tabular" style={{ color: f.n_flips ? "var(--single)" : undefined }}>
                      {(f.flip_rate * 100).toFixed(1)}%
                    </td>
                    <td className="tabular border-b border-border/50 py-2 pr-3 align-top text-muted-foreground">
                      {f.n_flips}/{f.n_pairs}
                    </td>
                    <td style={{ width: 90 }}>
                      <span className="block h-1 overflow-hidden rounded bg-muted">
                        <i style={{ width: `${Math.min(f.flip_rate * 100 * 4, 100)}%` }} />
                      </span>
                    </td>
                    <td className="border-b border-border/50 py-2 pr-3 align-top text-muted-foreground">{f.flip_examples.join(", ") || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {points.length > 1 && (
        <>
          <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground" style={{ marginTop: 32 }}>
            Specification curve
          </p>
          <p className="text-[13px] text-muted-foreground" style={{ marginBottom: 10 }}>
            {standardized
              ? "Standardized effect per specification, sorted."
              : "Raw effect per specification — NOT standardized, so values on different outcome scales are not comparable."}{" "}
            Below the curve, each row marks which option a specification used; a band that tracks
            the curve is the decision driving it.
          </p>
          <div className="mb-3 flex flex-wrap gap-5 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
            <span>
              <i style={{ background: "hsl(var(--ok))" }} />
              supported
            </span>
            <span>
              <i style={{ background: "hsl(var(--muted-foreground))" }} />
              not supported
            </span>
            <span>
              <i style={{ background: "hsl(var(--single))" }} />
              default / single-universe
            </span>
          </div>
          <SpecCurve
            universes={points}
            median={median}
            valueLabel={standardized ? "standardized effect" : "effect (unstandardized)"}
            colorByVerdict
          />
        </>
      )}

      <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground" style={{ marginTop: 32 }}>
        All results
      </p>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead>
            <tr>
              <th className="border-b border-border px-0 pb-2 pr-3 font-mono text-[10px] font-normal uppercase tracking-wider text-muted-foreground">universe</th>
              <th className="border-b border-border px-0 pb-2 pr-3 font-mono text-[10px] font-normal uppercase tracking-wider text-muted-foreground">rule</th>
              <th className="border-b border-border px-0 pb-2 pr-3 font-mono text-[10px] font-normal uppercase tracking-wider text-muted-foreground">estimate</th>
              <th className="border-b border-border px-0 pb-2 pr-3 font-mono text-[10px] font-normal uppercase tracking-wider text-muted-foreground">p</th>
              <th className="border-b border-border px-0 pb-2 pr-3 font-mono text-[10px] font-normal uppercase tracking-wider text-muted-foreground">n</th>
              <th className="border-b border-border px-0 pb-2 pr-3 font-mono text-[10px] font-normal uppercase tracking-wider text-muted-foreground">verdict</th>
            </tr>
          </thead>
          <tbody>
            {a.results.map((r: any, i: number) => (
              <tr key={`${r.universe_id}-${r.verdict_rule}-${i}`}>
                <td className="border-b border-border/50 py-2 pr-3 align-top">{r.universe_id}</td>
                <td className="border-b border-border/50 py-2 pr-3 align-top text-muted-foreground">{r.verdict_rule}</td>
                <td className="tabular border-b border-border/50 py-2 pr-3 align-top">{fmt(r.stats.estimate)}</td>
                <td className="tabular border-b border-border/50 py-2 pr-3 align-top">{fmt(r.stats.p_value, 4)}</td>
                <td className="tabular border-b border-border/50 py-2 pr-3 align-top">{r.stats.n ?? "—"}</td>
                <td
                  style={{
                    color:
                      r.verdict === "supported"
                        ? "hsl(var(--ok))"
                        : r.verdict === "failed"
                          ? "hsl(var(--muted-foreground))"
                          : "hsl(var(--foreground))",
                  }}
                >
                  {r.verdict.replace(/_/g, " ")}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

function Surprisal({ a }: { a: any }) {
  const fragile = (a.fragility_index ?? 0) > 0.1;
  return (
    <>
      {/* The belief update. Every universe analyses the same data, so they are
          not independent evidence — this is one posterior conditioned on the
          multiverse as a whole, and it is the number a reward should use. */}
      <div className="rounded-lg border border-foreground/80 border-l-[3px] bg-card p-5">
        <span className="mb-1 block font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground">Joint surprisal — the belief update</span>
        <span className="tabular my-2 block text-[44px] leading-none tracking-tight">
          {a.joint_surprisal == null ? "—" : signed(a.joint_surprisal)}
        </span>
        <p className="text-[13px] text-muted-foreground" style={{ margin: 0 }}>
          One update conditioned on all {a.n_universes} specifications at once. They share a
          dataset, so they are one body of evidence rather than {a.n_universes} independent
          studies — an average of per-universe posteriors would not be a posterior at all.
          Prior {fmt(a.prior_mean)} → posterior {fmt(a.joint_posterior_mean)}.
        </p>
      </div>

      <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground" style={{ marginTop: 28 }}>
        Diagnostics — how much to trust it
      </p>
      <p className="text-[13px] text-muted-foreground" style={{ marginBottom: 10 }}>
        A sensitivity analysis over the same evidence, not extra evidence.
      </p>
      <div className="mb-6 grid grid-cols-2 gap-px overflow-hidden rounded-md border border-border bg-border sm:grid-cols-3 lg:grid-cols-5">
        <div className="bg-card p-4">
          <span className="mb-1 block font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground">median</span>
          <span className="tabular text-[22px] tracking-tight">{signed(a.median)}</span>
        </div>
        <div className="bg-card p-4">
          <span className="mb-1 block font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground">IQR</span>
          <span className="tabular text-[22px] tracking-tight">{fmt(a.iqr)}</span>
        </div>
        <div className="bg-card p-4">
          <span className="mb-1 block font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground">sign agreement</span>
          <span className="tabular text-[22px] tracking-tight">{Math.round(a.sign_consistency * 100)}%</span>
        </div>
        <div className="bg-card p-4">
          <span className="mb-1 block font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground">single universe</span>
          <span className="tabular text-[22px] tracking-tight text-single">
            {signed(a.single_universe_surprisal)}
          </span>
        </div>
        <div className="bg-card p-4">
          <span className="mb-1 block font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground">fragility</span>
          <span className="tabular text-[22px] tracking-tight">{fmt(a.fragility_index)}</span>
        </div>
      </div>

      {fragile && (
        <div className="mb-4 rounded-md border-l-2 border-single bg-single/5 px-3 py-2 text-xs leading-relaxed text-single">
          The single-universe answer sits {fmt(a.fragility_index)} from the multiverse median. A
          pipeline reporting only that number would have reported an artifact of one arbitrary
          analytic choice.
        </div>
      )}

      <p className="text-[13px] text-muted-foreground" style={{ marginBottom: 10 }}>
        Per-specification surprisal, sorted. The specification curve of the underlying{" "}
        <em>effects</em> is on the verdicts stage; this one shows how belief would move if you
        took each specification alone.
      </p>
      <div className="mb-3 flex flex-wrap gap-5 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
        <span>
          <i style={{ background: "hsl(var(--multiverse))" }} />
          specification
        </span>
        <span>
          <i style={{ background: "hsl(var(--single))" }} />
          default / single-universe
        </span>
      </div>

      <SpecCurve
        universes={a.per_universe.map((u: any) => ({ ...u, value: u.surprisal }))}
        median={a.median}
        valueLabel="surprisal"
      />

      {a.between_agent_spread !== null && a.between_agent_spread !== undefined && (
        <p className="text-[13px] text-muted-foreground" style={{ marginTop: 16 }}>
          Between-agent spread {fmt(a.between_agent_spread)} vs between-universe IQR {fmt(a.iqr)}.
          {a.between_agent_spread < a.iqr
            ? " Decision variance dominates — the multiverse is measuring the analysis, not the agent."
            : " Agent variance rivals decision variance; treat the curve with caution."}
        </p>
      )}

      {a.decision_sensitivity?.length > 0 && (
        <>
          <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground" style={{ margin: "28px 0 10px" }}>
            Which decisions actually moved the result
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr>
                  <th className="border-b border-border px-0 pb-2 pr-3 font-mono text-[10px] font-normal uppercase tracking-wider text-muted-foreground">decision</th>
                  <th className="border-b border-border px-0 pb-2 pr-3 font-mono text-[10px] font-normal uppercase tracking-wider text-muted-foreground">kind</th>
                  <th className="border-b border-border px-0 pb-2 pr-3 font-mono text-[10px] font-normal uppercase tracking-wider text-muted-foreground">spread</th>
                  <th className="border-b border-border px-0 pb-2 pr-3 font-mono text-[10px] font-normal uppercase tracking-wider text-muted-foreground">mean surprisal by option</th>
                </tr>
              </thead>
              <tbody>
                {a.decision_sensitivity.map((d: any) => (
                  <tr key={d.decision_id}>
                    <td className="border-b border-border/50 py-2 pr-3 align-top">{d.decision_id}</td>
                    <td className="border-b border-border/50 py-2 pr-3 align-top text-muted-foreground">{d.kind}</td>
                    <td className="tabular border-b border-border/50 py-2 pr-3 align-top">{fmt(d.spread)}</td>
                    <td className="tabular border-b border-border/50 py-2 pr-3 align-top">
                      {Object.entries(d.option_means)
                        .map(([o, m]: [string, any]) => `${o} ${signed(m)}`)
                        .join("   ")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </>
  );
}
