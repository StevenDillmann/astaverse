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

## 6. Robust surprisal: the single universe *understates* the finding

Stage 8 on the 96-universe hurricane multiverse (288 results × 3 verdict
rules), belief elicitation on `gpt-5.6-luna`, 5 draws each:

| | |
|---|---|
| prior mean | 0.583 |
| median surprisal | **−0.325** |
| IQR | 0.049 |
| sign agreement | 96% |
| surprising (\|s\| ≥ 0.2) | 88% of universes |
| single-universe (default) | **−0.130** |
| **fragility index** | **0.195** |

The surprisal threshold is 0.2. The default universe returns −0.130, which is
**below** it — a single-universe pipeline reports "not surprising, inconclusive"
and moves on. The multiverse median is −0.325, comfortably past it, with 96%
sign agreement and an IQR of 0.049.

So the multiverse is not merely more cautious than the single universe here —
it is more *confident*, in the opposite direction. The evidence robustly
disconfirms the hypothesis, and the one arbitrary default specification is
the one that fails to see it. Fragility cuts both ways: a single universe can
manufacture a discovery, and it can also bury one.

De-duplication by (analytic decisions, reported statistics, verdict) cut this
from 288 elicitations to 99.

### The estimand determines which decisions matter

`min_pressure_direction` came out with a sensitivity spread of **0.001** —
effectively inert — despite being the fork that flipped AutoDiscovery's
reported result. This is not a contradiction. The reference analysis reports
the **femininity coefficient**, whereas the documented divergence was about the
**severity index's own correlation with deaths**. Orientation wrecks the index
as a standalone predictor while barely perturbing another regressor's
coefficient.

The lesson generalises: sensitivity is a property of a (decision, estimand)
pair, not of a decision alone. A multiverse that reports the wrong estimand
will pronounce a genuinely consequential fork harmless. Any future work on
extraction recall (§3) has to pin the estimand at the same time.

Ranked sensitivity for this estimand: covariates 0.106, model family 0.074,
outcome transform 0.070, outlier handling 0.068, femininity measure 0.007,
verdict rule 0.005, min-pressure direction 0.001.

## 7. First real agent run — and direct evidence for §3

`terminus-2` on `gpt-5.6-luna`, 24 universes, 2m12s, rubric 0.8.

**Both structural bias controls held against a real agent.** The verifier
reported "structural check passed: 24 universes, parametric analyze()
present", and the rubric scored `parametric_structure` and
`no_verdict_smuggling` at 1.0. The agent wrote one parameterised analysis and
did not try to assign verdicts.

Robust surprisal on the agent's own sweep: median +0.041, IQR 0.000,
fragility **0.000**. Against the femininity claim's fragility of 0.195, this
is the control case the diagnostic needed — it stays quiet when nothing is
fragile. 67 of 72 results supported, with a prior already at 0.708: the model
knew storm severity predicts deaths, so confirming it is unsurprising, which
is what a surprisal metric should say.

**The estimand defect.** The rubric scored `comparable_estimand` at 0.0, and
inspection showed why: estimates spanning +0.56 to +45.7, an 82x range,
because a coefficient on log-deaths and one on raw counts were reported side
by side. A specification curve over those would plot unit changes as though
they were analytic disagreement. Fixed by requiring `estimate_standardized`,
preferring it downstream, and failing the run when its spread shows it was not
actually standardized. Worth noting the first threshold chosen (100x) would
have let the real 82x case through; it is now 20x.

**The direct evidence for §3.** The agent's `/app/analysis.py` contains:

```python
# Pressure is reversed because lower pressure indicates greater severity.
'pressure': _z(-pd.to_numeric(df['min'], errors='coerce')),
```

It reversed minimum pressure spontaneously, correctly, and **hardcoded** —
not as a decision. This is the same resolution all three agents reached in the
sibling repo, and the opposite of what AutoDiscovery's own code did. So the
fork is real and live in this very run, an agent resolved it silently, and
because extraction never surfaced it into the decision space, the multiverse
did not test it. The choice that most needs a universe is precisely the one
competent implementers agree on without discussing — which is why it never
appears in plan text, and why extracting against data semantics rather than
plan text is the fix.

## Not yet run

- **Stage 6** (`harbor run`) — the task emits and passes its own structural
  check, but no agent has swept the grid yet.
Stage 8 has since run — see §6 above.
