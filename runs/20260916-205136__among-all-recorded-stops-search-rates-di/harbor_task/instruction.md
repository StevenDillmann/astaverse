# Multiverse analysis

You are running a **multiverse analysis**: the same hypothesis, evaluated under
every combination of a set of analytic choices, so that the result can be
reported as a distribution rather than as a single number.

## Hypothesis

Among all recorded stops, search rates differ across the known race categories.

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


### `analysis_universe` — Analysis universe

Which recorded stops should be included in the comparison?  [found by: direct]


- **`all_recorded_rows`** (All recorded rows): Include every row in the dataset, regardless of date or county_name, provided subject_race and the selected search outcome are usable.
- **`period_all_counties`** (2002–2015 stops in all counties): Keep rows with date from 2002-01-01 through 2015-12-31 inclusive, regardless of county_name.
- **`period_durham_county`** (2002–2015 Durham County stops): Keep rows with date from 2002-01-01 through 2015-12-31 inclusive and county_name equal to Durham County.

### `race_definition` — Race-category definition and unknown handling

Which column and category set should define the known race groups?  [found by: direct]


- **`subject_race_known_only`** (Recorded subject_race, known categories only): Use subject_race and retain only black, white, hispanic, asian/pacific islander, and other; exclude rows coded unknown or missing.
- **`subject_race_with_unknown`** (Recorded subject_race including unknown): Use subject_race with black, white, hispanic, asian/pacific islander, other, and unknown as separate comparison categories; exclude only missing values.
- **`raw_race_ethnicity_recode`** (Reconstructed race from raw fields): Use raw_Race and raw_Ethnicity, applying the source release coding scheme to reconstruct mutually exclusive black, white, hispanic, asian/pacific islander, other, and unknown categories before analysis.

### `search_outcome` — Search outcome definition

Which recorded action should count as a search for the search rate?  [found by: direct]


- **`search_conducted`** (Any recorded search): Define the binary outcome as search_conducted = 1 versus search_conducted = 0; exclude rows with missing search_conducted.
- **`person_search`** (Person search): Define the binary outcome as search_person = 1 versus search_person = 0; exclude rows with missing search_person.
- **`vehicle_search`** (Vehicle search): Define the binary outcome as search_vehicle = 1 versus search_vehicle = 0; exclude rows with missing search_vehicle.
- **`search_or_frisk`** (Search or frisk): Define the binary outcome as 1 when search_conducted = 1 or frisk_performed = 1, and 0 otherwise; exclude rows missing both component indicators.

### `race_adjustment_model` — Adjustment and rate-comparison model

Should race-group search rates be compared without adjustment or conditional on recorded stop characteristics?  [found by: direct]


- **`crude_rate_comparison`** (Unadjusted group-rate comparison): For each race category, report searches divided by stops and compare the categories using a single omnibus comparison of the unadjusted rates; do not include covariates.
- **`unadjusted_logistic`** (Unadjusted logistic regression): Fit a binary logistic regression of the selected search outcome on race category alone, reporting race-group predicted probabilities or odds ratios.
- **`adjusted_logistic`** (Adjusted logistic regression): Fit a binary logistic regression of the selected search outcome on race category, subject_age, subject_sex, reason_for_stop, county_name, department_name, and calendar date; report race-group adjusted predicted probabilities.

### `contrast_structure` — Race contrasts

What race comparison should constitute the primary test?  [found by: direct]


- **`global_omnibus`** (Global omnibus comparison): Test the null that all included race categories have the same search probability, using one joint race comparison; do not make a specific race the reference for the primary claim.
- **`white_reference`** (Each category versus white): Use white as the reference category and report separate contrasts of black, hispanic, asian/pacific islander, and other versus white; omit unknown unless it is included by the race-definition decision.
- **`all_pairwise`** (All pairwise race comparisons): Report a separate comparison for every pair of included race categories, rather than one global comparison or only comparisons with white.

### `dependence_handling` — Dependence and uncertainty calculation

How should repeated stops associated with the same officer or department affect uncertainty estimates?  [found by: direct]


- **`iid`** (Independent-stop standard errors): Treat rows as independent when computing standard errors, confidence intervals, and test statistics.
- **`cluster_officer`** (Cluster by officer): Compute heteroskedasticity-robust standard errors clustered by officer_id_hash, allowing arbitrary dependence among stops handled by the same officer.
- **`cluster_department`** (Cluster by department): Compute heteroskedasticity-robust standard errors clustered by department_name, allowing dependence within reporting departments.
- **`two_way_cluster`** (Two-way officer and department clustering): Compute two-way cluster-robust standard errors using officer_id_hash and department_name as the two clustering dimensions.


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
