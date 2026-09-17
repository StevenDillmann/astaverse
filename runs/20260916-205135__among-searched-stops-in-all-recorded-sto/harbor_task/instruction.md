# Multiverse analysis

You are running a **multiverse analysis**: the same hypothesis, evaluated under
every combination of a set of analytic choices, so that the result can be
reported as a distribution rather than as a single number.

## Hypothesis

Among searched stops in all recorded stops, Black subjects have a higher rate of any contraband hit than White subjects.

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


### `race_analytic_sample` — Race groups included

Which recorded driver races should define the Black-versus-White comparison?  [found by: direct]


- **`black_white_only`** (Black and White subjects only): Retain rows where `subject_race` is exactly `black` or `white`; exclude `hispanic`, `asian/pacific islander`, `other`, `unknown`, and missing values.
- **`use_raw_race_mapping`** (Use raw race fields to classify Black and White): Classify subjects using `raw_Race` (and, if needed, `raw_Ethnicity`) according to the source codes; retain only source-coded Black and White subjects, excluding other or ambiguous codes.
- **`include_unknown_as_nonwhite`** (Black versus all non-Black subjects): Retain Black subjects as the exposed group and combine White, Hispanic, Asian/Pacific Islander, Other, Unknown, and missing `subject_race` values into the comparison group.

### `searched_stop_definition` — Definition of a searched stop

Which rows count as searched stops for the denominator?  [found by: direct]


- **`search_conducted`** (Recorded conducted search): Retain rows with `search_conducted == 1`; exclude all rows with `search_conducted == 0` or missing.
- **`person_or_vehicle_search`** (Person or vehicle search indicator): Retain rows with `search_person == 1` or `search_vehicle == 1`; exclude rows where both indicators are 0 or missing.
- **`any_search_related_action`** (Any search-related action): Retain rows with `search_conducted == 1`, `search_person == 1`, `search_vehicle == 1`, or `frisk_performed == 1`; treat a row as searched if any of these indicators equals 1.

### `contraband_hit_coding` — Any-contraband outcome coding

How should `contraband_found`, `contraband_drugs`, and `contraband_weapons` define a hit among selected searched stops?  [found by: direct]


- **`direct_contraband_complete_case`** (Direct contraband field, complete cases): Define a hit as `contraband_found == TRUE` and a non-hit as `contraband_found == FALSE`; exclude selected searched rows where `contraband_found` is missing.
- **`direct_contraband_missing_nonhit`** (Direct contraband field, missing as no hit): Define a hit as `contraband_found == TRUE`; define every other selected searched row, including missing `contraband_found`, as a non-hit.
- **`drug_or_weapon_union`** (Union of drugs and weapons fields): Define a hit if `contraband_drugs == TRUE` or `contraband_weapons == TRUE`; define a non-hit if both are FALSE; exclude rows where both component fields are missing.

### `date_scope` — Calendar scope of recorded stops

Which dates in the supplied rows should enter the analysis?  [found by: direct]


- **`all_supplied_rows`** (All supplied rows): Use every row passing the race, searched-stop, and outcome rules, regardless of the value of `date`; do not impose an additional date filter.
- **`stated_2002_2015_window`** (Stops dated 2002 through 2015): Retain only rows whose parsed `date` is between `2002-01-01` and `2015-12-31`, inclusive; exclude missing, invalid, and out-of-window dates.
- **`complete_date_only`** (All rows with valid dates): Retain all rows with a successfully parsed `date`, including dates outside 2002–2015; exclude only missing or invalid dates.

### `race_comparison_model` — Statistical comparison of hit rates

Should the Black-versus-White comparison use raw rates or adjust for observed stop and driver characteristics?  [found by: direct]


- **`unadjusted_rate_comparison`** (Unadjusted two-group rate comparison): For each race, calculate hits divided by selected searched stops and compare the two proportions without adjustment for `subject_age`, `subject_sex`, `reason_for_stop`, `department_name`, officer, date, or time.
- **`race_only_logistic`** (Race-only logistic model): Fit `hit ~ Black`, where `hit` is the coded any-contraband outcome and Black indicates `subject_race == black` versus `white`; report the race coefficient as the comparison.
- **`adjusted_logistic`** (Observed-characteristics adjusted logistic model): Fit `hit ~ Black + subject_age + subject_sex + reason_for_stop + department_name + calendar_year`, using complete cases for these predictors; report the adjusted Black coefficient, with `calendar_year` derived from `date`.

### `dependence_and_uncertainty` — Dependence structure for uncertainty

How should repeated stops associated with the same officer or department affect standard errors and the hypothesis test?  [found by: direct]


- **`independent_stops`** (Treat stops as independent): Compute uncertainty as if each searched stop were independent, with no clustering adjustment for `officer_id_hash` or `department_name`.
- **`cluster_officer`** (Cluster by officer): Use cluster-robust uncertainty with `officer_id_hash` as the clustering unit, allowing arbitrary dependence among stops handled by the same officer.
- **`cluster_department`** (Cluster by department): Use cluster-robust uncertainty with `department_name` as the clustering unit, allowing arbitrary dependence among stops reported by the same department.


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
