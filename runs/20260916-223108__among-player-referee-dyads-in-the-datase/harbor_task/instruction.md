# Multiverse analysis

You are running a **multiverse analysis**: the same hypothesis, evaluated under
every combination of a set of analytic choices, so that the result can be
reported as a distribution rather than as a single number.

## Hypothesis

Among player–referee dyads in the dataset, the probability of at least one straight red card is higher for dark-skinned than for light-skinned players, using a prespecified binary skin-tone threshold and a dyad-level any-event logistic model.

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


### `skin_tone_rater_combination` — Skin-tone score construction

How should `rater1` and `rater2` be combined into the player skin-tone score before dichotomization?  [found by: direct]


- **`mean_raters`** (Mean of both raters): For each dyad, define skin_score = (`rater1` + `rater2`) / 2.
- **`rater1_only`** (Use first rater only): Define skin_score = `rater1`, ignoring `rater2`.
- **`both_raters_thresholded`** (Require both raters to classify as dark): Retain the two separate scores for dichotomization; a player is dark only if both `rater1` and `rater2` meet the selected dark-skin threshold, and light otherwise.

### `skin_tone_threshold` — Binary skin-tone threshold

Which prespecified threshold should convert the combined skin-tone score into dark versus light skin?  [found by: direct]


- **`at_least_050`** (Dark if score ≥ 0.50): Set dark_skin = 1 when the score constructed from the selected rater rule is at least 0.50; otherwise set dark_skin = 0.
- **`at_least_075`** (Dark if score ≥ 0.75): Set dark_skin = 1 when the score constructed from the selected rater rule is at least 0.75; otherwise set dark_skin = 0.
- **`above_050`** (Dark if score > 0.50): Set dark_skin = 1 when the score constructed from the selected rater rule is strictly greater than 0.50; otherwise set dark_skin = 0.

### `red_card_outcome_definition` — Any-event outcome definition

Should the dyad outcome count only straight red cards, or also second-yellow sendings-off?  [found by: direct]


- **`straight_red_only`** (At least one straight red card): Set outcome = 1 when `redCards` ≥ 1 and outcome = 0 when `redCards` = 0; ignore `yellowReds`.
- **`any_sending_off`** (At least one sending-off of either type): Set outcome = 1 when `redCards` + `yellowReds` ≥ 1 and outcome = 0 otherwise.

### `games_exposure_handling` — Handling variation in games per dyad

How should the `games` exposure difference across player–referee dyads enter the logistic analysis?  [found by: direct]


- **`unweighted_dyads`** (Unweighted dyad-level logistic regression): Fit the binary logistic model with one equal-weight observation per row, without using `games` as a weight, offset, or predictor.
- **`games_frequency_weight`** (Weight dyads by games): Fit the binary logistic model using `games` as a frequency or analytic weight, so a dyad with 20 games contributes 20 times as much as a dyad with 1 game.
- **`adjust_for_log_games`** (Adjust for log games): Fit the binary logistic model with `log(games)` included as a continuous covariate; do not use `games` as a frequency weight.

### `covariate_adjustment` — Adjustment set for the skin-tone association

Which variables, if any, should be included alongside the binary skin-tone predictor in the dyad-level logistic model?  [found by: direct]


- **`skin_tone_only`** (Unadjusted skin-tone model): Use only the binary skin-tone indicator as a predictor of the selected dyad outcome, with an intercept.
- **`player_and_league_covariates`** (Adjust for player and league characteristics): Include binary skin tone plus `leagueCountry`, `position`, `height`, and `weight` as predictors; do not include referee-country variables.
- **`player_league_referee_country_covariates`** (Also adjust for referee-country characteristics): Include binary skin tone, `leagueCountry`, `position`, `height`, `weight`, `refCountry`, `meanIAT`, and `meanExp` as predictors. Treat `refCountry` as categorical and the two bias measures as continuous.

### `dependence_inference` — Inference for repeated players and referees

How should uncertainty account for the fact that rows repeatedly involve the same `playerShort` and `refNum`?  [found by: direct]


- **`model_based_iid`** (Model-based iid standard errors): Use the ordinary logistic-regression covariance matrix, treating the 146028 rows as independent for standard-error and confidence-interval calculation.
- **`player_clustered`** (Cluster by player): Use a sandwich covariance estimator clustered on `playerShort`, allowing arbitrary dependence among dyads involving the same player.
- **`two_way_clustered`** (Two-way cluster by player and referee): Use a multiway sandwich covariance estimator with clustering on both `playerShort` and `refNum`, allowing dependence within either repeated-player or repeated-referee groups.
- **`random_intercepts`** (Random intercepts for player and referee): Fit a mixed-effects logistic model with random intercepts for `playerShort` and `refNum`, and report the fixed-effect odds ratio for binary skin tone using model-based mixed-model uncertainty.


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
