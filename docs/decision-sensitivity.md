# Decision sensitivity

How stage 7 (`src/astaverse/core/stages/s7_verdicts.py`, `compute_decision_sensitivity`)
measures which analytic decisions move the result of a multiverse. Everything
here is descriptive: every universe analyses the same dataset, so none of these
numbers is a statistical test of the hypothesis. They answer a different
question — *how much does the answer depend on choices the analyst could have
made differently?* — along two axes that are deliberately kept apart:

- **Effect sensitivity** — how far does the *estimate* move when the choice
  changes? (sections 1 and 2)
- **Inference sensitivity** — does the *conclusion* change? (section 3)

The two can disagree. A decision can move the estimate a great deal without
flipping any conclusion when the whole curve is far from the threshold, and a
decision that barely moves the estimate can flip many conclusions when p-values
sit near it. A single blended score would hide which of these happened, so the
interface shows the two groups side by side.

## Setup

A multiverse has decisions $D_1, \dots, D_m$, each with a set of options. A
universe $u$ is one option per decision, and reports an effect $y_u$ on the
curve scale (the standardized estimate when every universe has one, otherwise
the raw estimate) together with a p-value $p_u$.

Two housekeeping steps come first:

- **One result per universe.** Verdicts are computed under every verdict rule,
  so each universe appears once per rule. Sensitivity keeps one, preferring
  `alpha_05_directional`, then `alpha_05_two_sided`, so the same statistics are
  never counted twice.
- **Curve spread.** The interquartile range of the curve,
  $\mathrm{IQR} = Q_{75}(y) - Q_{25}(y)$, is the unit for normalised measures.
  If it is numerically zero nothing is normalised.

## Effect sensitivity

### 1. Matched pairs

For decision $D$, group universes by *every decision except $D$*. Within a
group, any two universes that differ in $D$ form a **matched pair**: two
analyses identical apart from that one choice. Universes from different agents
are never paired with each other.

For a pair $(u, v)$ the **paired change** is

$$\Delta_{uv} = \lvert y_u - y_v \rvert .$$

#### Effect sensitivity score

$$\text{effect sensitivity}(D) = \operatorname{median}_{\text{pairs}} \Delta_{uv}$$

in outcome units. Reported alongside it, from the same pairs:

- the **90th percentile** and **maximum** of $\Delta_{uv}$, because a decision
  that is decisive in a few cells has a modest median and a long tail;
- the **normalised sensitivity**

  $$\text{normalised}(D) = \frac{\operatorname{median} \Delta_{uv}}{\mathrm{IQR}} ,$$

  so that $1.0$ means "changing this decision alone typically moves the
  estimate by as much as the middle half of the whole curve spans";
- a **95% interval** for the median from 1,000 bootstrap resamples of the
  paired changes (seeded per decision, so it is reproducible), also divided by
  the IQR.

**Example.** Changing the weighting decision produces paired changes of
$0.05, 0.10, 0.15$. Its effect sensitivity is $0.10$. If the curve's IQR is
$0.20$, the normalised sensitivity is $0.5$ IQR.

#### Option pairs

The pooled score mixes every option comparison, so it cannot say whether the
sensitivity comes from $A \to B$ or $A \to C$. Each matched pair is therefore
also filed under its ordered option pair $(A, B)$, with $A$ before $B$ by
option id, and for every option pair:

$$S(A, B) = \operatorname{median} \lvert y_B - y_A \rvert ,
\qquad
\text{shift}(A, B) = \operatorname{median} \left( y_B - y_A \right).$$

The shift is signed: positive means switching from $A$ to $B$ raises the
estimate. A large $S(A,B)$ with a shift near zero means the switch moves the
estimate up in some cells and down in others, which is the signature of an
interaction with another decision. Each option pair also carries its pair
count, its shift divided by the IQR, and its own significance flip rate
(section 3).

### 2. Variance shares

On a *complete* grid — every combination of options present exactly once for
an agent — the effect is a deterministic function of the decisions and its
variance decomposes exactly (Sobol / functional ANOVA). With
$V = \operatorname{Var}(y)$ over all universes:

