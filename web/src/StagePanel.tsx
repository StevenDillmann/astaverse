/** Per-stage artifact views. Each stage shows the thing it actually produced. */

import { SpecCurve } from "./SpecCurve";
import type { Stage } from "./api";

const fmt = (v: number | null | undefined, digits = 3) =>
  v === null || v === undefined ? "—" : v.toFixed(digits);

const signed = (v: number | null | undefined, digits = 3) =>
  v === null || v === undefined ? "—" : (v >= 0 ? "+" : "") + v.toFixed(digits);

export function StagePanel({ stage, artifact }: { stage: Stage; artifact: any }) {
  if (!artifact) {
    return <p className="empty">Not run yet. Run this stage to see its output.</p>;
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
      return <pre>{JSON.stringify(artifact, null, 2)}</pre>;
  }
}

function Study({ a }: { a: any }) {
  return (
    <>
      <p className="prose">{a.dataset_description || "No dataset description available."}</p>
      <p className="empty" style={{ margin: "16px 0" }}>
        {a.n_rows} rows · {a.columns.length} columns · {a.dataset_path}
      </p>
      <div className="scroll-x">
        <table>
          <thead>
            <tr>
              <th>column</th>
              <th>type</th>
              <th>range</th>
              <th>description</th>
            </tr>
          </thead>
          <tbody>
            {a.columns.map((c: any) => (
              <tr key={c.name}>
                <td>{c.name}</td>
                <td>{c.dtype}</td>
                <td className="num">
                  {c.min !== null && c.max !== null ? `${c.min} – ${c.max}` : "—"}
                </td>
                <td style={{ color: "var(--ink-2)" }}>{c.description || ""}</td>
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
      <p className="empty" style={{ marginBottom: 16 }}>
        {a.plans.length} plans sampled from {a.model} at temperature {a.temperature}. Where these
        disagree is what stage 3 extracts.
      </p>
      {a.plans.map((p: any) => (
        <div className="card" key={p.id}>
          <h3>
            {p.id} <span className="tag">plan</span>
          </h3>
          <p className="why">{p.objective}</p>
          <details>
            <summary style={{ cursor: "pointer", color: "var(--ink-3)", fontSize: 11 }}>
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
      <p className="empty" style={{ marginBottom: 16 }}>
        {Object.keys(decisions).length} decisions. Each is a point where the sampled plans diverged
        or left a choice unstated.
      </p>
      {Object.entries(decisions).map(([id, d]: [string, any]) => {
        const ext = d.x_astaverse ?? {};
        return (
          <div className="card" key={id}>
            <h3>
              {id} <span className="tag">{ext.kind ?? "decision"}</span>
              {ext.post_hoc && <span className="tag"> post-hoc</span>}
            </h3>
            <p className="why">{d.rationale || d.label}</p>
            <ul className="opts">
              {Object.entries(d.options ?? {}).map(([oid, o]: [string, any]) => (
                <li key={oid}>
                  <span className={`opt-id${oid === d.default ? " is-default" : ""}`}>{oid}</span>
                  <span style={{ color: "var(--ink-2)" }}>{o.description || o.label}</span>
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
      <p className="empty" style={{ marginBottom: 16 }}>
        {a.universes.length} universes to execute, from a grid of {a.n_total_grid}.
        {a.n_dropped_constraints > 0 && ` ${a.n_dropped_constraints} ruled out by constraints.`}
      </p>
      {a.n_dropped_cap > 0 && (
        <div className="error">
          {a.n_dropped_cap} universes dropped by the cap of {a.cap}. The reported distribution
          covers only what ran.
        </div>
      )}
      <div className="scroll-x">
        <table>
          <thead>
            <tr>
              <th>universe</th>
              {ids.map((d) => (
                <th key={d}>{d}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {a.universes.map((u: any) => (
              <tr key={u.id}>
                <td>
                  {u.id}
                  {u.is_default && (
                    <span style={{ color: "var(--single)" }}> ← single-universe baseline</span>
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
      <p className="empty" style={{ marginBottom: 16 }}>
        {a.task_name} · {a.n_universes} universes · {a.files.length} files
      </p>
      <pre>{a.files.join("\n")}</pre>
      <p className="empty" style={{ marginTop: 16 }}>
        {a.task_dir}
      </p>
    </>
  );
}

function Execute({ a }: { a: any }) {
  return (
    <>
      {a.dry_run && <p className="empty">Dry run — nothing was executed.</p>}
      {a.jobs.map((j: any) => (
        <div className="card" key={j.job_name}>
          <h3>
            {j.job_name}{" "}
            <span className="tag">{j.returncode === 0 ? "ok" : `exit ${j.returncode ?? "—"}`}</span>
          </h3>
          <p className="why">
            {j.agent}
            {j.model ? ` · ${j.model}` : ""}
          </p>
          <pre>{j.command.join(" ")}</pre>
        </div>
      ))}
    </>
  );
}

function Verdicts({ a }: { a: any }) {
  const counts: Record<string, number> = {};
  a.results.forEach((r: any) => (counts[r.verdict] = (counts[r.verdict] ?? 0) + 1));
  return (
    <>
      {a.missing_universe_ids?.length > 0 && (
        <div className="error">
          Incomplete: {a.missing_universe_ids.length} universes were never reported (
          {a.missing_universe_ids.slice(0, 6).join(", ")}). The distribution below covers only what
          came back.
        </div>
      )}
      <div className="stats">
        {Object.entries(counts).map(([verdict, n]) => (
          <div className="stat" key={verdict}>
            <span className="label">{verdict.replace(/_/g, " ")}</span>
            <span className="value num">{n}</span>
          </div>
        ))}
      </div>
      <p className="empty" style={{ marginBottom: 16 }}>
        Verdict rules applied: {a.verdict_rules.join(", ")}. Assigned here from the reported
        statistics — the agent never saw a verdict field.
      </p>
      <div className="scroll-x">
        <table>
          <thead>
            <tr>
              <th>universe</th>
              <th>rule</th>
              <th>estimate</th>
              <th>p</th>
              <th>n</th>
              <th>verdict</th>
            </tr>
          </thead>
          <tbody>
            {a.results.map((r: any, i: number) => (
              <tr key={`${r.universe_id}-${r.verdict_rule}-${i}`}>
                <td>{r.universe_id}</td>
                <td style={{ color: "var(--ink-3)" }}>{r.verdict_rule}</td>
                <td className="num">{fmt(r.stats.estimate)}</td>
                <td className="num">{fmt(r.stats.p_value, 4)}</td>
                <td className="num">{r.stats.n ?? "—"}</td>
                <td
                  style={{
                    color:
                      r.verdict === "supported"
                        ? "var(--ok)"
                        : r.verdict === "failed"
                          ? "var(--muted-signal)"
                          : "var(--ink-2)",
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
      <div className="stats">
        <div className="stat">
          <span className="label">median</span>
          <span className="value num">{signed(a.median)}</span>
        </div>
        <div className="stat">
          <span className="label">IQR</span>
          <span className="value num">{fmt(a.iqr)}</span>
        </div>
        <div className="stat">
          <span className="label">sign agreement</span>
          <span className="value num">{Math.round(a.sign_consistency * 100)}%</span>
        </div>
        <div className="stat">
          <span className="label">single universe</span>
          <span className="value num" style={{ color: "var(--single)" }}>
            {signed(a.single_universe_surprisal)}
          </span>
        </div>
        <div className={`stat${fragile ? " is-fragile" : ""}`}>
          <span className="label">fragility</span>
          <span className="value num">{fmt(a.fragility_index)}</span>
        </div>
      </div>

      {fragile && (
        <div className="error">
          The single-universe answer sits {fmt(a.fragility_index)} from the multiverse median. A
          pipeline reporting only that number would have reported an artifact of one arbitrary
          analytic choice.
        </div>
      )}

      <div className="legend">
        <span>
          <i style={{ background: "var(--dist)" }} />
          universe
        </span>
        <span>
          <i style={{ background: "var(--single)" }} />
          default / single-universe
        </span>
      </div>

      <SpecCurve universes={a.per_universe} median={a.median} />

      {a.between_agent_spread !== null && a.between_agent_spread !== undefined && (
        <p className="empty" style={{ marginTop: 16 }}>
          Between-agent spread {fmt(a.between_agent_spread)} vs between-universe IQR {fmt(a.iqr)}.
          {a.between_agent_spread < a.iqr
            ? " Decision variance dominates — the multiverse is measuring the analysis, not the agent."
            : " Agent variance rivals decision variance; treat the curve with caution."}
        </p>
      )}

      {a.decision_sensitivity?.length > 0 && (
        <>
          <p className="eyebrow" style={{ margin: "28px 0 10px" }}>
            Which decisions actually moved the result
          </p>
          <div className="scroll-x">
            <table>
              <thead>
                <tr>
                  <th>decision</th>
                  <th>kind</th>
                  <th>spread</th>
                  <th>mean surprisal by option</th>
                </tr>
              </thead>
              <tbody>
                {a.decision_sensitivity.map((d: any) => (
                  <tr key={d.decision_id}>
                    <td>{d.decision_id}</td>
                    <td style={{ color: "var(--ink-3)" }}>{d.kind}</td>
                    <td className="num">{fmt(d.spread)}</td>
                    <td className="num">
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
