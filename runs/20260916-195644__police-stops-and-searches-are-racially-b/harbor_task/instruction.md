# Multiverse analysis

You are running a **multiverse analysis**: the same hypothesis, evaluated under
every combination of a set of analytic choices, so that the result can be
reported as a distribution rather than as a single number.

## Hypothesis

Police stops and searches are racially biased.

## Dataset

`/app/data.csv` — nc-durham-stops, 326024 rows.

Every recorded vehicular police stop in Durham, North Carolina, 2002-2015, from the Stanford Open Policing Project: 326,024 stops with driver race, stop date and time, whether a search was conducted, and whether contraband was recovered. Supports outcome/hit-rate tests and time-of-day (veil-of-darkness) designs; it carries no population denominator, so per-capita benchmark tests are not computable from it alone.

| column | dtype | range | description |
|---|---|---|---|
| `raw_row_number` | number | 1.21954e+06 – 2.02802e+07 | Row identifier from the source release. |
| `date` | string | e.g. 2001-12-28, 2002-01-01, 2002-01-02 | Date of the stop (YYYY-MM-DD). |
| `time` | string | e.g. 00:00:01, 00:00:02, 00:00:03 | Time of the stop (HH:MM:SS); needed for any time-of-day or sunset-based analysis. |
| `location` | string | e.g. +Durham, Durham County, , Brunswick County, , Dare County | Free-text stop location. |
| `county_name` | category | e.g. Beaufort County, Brunswick County, Dare County | County of the stop. |
| `subject_age` | number | 10 – 99 | Age of the driver. |
| `subject_race` | category | e.g. asian/pacific islander, black, hispanic | Race of the driver as recorded: black, white, hispanic, asian/pacific islander, other, unknown. |
| `subject_sex` | category | e.g. female, male | Sex of the driver. |
| `officer_id_hash` | string | e.g. 00155aed0d, 002e4938f6, 0044ef63f5 | Anonymised officer identifier; supports officer-level clustering. |
| `department_name` | category | e.g. Durham County Sheriff's Office, Durham Police Department | Reporting department. |
| `type` | category | e.g. vehicular | Stop type; all rows are vehicular. |
| `arrest_made` | category | 0 – 1 | Whether an arrest resulted. |
| `citation_issued` | category | 0 – 1 | Whether a citation was issued. |
| `warning_issued` | category | 0 – 1 | Whether a warning was issued. |
| `outcome` | category | e.g. arrest, citation, warning | Most severe outcome: citation, warning or arrest. |
| `contraband_found` | category | e.g. FALSE, TRUE | Whether contraband was recovered; NA where no search was conducted. |
| `contraband_drugs` | category | e.g. FALSE, TRUE | Whether drugs were recovered. |
| `contraband_weapons` | category | e.g. FALSE, TRUE | Whether weapons were recovered. |
| `frisk_performed` | category | 0 – 1 | Whether a frisk was performed. |
| `search_conducted` | category | 0 – 1 | Whether the stop involved a search. |
| `search_person` | category | 0 – 1 | Whether the person was searched. |
| `search_vehicle` | category | 0 – 1 | Whether the vehicle was searched. |
| `search_basis` | category | e.g. consent, other, probable cause | Recorded legal basis for the search (consent, probable cause, etc.). |
| `reason_for_frisk` | string | e.g. Erratic/Suspicious Behavior, Erratic/Suspicious Behavior|Informant Tip, Erratic/Suspicious Behavior|Informant Tip|Other Official Information | Recorded reason for the frisk. |
| `reason_for_search` | string | e.g. Erratic/Suspicious Behavior, Erratic/Suspicious Behavior|Informant Tip, Erratic/Suspicious Behavior|Informant Tip|Other Official Information | Recorded reason for the search. |
| `reason_for_stop` | category | e.g. Checkpoint, Driving While Impaired, Investigation | Recorded reason for the stop. |
| `raw_Ethnicity` | category | e.g. H, N | Ethnicity exactly as recorded in the source data. |
| `raw_Race` | category | e.g. A, B, I | Race exactly as recorded in the source data. |
| `raw_action_description` | category | e.g. Citation Issued, No Action Taken, On-View Arrest | Action description exactly as recorded in the source data. |

## The decisions

Each decision below is a point where reasonable analysts disagree. A
**universe** is one choice per decision.


### `geographic_scope` — Geographic scope of stops