$$S_1(D) = \frac{\operatorname{Var}\big(\mathbb{E}[y \mid D]\big)}{V}
\qquad\text{(first-order: the decision's own effect)}$$

$$S_T(D) = 1 - \frac{\operatorname{Var}\big(\mathbb{E}[y \mid \text{all decisions except } D]\big)}{V}
\qquad\text{(total: including every interaction it takes part in)}$$

$\mathbb{E}[y \mid D]$ is the mean effect within each option of $D$, and
variances are population variances weighted by cell size. The gap
$S_T - S_1$ is the share of the curve's variance that $D$ contributes only
through interactions. The first-order shares sum to at most one; whatever they
leave unexplained is interaction variance.

These shares are exact only on a full grid, so they are computed per agent and
left empty for any agent whose reported universes do not cover the grid. When
several agents each report a full grid, their shares are averaged.

## Inference sensitivity

### 3. Flips and p-value shifts

Each universe is classed as *significant positive*, *significant negative* or
*indeterminate* from its p-value (threshold $0.05$, or $0.01$ under an
`alpha_01` rule) and the sign of its effect.

- **Verdict flip rate** (headline): a separate pass, `compute_decision_flips`,
  repeats the matched-pair construction on the **verdict** and treats the
  verdict rule itself as a decision. The rate is the share of pairs whose
  verdicts differ, with the most frequent option swaps listed.
- **p-value shift**: $\operatorname{median} \lvert \log_{10} p_u - \log_{10} p_v \rvert$
  over matched pairs, a continuous measure that moves even when nothing crosses
  the threshold.
- **Significance flip rate** (shown as small print under the p-value shift):
  the share of matched pairs whose two members fall in different significance
  classes. It is close to the verdict flip rate, since verdicts are a rule
  applied to the same p-values.

## Ranking

Decisions are ordered by normalised effect sensitivity, then by significance
flip rate. Option pairs are listed by option id under their decision.

## What each number is good for

| Measure | Reads as | Blind to |
|---|---|---|
| Effect sensitivity (median) | Typical cost of the choice, in outcome units | Rare but decisive cells (see 90th pct, max) |
| Normalised sensitivity | Comparable across experiments and scales | Absolute stakes |
| Option-pair shift | Which switch, and in which direction | — |
| Variance shares | How much of the whole spread the decision explains, alone vs. via interactions | Sampled or capped grids |
| Significance / verdict flips | Whether the choice changes the conclusion | Curves where almost everything is indeterminate |

## Worked example: the hurricane specification curve

Simonsohn et al.'s (2020) 1,728-specification grid, effect in extra deaths
for a female- versus male-named hurricane, curve IQR $2.21$:

| Decision | Pairs | Median $\Delta$ | 90th pct | Normalised | $S_1$ | $S_T$ | Sig. flips |
|---|---|---|---|---|---|---|---|
| model | 864 | 1.49 | 4.14 | 0.68 | 0.23 | 0.50 | 4.3% |
| damages_form | 864 | 0.84 | 2.53 | 0.38 | 0.00 | 0.23 | 4.3% |
| outliers | 1,728 | 0.74 | 3.31 | 0.33 | 0.19 | 0.43 | 2.1% |
| year_control | 1,728 | 0.47 | 1.67 | 0.21 | 0.01 | 0.15 | 2.7% |
| leverage_points | 2,592 | 0.47 | 1.88 | 0.21 | 0.06 | 0.21 | 3.7% |
| femininity | 864 | 0.34 | 0.98 | 0.16 | 0.01 | 0.03 | 1.3% |
| intensity_terms | 4,320 | 0.30 | 1.49 | 0.14 | 0.02 | 0.13 | 3.7% |

Reading across the methods: the damages functional form has a first-order
share of zero but a total share of 0.23, and its single option pair has
$S = 0.84$ with a shift of only $+0.12$. The switch moves estimates
substantially, but in both directions depending on the model family — an
interaction the pooled score alone would not reveal. Among the outlier options,
`drop_katrina → keep_all` has a shift of exactly zero: three of the four
leverage-point options already exclude Katrina through the damages threshold,
so for most matched pairs that switch is a no-op.

## Caveats

- Matched pairs need a balanced design. When the universe cap forces sampling,
  stage 4 uses a pair-balanced selection so each decision keeps matched pairs,
  but far fewer of them; the variance shares are then unavailable.
- The measures describe the multiverse *as specified*. A decision with many
  near-duplicate options will look less sensitive per pair than one with two
  sharply different options.
- None of this weights specifications by quality. A poorly fitting model
  counts as much as a good one; if that matters, it is a separate decision or a
  separate weighting, not a property of these scores.
