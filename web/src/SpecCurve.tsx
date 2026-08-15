/**
 * The specification curve — the instrument this whole pipeline exists to draw.
 *
 * Top: every universe's surprisal, sorted. Bottom: which option each universe
 * used, aligned column-for-column, so a band of marks that tracks the sorted
 * curve identifies the decision doing the work.
 *
 * The default universe is drawn in red. That is the single answer the old
 * pipeline would have reported, and seeing where it falls in the distribution
 * is the point.
 */

interface UniverseSurprisal {
  universe_id: string;
  decisions: Record<string, string>;
  verdict: string;
  surprisal: number;
  is_default: boolean;
}

interface Props {
  universes: UniverseSurprisal[];
  median: number;
  width?: number;
}

const CURVE_H = 190;
const ROW_H = 15;
const LABEL_W = 168;
const PAD = 16;

export function SpecCurve({ universes, median, width = 860 }: Props) {
  if (!universes.length) return null;

  const sorted = [...universes].sort((a, b) => a.surprisal - b.surprisal);

  const decisionIds = Array.from(
    sorted.reduce((set, u) => {
      Object.keys(u.decisions).forEach((d) => set.add(d));
      return set;
    }, new Set<string>()),
  );

  // A header row naming each decision, then one row per option. The header
  // gets its own line so it cannot collide with the option labels.
  type Row =
    | { kind: "header"; decision: string }
    | { kind: "option"; decision: string; option: string };

  const rows: Row[] = [];
  decisionIds.forEach((decision) => {
    const options = Array.from(
      sorted.reduce((set, u) => {
        if (u.decisions[decision]) set.add(u.decisions[decision]);
        return set;
      }, new Set<string>()),
    ).sort();
    rows.push({ kind: "header", decision });
    options.forEach((option) => rows.push({ kind: "option", decision, option }));
  });

  const plotW = width - LABEL_W - PAD * 2;
  const step = plotW / Math.max(sorted.length, 1);
  const x = (i: number) => LABEL_W + PAD + step * (i + 0.5);

  const values = sorted.map((u) => u.surprisal);
  const lo = Math.min(...values, -0.05);
  const hi = Math.max(...values, 0.05);
  const span = hi - lo || 1;
  const y = (v: number) => PAD + CURVE_H - ((v - lo) / span) * CURVE_H;

  const height = PAD * 2 + CURVE_H + 24 + rows.length * ROW_H;

  return (
    <div className="scroll-x">
      <svg
        width={width}
        height={height}
        role="img"
        aria-label={`Specification curve across ${sorted.length} universes`}
        style={{ display: "block" }}
      >
        {/* zero line and median */}
        <line
          x1={LABEL_W + PAD}
          x2={width - PAD}
          y1={y(0)}
          y2={y(0)}
          stroke="var(--rule-strong)"
        />
        <line
          x1={LABEL_W + PAD}
          x2={width - PAD}
          y1={y(median)}
          y2={y(median)}
          stroke="var(--dist)"
          strokeDasharray="3 3"
          opacity={0.5}
        />
        <text x={LABEL_W} y={y(0) + 3} textAnchor="end" fontSize={10} fill="var(--ink-3)">
          0
        </text>
        <text x={LABEL_W} y={y(median) + 3} textAnchor="end" fontSize={10} fill="var(--dist)">
          median
        </text>

        {/* the curve */}
        {sorted.map((u, i) => (
          <g key={u.universe_id}>
            <line
              x1={x(i)}
              x2={x(i)}
              y1={y(0)}
              y2={y(u.surprisal)}
              stroke={u.is_default ? "var(--single)" : "var(--rule-strong)"}
              strokeWidth={u.is_default ? 1.5 : 1}
            />
            <circle
              cx={x(i)}
              cy={y(u.surprisal)}
              r={u.is_default ? 4 : 3}
              fill={u.is_default ? "var(--single)" : "var(--dist)"}
            >
              <title>
                {`${u.universe_id}\nsurprisal ${u.surprisal.toFixed(3)}\n${u.verdict}\n` +
                  Object.entries(u.decisions)
                    .map(([d, o]) => `${d} = ${o}`)
                    .join("\n")}
              </title>
            </circle>
          </g>
        ))}

        {/* decision assignment matrix */}
        {rows.map((row, r) => {
          const rowY = PAD + CURVE_H + 24 + r * ROW_H;
          if (row.kind === "header") {
            return (
              <g key={`h.${row.decision}`}>
                <line
                  x1={PAD}
                  x2={width - PAD}
                  y1={rowY - ROW_H / 2}
                  y2={rowY - ROW_H / 2}
                  stroke="var(--rule)"
                />
                <text
                  x={PAD}
                  y={rowY + 4}
                  fontSize={9}
                  fill="var(--ink-3)"
                  letterSpacing="0.1em"
                >
                  {row.decision.replace(/_/g, " ").toUpperCase()}
                </text>
              </g>
            );
          }
          return (
            <g key={`${row.decision}.${row.option}`}>
              <text x={LABEL_W} y={rowY + 3} textAnchor="end" fontSize={10} fill="var(--ink-2)">
                {row.option}
              </text>
              {sorted.map((u, i) =>
                u.decisions[row.decision] === row.option ? (
                  <circle
                    key={u.universe_id}
                    cx={x(i)}
                    cy={rowY}
                    r={2.5}
                    fill={u.is_default ? "var(--single)" : "var(--ink-2)"}
                  />
                ) : null,
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
}
