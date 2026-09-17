# Multiverse analysis report

- Universes evaluated: **256**; successful fits: **256**; failed fits: **0**.
- Standardized estimate range: **-0.0010** to **0.5847** (median **0.0456**).
- Sample-size range: **18633** to **21706**.
- Positive estimates: **241**; negative estimates: **15**.

## What `analyze` does

`analyze(df, selections)` applies every universe selection through one shared code path. It first selects the race population, searched-stop definition, contraband-hit coding, and date scope. It then computes either an unadjusted Black-minus-comparison hit-rate difference, a race-only logistic model, or an adjusted logistic model with subject age, sex, stop reason, department, and calendar year. Uncertainty is treated as independent, officer-clustered, or department-clustered according to the selected dependence option. The focal binary race predictor and binary outcome are standardized so estimates are comparable across model specifications; confidence intervals and two-sided p-values are reported on that standardized scale. Failed or unidentified fits are represented with null statistics and `converged: false`.

## Decision sensitivity

### race_analytic_sample

- `include_unknown_as_nonwhite`: mean **0.2720**, range **0.0487** to **0.5847**, n=52.
- `use_raw_race_mapping`: mean **0.2551**, range **0.0452** to **0.5634**, n=51.
- `black_white_only`: mean **0.0341**, range **-0.0010** to **0.1739**, n=153.

### searched_stop_definition

- `search_conducted`: mean **0.1276**, range **0.0013** to **0.5847**, n=135.
- `any_search_related_action`: mean **0.1460**, range **0.0013** to **0.5847**, n=75.
- `person_or_vehicle_search`: mean **0.0912**, range **-0.0010** to **0.2833**, n=46.

### contraband_hit_coding

- `drug_or_weapon_union`: mean **0.2313**, range **0.0247** to **0.5847**, n=70.
- `direct_contraband_missing_nonhit`: mean **0.0875**, range **-0.0010** to **0.2934**, n=91.
- `direct_contraband_complete_case`: mean **0.0865**, range **-0.0010** to **0.2934**, n=95.

### date_scope

- `stated_2002_2015_window`: mean **0.1389**, range **-0.0010** to **0.5847**, n=66.
- `complete_date_only`: mean **0.1346**, range **-0.0010** to **0.5847**, n=70.
- `all_supplied_rows`: mean **0.1148**, range **-0.0010** to **0.5847**, n=120.

### race_comparison_model

- `race_only_logistic`: mean **0.1701**, range **0.0046** to **0.5847**, n=70.
- `adjusted_logistic`: mean **0.1603**, range **-0.0010** to **0.5303**, n=116.
- `unadjusted_rate_comparison`: mean **0.0267**, range **0.0009** to **0.0751**, n=70.

### dependence_and_uncertainty

- `cluster_department`: mean **0.1876**, range **-0.0010** to **0.5847**, n=154.
- `independent_stops`: mean **0.0341**, range **-0.0010** to **0.1739**, n=51.
- `cluster_officer`: mean **0.0341**, range **-0.0010** to **0.1739**, n=51.

Across option-group means, the largest estimate movements were: **race_analytic_sample (0.2379), dependence_and_uncertainty (0.1535), contraband_hit_coding (0.1448), race_comparison_model (0.1434), searched_stop_definition (0.0547), date_scope (0.0241)**. Outcome and searched-stop definitions alter the denominator and hit coding; model choice changes the estimand and adjustment set; clustering mainly changes standard errors and p-values rather than point estimates.
