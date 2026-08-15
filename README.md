# Astaverse

Multiverse analysis and **robust surprisal** for agentic scientific discovery.

## The problem

Today's AutoDiscovery pipeline runs a single universe:

```
Hypothesis + Dataset → Experiment Plan → Execution → Verification Code
                     → Evidence → Output/Verdict → Reward → Surprisal
```

Every arrow hides analytic choices nobody wrote down, and the surprisal at the
end rides on all of them. This is not hypothetical. On the BLADE `hurricane`
dataset, one undocumented choice — whether minimum pressure is sign-flipped —
moves the headline result from `r=0.039, p=0.711` to `r=0.240, p=0.020`. Three
different agents made one choice; AutoDiscovery's own reference code made the
other. Same plan, same data, opposite conclusions, and nothing in the pipeline
notices.

That dataset is from Simonsohn et al.'s *specification curve analysis* paper,
which exists precisely because a single specification is not a result.

## What Astaverse does

```
Hypothesis + Dataset → K sampled Plans → Decision Extraction → Decision Space
                     → Decision Spec → Multiverse Instantiation → Execution
                     → Multiple Outputs/Verdicts → Evidence → Robust Surprisal
```

Sample K plans independently; where they disagree are the analytic decisions.
Turn those into a decision space, execute every combination, and report
surprisal as a **distribution** with a `fragility_index`: how far the
single-universe answer sits from the multiverse median.

## Pipeline

Eight stages. Each is a pure function `(run, config) → artifact`, so any stage
re-runs alone from disk, and the CLI and the web viewer call identical code.

| # | Stage | In → Out |
|---|---|---|
| 1 | `study` | hypothesis + dataset → `01_study.json` (profiled columns) |
| 2 | `plans` | study → `02_plans.json` (K sampled plans) |
| 3 | `decisions` | plans → `03_astra.yaml` (the decision space) |
| 4 | `universes` | spec → `04_universes.json` + `universes/*.yaml` |
| 5 | `task` | spec + universes → `harbor_task/` |
| 6 | `execute` | task → Harbor job artifacts |
| 7 | `verdicts` | statistics → `07_verdicts.json` |
| 8 | `surprisal` | verdicts → `08_surprisal.json` |

```bash
astaverse new --hypothesis "…" --dataset path/to/blade/hurricane
astaverse pipeline <run_id> --through universes   # offline, no Harbor needed
astaverse task <run_id> && astaverse execute <run_id> -m openai/gpt-5-mini
astaverse verdicts <run_id> && astaverse surprisal <run_id>
astaverse serve                                   # the pipeline viewer
```

## Bias controls

If a coding agent produces the universes, does the agent's bias contaminate the
measurement? The two obvious designs fail in opposite directions — N
independent agents confound decision effects with implementation variance,
while one agent sweeping the grid can special-case cells, anchor on earlier
results, and impose its own verdicts. Astaverse takes the second and closes
each channel:

1. **Parametric sweep, enforced.** The task requires a single
   `analyze(df, selections)` that every universe passes through. The verifier
   parses `analysis.py` and fails the run if it branches on a universe id.
2. **The agent never assigns verdicts.** `universes.jsonl` carries statistics
   only; the verifier rejects a `verdict` field. Verdicts are applied in
   `s7_verdicts.py` by pure functions with no LLM in the path — the verdict
   rule is itself a decision axis (`alpha_05_two_sided`, `alpha_01_two_sided`,
   `alpha_05_directional`), applied post-hoc at zero execution cost.
3. **Measure the residual.** Pass `-m` more than once. The spread between
   models is the implementation-bias estimate, reported as
   `between_agent_spread` beside the between-universe `iqr`.
4. **Cross-model extraction.** Plans and decisions default to *different*
   models (`ASTAVERSE_PLAN_MODEL` vs `ASTAVERSE_DECISION_MODEL`), since one
   model doing both misses forks it never entertains.

## Relationship to ASTRA

[ASTRA](https://astra-spec.org) (Agentic Schema for Transparent Research
Analysis) already models decisions, options, and universes as first-class
entities, and maps almost one-to-one onto this pipeline.

**Astaverse emits ASTRA-*shaped* YAML but does not yet depend on
`astra-tools`.** The novel stage here is decision extraction, and putting a
pre-1.0 external validator on its critical path would force the output to
satisfy a schema before we know what the output should be. So the pydantic
models deliberately mirror ASTRA's field names (`decisions`/`options`/`default`/
`requires`/`incompatible_with`, `DecisionSelection{decision_id, option_id}`),
constraint pruning is reimplemented in `astra_io.py`, and astaverse extensions
are quarantined under `x_astaverse` keys. Adopting the real tooling later
should be `astra validate` plus fixes, not a redesign.

When adopting: `astra-tools` (the CLI, PyPI 0.2.x) and `astra-spec` (the
schema, tags 0.0.x) are separate repos on separate version lines.

ASTRA schema is CC BY 4.0, its code BSD-3-Clause; cite via the spec repo's
`CITATION.cff`.

## Setup

```bash
uv venv && uv pip install -e '.[dev]'
cp .env.example .env    # OpenAI + Gemini keys
```

Harbor is needed only for stages 6+; stages 1–5 run offline.

## Layout

```
src/astaverse/
  schemas.py     wire format between stages (ASTRA-shaped decision models)
  astra_io.py    astra.yaml emit/load, constraint pruning, grid enumeration
  store.py       run directories, artifacts, downstream invalidation
  llm.py         LiteLLM wrapper (OpenAI + Gemini)
  stages/        s1_study … s8_surprisal
  cli.py         typer CLI
  server.py      FastAPI viewer backend
templates/harbor_task/   jinja2 task template
web/                     Vite + React SPA
```
