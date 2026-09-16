# Matched-pair decision sensitivity

## Definitions

A **multiverse** contains many universes. Each universe is one complete
combination of analytic choices, such as the model, controls, weighting,
outcome, and inference method.

A **decision** is one analytic choice. For example: “How should districts be
weighted?”

A **matched pair** contains two universes that are identical in every decision
except the one being evaluated. This isolates the effect of changing that
decision.

The **effect** is the comparable, hypothesis-aligned estimate produced by each
universe.

## Options and matched comparisons

**Example hypothesis:** Lower student-teacher ratios are associated with higher
average reading and math scores in California school districts.

Each universe estimates the relationship described by this hypothesis under a
different combination of analytic choices.

One decision could be district weighting:

- A: equal weighting
- B: enrollment weighting
- C: square-root enrollment weighting

With three options, the comparisons are A vs B, A vs C, and B vs C.

These comparisons are repeated under every available combination of the other
decisions.

The number of option comparisons per matched context is:
`options × (options − 1) ÷ 2`.

Therefore:

- 2 options produce 1 comparison.
- 3 options produce 3 comparisons.
- 4 options produce 6 comparisons.

Constraints and universe sampling may reduce the number of available matched
pairs.

## Effect sensitivity

For each matched pair:
`effect change = absolute value of (effect from option 1 − effect from option 2)`.

For example:

- A effect: -0.20
- B effect: -0.08
- C effect: 0.10

The changes are:

- A vs B: 0.12
- A vs C: 0.30
- B vs C: 0.18

For each option pair, AstaVerse takes the median change across all matched
contexts. It then pools every option-pair comparison to calculate the
decision’s overall sensitivity:
`overall effect sensitivity = median of all matched effect changes`.

It is also normalized by the curve’s middle-50% range:
`normalized sensitivity = overall effect sensitivity ÷ (75th percentile − 25th percentile)`.

A result of `0.5 IQR` means changing the decision typically moves the effect by
half the width of the curve’s middle 50%.

A 95% interval is estimated by repeatedly resampling the matched changes and
recalculating their median.

## Significance sensitivity

Each universe is classified as:

- Significant positive
- Significant negative
- Not significant

A matched pair counts as a **flip** when changing the decision changes this
classification. Examples include:

- Significant to not significant
- Not significant to significant
- Significant positive to significant negative

The significance sensitivity is:
`flip rate = matched pairs that flip ÷ all classified matched pairs`.

A 40% flip rate means changing that decision changes the statistical conclusion
in 40% of otherwise identical comparisons.

Effect and significance sensitivity should both be reported. Effect sensitivity
measures how much the estimate changes, while significance sensitivity measures
how often the threshold-based conclusion changes.
