# Multiverse analysis

You are running a **multiverse analysis**: the same hypothesis, evaluated under
every combination of a set of analytic choices, so that the result can be
reported as a distribution rather than as a single number.

## Hypothesis

Among all recorded stops, Black subjects have a higher search rate than White subjects.

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


### `race_variable_definition` — Race comparison definition

Which recorded race field and categories define the Black-versus-White comparison?  [found by: direct]


- **`subject_race_black_white`** (Use subject_race categories): Retain rows with subject_race == "black" or subject_race == "white"; compare those two groups and exclude all other subject_race values.
- **`raw_race_black_white`** (Use raw_Race codes): Retain rows with raw_Race == "B" or raw_Race == "W"; define B as Black and W as White, and exclude all other raw_Race values.
- **`subject_race_with_unknown_as_white`** (Use subject_race with unknowns assigned to White): Use subject_race == "black" as Black and combine subject_race == "white" with subject_race == "unknown" or other non-Black categories as the comparison group.

### `stop_scope` — Stops included in the estimand

Does “all recorded stops” mean every row in the dataset or only stops from a Durham geographic or departmental subset?  [found by: direct]


- **`all_dataset_rows`** (All eligible dataset rows): Use stops from every county_name and department_name represented in nc-durham-stops, subject only to the selected race and outcome missingness rules.
- **`durham_county_only`** (Durham County stops): Retain only rows with county_name == "Durham County".
- **`durham_police_only`** (Durham Police Department stops): Retain only rows with department_name == "Durham Police Department".

### `search_outcome_definition` — Search-rate outcome

Which column or combination of columns counts as a search?  [found by: direct]


- **`search_conducted`** (Any recorded search): Set the binary outcome to 1 when search_conducted == 1 and to 0 when search_conducted == 0.
- **`any_person_or_vehicle_search`** (Person-or-vehicle search): Set the binary outcome to 1 when search_person == 1 or search_vehicle == 1; otherwise set it to 0.
- **`person_search_only`** (Person search): Set the binary outcome to 1 only when search_person == 1; set it to 0 when search_person == 0.
- **`vehicle_search_only`** (Vehicle search): Set the binary outcome to 1 only when search_vehicle == 1; set it to 0 when search_vehicle == 0.

### `missing_search_handling` — Missing outcome handling

How should stops with a missing value for the selected search outcome be handled?  [found by: direct]


- **`complete_case`** (Exclude missing outcome values): Exclude any retained Black or White stop whose selected search outcome is missing; calculate each race-specific rate using only rows with a nonmissing outcome.
- **`missing_as_no_search`** (Code missing as no search): For retained Black or White stops, replace a missing selected search outcome with 0 before calculating rates.
- **`report_missing_as_separate_status`** (Treat missing outcomes as unavailable): Do not impute missing outcomes; calculate rates among nonmissing outcomes and additionally report the number and fraction of missing outcomes by race.

### `confounding_adjustment` — Adjustment for stop composition

Should the Black-versus-White search-rate comparison be an unadjusted comparison across stops or adjust for recorded stop and driver characteristics?  [found by: direct]


- **`unadjusted_rate_comparison`** (Unadjusted stop-level rates): For each race, divide the number of stops with the selected search outcome equal to 1 by the number of eligible stops, with no adjustment for age, sex, reason, date, county, department, or officer.
- **`covariate_adjusted_logistic`** (Covariate-adjusted logistic model): Fit a logistic regression for the selected binary search outcome with Black-versus-White race as the focal predictor and subject_age, subject_sex, reason_for_stop, department_name, county_name, and calendar year extracted from date as covariates; report the race contrast from the model.

### `uncertainty_dependence` — Dependence and uncertainty calculation

How should uncertainty account for repeated stops associated with the same officer_id_hash?  [found by: direct]


- **`iid_two_proportion`** (Independent-stop uncertainty): Use a two-sample proportion comparison or equivalent model-based standard error that treats all eligible stop rows as independent.
- **`officer_cluster_robust`** (Officer-clustered uncertainty): Estimate uncertainty with standard errors or a bootstrap clustered by officer_id_hash, allowing stops handled by the same officer to be correlated.
- **`department_cluster_robust`** (Department-clustered uncertainty): Estimate uncertainty with standard errors or a bootstrap clustered by department_name, allowing dependence among stops reported by the same department.


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
