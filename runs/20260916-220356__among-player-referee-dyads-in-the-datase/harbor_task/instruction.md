# Multiverse analysis

You are running a **multiverse analysis**: the same hypothesis, evaluated under
every combination of a set of analytic choices, so that the result can be
reported as a distribution rather than as a single number.

## Hypothesis

Among player–referee dyads in the dataset, the probability of at least one sending-off (including second-yellow sendings-off) is higher for dark-skinned than for light-skinned players, using a prespecified binary skin-tone threshold and a dyad-level any-event logistic model.

## Dataset

`/app/data.csv` — silberzahn-red-cards, 146028 rows.

The Silberzahn et al. (2018) 'Many Analysts, One Data Set' data: 146,028 player-referee dyads from four European leagues, covering 2,053 players, 3,147 referees and 426,572 games, with 1,834 straight red cards and 1,662 second-yellow sendings-off. Each player's skin tone was scored independently by two raters on a 5-point scale. Twenty-nine independent teams analysed these rows to answer one question and reported odds ratios from 0.89 to 2.93, so the analytic spread here has a published benchmark.

| column | dtype | range | description |
|---|---|---|---|
| `playerShort` | string | e.g. aaron-hughes, aaron-hunt, aaron-lennon | Short player identifier; one player appears in many rows, once per referee. |
| `player` | string | e.g.  Abdón Prats,  Adriano,  Adrián | Player name. |
| `club` | string | e.g. 1. FC Nürnberg, 1. FSV Mainz 05, 1899 Hoffenheim | Club the player played for. |
| `leagueCountry` | category | e.g. England, France, Germany | League the club competed in: England, Germany, France or Spain. |
| `birthday` | string | e.g. 01.01.1981, 01.01.1985, 01.01.1988 | Player date of birth (DD.MM.YYYY). |
| `height` | number | 161 – 203 | Player height in cm. |
| `weight` | number | 54 – 100 | Player weight in kg. |
| `position` | category | e.g. Attacking Midfielder, Center Back, Center Forward | Playing position. |
| `games` | number | 1 – 47 | Games this player played under this referee — the exposure for any rate. |
| `victories` | number | 0 – 29 | Games won under this referee. |
| `ties` | number | 0 – 14 | Games drawn under this referee. |
| `defeats` | number | 0 – 18 | Games lost under this referee. |
| `goals` | number | 0 – 23 | Goals scored under this referee. |
| `yellowCards` | number | 0 – 14 | Yellow cards received from this referee. |
| `yellowReds` | number | 0 – 3 | Second-yellow sendings-off from this referee; whether these count as red cards is an analytic choice. |
| `redCards` | number | 0 – 2 | Straight red cards received from this referee. |
| `photoID` | string | e.g. 100063.jpg, 100350.jpg, 10037.jpg | Photo used for the skin-tone ratings. |
| `rater1` | number | 0 – 1 | First rater's skin-tone score on a 5-point scale: 0 very light, 0.25, 0.5, 0.75, 1 very dark. |
| `rater2` | number | 0 – 1 | Second rater's skin-tone score on the same scale; the two raters agree exactly on 80.2% of dyads, so how to combine them is an analytic choice. |
| `refNum` | number | 1 – 3147 | Anonymous referee identifier. |
| `refCountry` | number | 1 – 161 | Referee country identifier. |
| `Alpha_3` | string | e.g. ABW, AGO, ALB | Referee country ISO code. |
| `meanIAT` | number | -0.0472542 – 0.573793 | Country-level mean implicit racial bias (IAT) score for the referee's country. |
| `nIAT` | number | 2 – 1.9758e+06 | Number of IAT respondents for that country. |
| `seIAT` | number | 2.23537e-07 – 0.286287 | Standard error of the country IAT mean. |
| `meanExp` | number | -1.375 – 1.8 | Country-level mean explicit racial bias score for the referee's country. |
| `nExp` | number | 2 – 2.02955e+06 | Number of explicit-bias respondents for that country. |
| `seExp` | number | 1.04333e-06 – 1.06066 | Standard error of the country explicit-bias mean. |

## The decisions