Which records should represent the population of police stops being tested for racial bias?  [found by: direct]


- **`all_records`** (All records in the dataset): Include every row with a usable subject_race value, regardless of county_name, location, or department_name.
- **`durham_county`** (Durham County stops): Keep only rows where county_name equals "Durham County"; retain stops from all departments in that county.
- **`durham_police_department`** (Durham Police Department stops): Keep only rows where department_name equals "Durham Police Department", regardless of county_name.

### `race_comparison_set` — Race comparison and coding

Which recorded driver-race groups should be compared?  [found by: direct]


- **`black_vs_white`** (Black versus white comparison): Keep only rows with subject_race equal to "black" or "white"; model or report the black-minus-white difference, with white as the reference group.
- **`all_known_races`** (All known race categories): Keep all rows whose subject_race is not "unknown" and estimate separate associations for black, white, hispanic, asian/pacific islander, and other, using white as the reference group.
- **`include_unknown_as_category`** (Include unknown race as a category): Retain all rows, including subject_race equal to "unknown", and treat "unknown" as an additional categorical race level rather than missing data.

### `bias_outcome` — Primary observable outcome

Which observable consequence of a stop should be treated as the test outcome for racial bias?  [found by: direct]


- **`search_rate`** (Search-conducted rate): Use search_conducted as a binary outcome for every included stop; estimate the racial difference in the probability of a search.
- **`contraband_hit_rate`** (Contraband hit rate among searches): Restrict to stops with search_conducted equal to 1 and use contraband_found as the binary outcome; estimate racial differences in the probability that a search recovered contraband.
- **`search_and_hit_rates`** (Both search rate and hit rate): Report a search_conducted outcome for all included stops and a separate contraband_found outcome among searched stops, treating both as primary racial-bias tests.

### `hit_definition` — Definition of a contraband hit

When a hit-rate analysis is conducted, what should count as recovered contraband?  [found by: direct]


- **`any_contraband`** (Any contraband): Among rows with search_conducted equal to 1, code a hit as contraband_found equal to TRUE and a non-hit as contraband_found equal to FALSE; exclude missing contraband_found values.
- **`drugs_only`** (Drugs only): Among rows with search_conducted equal to 1, use contraband_drugs as the binary hit outcome; exclude rows where contraband_drugs is missing.
- **`weapons_only`** (Weapons only): Among rows with search_conducted equal to 1, use contraband_weapons as the binary hit outcome; exclude rows where contraband_weapons is missing.
- **`not_applicable`** (Not applicable): Do not define a hit outcome because the analysis uses only search_conducted.

### `time_of_day_adjustment` — Treatment of stop time

How should date and time be used when comparing racial search or hit outcomes?  [found by: direct]


- **`no_time_adjustment`** (No time adjustment): Use date and time only for parsing or descriptive summaries; estimate racial differences without conditioning on date, hour, or daylight status.
- **`clock_time_controls`** (Clock-time and calendar controls): Include hour-of-day indicators derived from time, plus calendar-year and month indicators derived from date, as adjustment variables in the outcome model.
- **`veil_of_darkness`** (Veil-of-darkness comparison): Construct daylight status from date, time, and a specified sunset calculation for the stop location; compare stops near the daylight-to-dark transition while controlling for date or season, rather than using all hours equally.

### `outcome_model_and_inference` — Outcome model and uncertainty calculation

How should racial differences be estimated and how should repeated stops or officers affect uncertainty?  [found by: direct]


- **`unadjusted_proportions_iid`** (Unadjusted proportions with independent-stop uncertainty): Estimate group-specific outcome proportions and their differences directly, using a two-sample proportion test or equivalent model with observations treated as independent; do not adjust for subject_age, subject_sex, reason_for_stop, officer_id_hash, or department_name.
- **`adjusted_logistic_officer_clustered`** (Covariate-adjusted logistic regression clustered by officer): Fit a logistic regression for the selected binary outcome with race, subject_age, subject_sex, and reason_for_stop as predictors; include calendar or time variables only if selected separately, and use officer_id_hash-clustered standard errors.
- **`department_and_officer_controls`** (Officer and department controls): Fit a logistic regression including race, subject_age, subject_sex, reason_for_stop, department_name indicators, and officer_id_hash fixed effects, with uncertainty clustered by officer_id_hash; observations from officers with no within-officer race variation cannot identify the race coefficient.


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
