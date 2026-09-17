# Multiverse analysis

You are running a **multiverse analysis**: the same hypothesis, evaluated under
every combination of a set of analytic choices, so that the result can be
reported as a distribution rather than as a single number.

## Hypothesis

Referees are more likely to award red cards to dark-skinned players than to light-skinned players.

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


### `sendoff_outcome_definition` — Definition of a red-card outcome

Should the outcome be straight red cards only, or all sendings-off including second-yellow cards?  [found by: direct]


- **`straight_red_only`** (Straight red cards only): Define the event count for each player-referee dyad as `redCards`; exclude `yellowReds`.
- **`all_sendings_off`** (Straight red or second-yellow sending-off): Define the event count as `redCards + yellowReds` for each player-referee dyad.

### `skin_tone_measurement_and_encoding` — Measurement and encoding of skin tone

How should `rater1` and `rater2` be combined and represented as the exposure?  [found by: direct]


- **`mean_continuous`** (Mean rater score as a continuous predictor): Compute `skin_tone = (rater1 + rater2) / 2` and enter it as a linear predictor ranging from 0 to 1.
- **`mean_five_level_factor`** (Mean score as a five-level factor): Compute `(rater1 + rater2) / 2` and treat the values 0, 0.25, 0.5, 0.75, and 1 as five indicator-coded categories, using 0 as the reference category.
- **`mean_binary_threshold`** (Binary light/dark classification): Compute `(rater1 + rater2) / 2`; classify scores below 0.5 as light and scores greater than or equal to 0.5 as dark, then estimate the dark-versus-light contrast.
- **`rater1_continuous`** (First rater score as a continuous predictor): Use `rater1` directly as a linear predictor from 0 to 1 and ignore `rater2`.

### `exposure_and_event_model` — Model for event counts and game exposure

How should the `redCards` or combined sending-off count be related to the number of games in `games`?  [found by: direct]


- **`binomial_count_rate`** (Binomial rate model): Use the selected sending-off count as the number of successes and `games` as the number of trials in a binomial regression; report the skin-tone odds ratio.
- **`dyad_any_event_logistic`** (Any-event logistic model): Replace the selected sending-off count by an indicator equal to 1 when the dyad has at least one event and 0 otherwise; fit an unweighted logistic regression with one observation per dyad, without using `games` as a denominator.
- **`poisson_exposure_model`** (Count model with game exposure offset): Model the selected sending-off count with Poisson regression and include `log(games)` as an offset, interpreting the skin-tone coefficient as a rate-ratio contrast rather than an odds ratio.

### `repeated_player_referee_structure` — Dependence from repeated players and referees

How should the repeated observations for the same `playerShort` and `refNum` be represented in the model?  [found by: direct]


- **`no_random_effects`** (No player or referee random effects): Fit the selected event model with no random intercept for `playerShort` or `refNum`; any adjustment variables are included only as fixed effects.
- **`player_referee_random_intercepts`** (Random intercepts for player and referee): Add independent random intercepts for `playerShort` and `refNum` to the selected regression model, while estimating the fixed effect of skin tone.
- **`referee_random_intercept_only`** (Random intercept for referee only): Add a random intercept for `refNum` but not for `playerShort`, leaving player characteristics represented only by observed covariates.

### `fixed_covariate_adjustment` — Adjustment for observed player, league, and referee characteristics

Which variables in addition to skin tone should be included as fixed-effect covariates?  [found by: direct]


- **`unadjusted`** (Skin tone only): Include no covariates beyond the selected skin-tone exposure and the selected outcome model.
- **`league_position_adjusted`** (League and position adjusted): Include categorical `leagueCountry` and categorical `position` as fixed effects in addition to skin tone.
- **`player_characteristics_adjusted`** (Add player characteristics): Include `leagueCountry`, `position`, `height`, `weight`, and birth year extracted from `birthday` as fixed effects in addition to skin tone.
- **`referee_bias_adjusted`** (Add referee-country bias measures): Include `leagueCountry`, `position`, `height`, `weight`, birth year from `birthday`, `meanIAT`, and `meanExp` as fixed effects in addition to skin tone.

### `uncertainty_accounting` — Uncertainty calculation for repeated dyads

How should standard errors or confidence intervals account for dependence among rows involving the same players and referees?  [found by: direct]


- **`model_based_uncertainty`** (Model-based standard errors): Use the standard errors and confidence intervals implied by the selected regression model, with no additional clustering or resampling.
- **`two_way_clustered_uncertainty`** (Two-way clustered uncertainty): Calculate sandwich standard errors clustered simultaneously by `playerShort` and `refNum`, using a multiway-cluster correction for their overlap.
- **`cluster_bootstrap_uncertainty`** (Cluster bootstrap): Resample `playerShort` clusters and `refNum` clusters in a two-way cluster bootstrap, refit the complete model for each replicate, and use the bootstrap distribution for confidence intervals.


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
