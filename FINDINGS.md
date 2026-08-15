# Findings — first working prototype

2026-08-15. Everything below is from real runs in this repo; the run
directories are gitignored but reproducible with the commands shown.

## 1. The pipeline is generic, and verified on two unrelated studies

`astaverse new --hypothesis … --dataset …` then `pipeline --through universes`
runs the automatic path with real LLM calls. Confirmed on:

- **hurricane** (BLADE, 94 rows) — feminine hurricane names and deaths.
  Extracted: severity covariates, model selection strategy, influential-case
  strategy, temporal/source controls, standard-error type.
- **caschools** (BLADE, 420 rows) — class size and test scores.
  Extracted: outcome variable, county clustering, district-size control,
  nonlinearity handling, influential points.

Nothing in `src/astaverse/` is study-specific. The decision spaces above were
produced with no hand-written input, and they are recognisably specific to
their datasets.

## 2. A real multiverse: the hurricane claim survives 4% of specifications

Using the hand-authored `examples/hurricane/astra.yaml` (6 axes) and
`scripts/hurricane_reference.py`, with **no LLM anywhere in the path**:

| | |
|---|---|
| grid | 128 combinations |
| valid after constraints | 96 (32 dropped: `log1p` × `negative_binomial`) |
| significant at p<0.05 | **4 / 96 (4%)** |
| verdicts (× 3 rules) | 9 supported / 279 not supported |
| default universe | estimate +1.177, p=0.322 |

All four significant universes need the same narrow conjunction: negative
binomial **and** severity-index-only covariates **and** raw counts **and**
outliers kept. Drop any one and significance disappears. A single-universe
pipeline landing in that corner would report a discovery; landing anywhere
else it reports nothing. That is the fragility this project exists to expose.

Constraint pruning was exercised for real here: 128 → 96 is exactly the
count-model-on-log-transformed-outcome combinations, removed by one
`incompatible_with` declaration.

## 3. Decision extraction has a blind spot: under-specification by silence

**This is the important negative result.** The pre-registered check was whether
extraction recovers the documented min-pressure-direction fork from the
sibling repo's `findings/hurricane__node_0.md`. It does not, across three
prompt formulations.

The reason is not a weak prompt. AutoDiscovery's plan text says only:

> "z-score normalize each of the three variables, then average"

It never mentions orientation. Minimum pressure runs *inverse* to severity
(lower = stronger), so averaging raw z-scores yields a near-meaningless
composite — the reference implementation got r=0.039 this way, while every
agent that inverted it got r=0.240. **The fork is not a disagreement in the
plan text; it is an omission from it.** It materialises only in code.

Extraction-by-diff cannot see this. Two implementers reading the same silent
sentence write different programs, and no amount of comparing plan texts
surfaces a step none of them describes.

Sharper still: when seeded with AutoDiscovery's plan and asked explicitly to
audit it for implementation gaps, the extractor reliably proposes
`composite_index_weighting` (weighted vs unweighted average) — which the
experiments repo measured as **inconsequential** — while missing orientation,
which flipped a sub-verdict. It finds the salient latitude and misses the
silent one. That is exactly the distinction finding #6 there draws: *"Not all
latitude matters. Remove ambiguity that changes the conclusion, not all
ambiguity."*

### What this implies

Plan text is the wrong sole input for decision extraction. Candidate fixes,
in rough order of expected value:

1. **Extract against data semantics, not just plan text.** The column
   description for `min` states it is minimum pressure. An extractor given
   the schema and asked "which variables in this composite run opposite to
   the others?" can derive the orientation fork deterministically. This is a
   targeted lint, not a general reasoning problem.
2. **Two-pass extraction**: diff the plans, then separately audit each step of
   the plan under evaluation for what code it under-determines.
3. **Extract from code, not plans.** Divergence appeared between
   implementations. Sampling K *implementations* of one plan and diffing those
   would have caught it — at much higher cost.

Option 1 is cheap and testable, and the hurricane case is a ready-made
regression test with a known answer.

## 4. Seeding matters, and changes what gets found

Sampling plans from scratch produced plans that never build a composite
severity index at all — so the index-related decision space did not exist for
them. Seeding with AutoDiscovery's plan (`--seed-jsonl … --seed-id …`) shifted
every sampled plan onto composite-index territory, and notably all four
sampled alternatives explicitly reversed minimum pressure while the seed did
not. **The decision space is relative to the plan population you sample.**
For evaluating AutoDiscovery, the seeded mode is the correct one.

## 5. Methodological notes worth keeping

- **Negating a plain regressor is inert.** An early version of the reference
  analysis made `min_pressure_direction` flip an OLS control, which cannot
  change any other coefficient. An axis that is mathematically incapable of
  mattering will read as "not consequential" and look like a finding. The
  orientation fork only bites inside the composite index.
- **The verdict rule earns its place.** Across 96 universes, moving between
  p<0.05 and p<0.01 changes the count of supported results at zero execution
  cost, because it is applied post-hoc to stored statistics.

## Not yet run

- **Stage 6** (`harbor run`) — the task emits and passes its own structural
  check, but no agent has swept the grid yet.
- **Stage 8** (robust surprisal) on real data — needs belief elicitation per
  universe. At 96 universes × 3 verdict rules × 5 draws this is ~1,440 LLM
  calls, so it wants either a cost decision or the de-duplication described
  below (belief only depends on the reported statistics, and many universes
  share a verdict and a similar estimate, so distinct-signature caching should
  cut it by roughly an order of magnitude).