Each decision below is a point where reasonable analysts disagree. A
**universe** is one choice per decision.


### `sending_off_outcome` — Sending-off outcome definition

Which columns define the dyad-level indicator for at least one sending-off?  [found by: direct]


- **`include_second_yellows`** (Include straight and second-yellow sendings-off): Set outcome = 1 when redCards > 0 or yellowReds > 0; otherwise set outcome = 0.
- **`straight_red_only`** (Straight red cards only): Set outcome = 1 when redCards > 0 and ignore yellowReds, even when yellowReds > 0.

### `skin_tone_combination` — Combining the two skin-tone ratings

How should rater1 and rater2 be combined into the player skin-tone score before dichotomization?  [found by: direct]


- **`mean_raters`** (Mean of both raters): For every row, define skin_score = (rater1 + rater2) / 2.
- **`rater1_only`** (Use rater 1 only): Define skin_score = rater1 for every row and ignore rater2.
- **`rater2_only`** (Use rater 2 only): Define skin_score = rater2 for every row and ignore rater1.
- **`conservative_agreement`** (Use only exact rater agreement): Retain rows only when rater1 = rater2, and define skin_score as that common value.

### `skin_tone_threshold` — Binary skin-tone threshold

Which prespecified rule converts the combined skin-tone score into the dark-skinned exposure?  [found by: direct]


- **`dark_at_least_half`** (Dark at score at least 0.5): Define dark_skin = 1 when skin_score >= 0.5 and dark_skin = 0 otherwise; scores 0.5, 0.75, and 1 are dark.
- **`dark_above_half`** (Dark above 0.5): Define dark_skin = 1 when skin_score > 0.5 and dark_skin = 0 otherwise; only scores above 0.5 are dark.
- **`dark_at_least_three_quarters`** (Dark at score at least 0.75): Define dark_skin = 1 when skin_score >= 0.75 and dark_skin = 0 otherwise.

### `games_exposure_handling` — Handling games as exposure

How should the games column enter the dyad-level any-event logistic analysis?  [found by: direct]


- **`unweighted_dyads`** (One equally weighted observation per dyad): Fit the binary logistic model to the 146,028 dyad rows without weights; games is not used as a weight or offset.
- **`games_frequency_weights`** (Weight dyads by games): Fit the binary logistic model with games as a frequency weight, so a dyad with games = k contributes k times the likelihood contribution of a dyad with games = 1.
- **`games_as_predictor`** (Adjust for games as a covariate): Fit the unweighted binary logistic model and include the numeric games column as a linear predictor; do not use it as a weight.

### `logistic_model_specification` — Covariate and referee-effect specification

Which predictor structure should be used for the dyad-level logistic model estimating the dark_skin odds ratio?  [found by: direct]


- **`crude_logistic`** (Crude logistic model): Fit outcome ~ dark_skin using a standard logistic link, with no additional columns and no referee effects.
- **`adjusted_player_league_logistic`** (Adjust for league and player characteristics): Fit outcome ~ dark_skin + leagueCountry + position + height + weight using a standard logistic link; do not include referee effects.
- **`referee_fixed_effect_logistic`** (Add referee fixed effects): Fit outcome ~ dark_skin + leagueCountry + position + height + weight + factor(refNum) using a standard logistic link; omit any player fixed effect because dark_skin is constant within player.
- **`crossed_random_intercepts`** (Crossed player and referee random intercepts): Fit a logistic mixed model with fixed effect dark_skin and random intercepts (1 | playerShort) and (1 | refNum); include no other fixed covariates.

### `uncertainty_estimation` — Uncertainty estimation for repeated dyads

How should standard errors and intervals for the dark_skin odds ratio account for repeated players and referees?  [found by: direct]


- **`model_based_standard_errors`** (Model-based standard errors): Use the fitted logistic model's default model-based variance and report its Wald standard error and confidence interval.
- **`two_way_cluster_robust`** (Two-way cluster-robust standard errors): Estimate a sandwich variance clustered simultaneously by playerShort and refNum, and use it for the dark_skin odds ratio interval.
- **`cluster_bootstrap`** (Cluster bootstrap): Resample playerShort clusters and refNum clusters using a two-way cluster bootstrap procedure, refit the selected model for each successful replicate, and use the bootstrap distribution for the interval.


The 256 universes to evaluate are in `/app/universes/`, one YAML
file each, listing a selected `option_id` per `decision_id`. The same decision
space is in `/app/astra.yaml`.

## What to build

**`/app/analysis.py`**, structured as exactly one parameterised analysis plus a
driver:

```python
def analyze(df, selections: dict[str, str]) -> dict:
    """Run the analysis for ONE universe.

    `selections` maps decision_id -> option_id. Every analytic choice this
    function makes must be driven by `selections`; nothing may be branched on
    universe id or on the loop index.

    Returns: {
        "estimate", "estimate_standardized",
        "std_error", "std_error_standardized",
        "ci_low_standardized", "ci_high_standardized",
        "p_value", "n", "direction", "converged"
    }
    """
```

plus a driver that loads every file in `/app/universes/`, calls `analyze` for
each, and appends a line to `/app/universes.jsonl`.

**This structure is required, and it is checked.** Every universe must go
through the same code path. Do not special-case an individual universe, and do
not hand-write a separate analysis per universe — if a universe needs different
behaviour, that behaviour must be expressed through `selections`.

## Deliverables

**`/app/universes.jsonl`** — one JSON object per line, one line per universe:

```json
{"universe_id": "universe_000",
 "decisions": {"<decision_id>": "<option_id>", ...},
 "estimate": 0.243, "estimate_standardized": 0.181,
 "std_error": 0.101, "std_error_standardized": 0.075,
 "ci_low_standardized": 0.034, "ci_high_standardized": 0.328,
 "p_value": 0.019,
 "n": 92, "direction": "positive", "converged": true,
 "notes": "optional, brief"}
```

- `estimate` — the effect estimate that bears on the hypothesis, on the
  natural scale of the model you fitted.
- `estimate_standardized` — **the comparable estimand, and the one that
  matters.** Standardize the focal predictor to mean 0 and SD 1 before
  fitting, so that the coefficient is "effect per one standard deviation of
  the predictor". Where the outcome scale also varies across universes (a
  log transform in one, raw counts in another), divide by the standard
  deviation of the outcome actually modelled, so the result is in
  outcome-SD units.

**Why this matters more than it looks.** A coefficient on log(deaths) and a
coefficient on raw deaths are different quantities, and a specification curve
that plots them on one axis is meaningless — the spread it shows would be an
artifact of unit changes rather than an analytic disagreement. If two universes
use different outcome scales or model families, their `estimate` values will
differ by orders of magnitude for reasons that have nothing to do with the
hypothesis. `estimate_standardized` is what makes them comparable, so compute
it deliberately rather than copying `estimate` into it.
- `std_error_standardized` — the standard error on exactly the same scale as
  `estimate_standardized`. If standardization multiplies the natural-scale
  estimate by a factor `s`, multiply its standard error by `abs(s)` too.
- `ci_low_standardized` and `ci_high_standardized` — the lower and upper
  bounds of the 95% confidence interval on the standardized scale. Prefer the
  fitted model's confidence interval transformed by the same standardization.
  If only a standard error is available, use
  `estimate_standardized ± 1.96 * std_error_standardized`.
- `direction` — `"positive"`, `"negative"`, or `"none"`, relative to the
  hypothesis as stated.
- Use `null` for a statistic that genuinely does not exist for a universe, and
  set `"converged": false` if the model failed to fit. Do not drop the line.

**There is deliberately no verdict field.** Report the numbers; whether the
hypothesis is supported is decided downstream from these statistics. Do not add
a verdict, a conclusion flag, or a significance boolean to the JSON.

**`/app/results.md`** — a short report: what `analyze` does, how each decision
is implemented, the spread of results across universes, and which decisions
moved the estimate most. Prose conclusions belong here, not in the JSONL.

## Notes

- Every one of the 256 universes must appear in the JSONL exactly
  once, keyed by the `id` in its YAML file.
- Prefer a clear failure over a fabricated number: if a universe cannot be
  computed, emit the line with nulls and `"converged": false`.
