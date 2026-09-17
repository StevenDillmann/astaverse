# Multiverse analysis report

Evaluated **256** universes; **256** converged.

All six decisions are applied inside one parameterized `analyze` function. Unadjusted estimates are Black-minus-White rate differences; adjusted estimates use logistic regression with the specified age, sex, stop reason, department, county, and year covariates.

Standardized estimate range: **0.0780798** to **0.46318**.
Positive estimates: **256 / 256**.

## confounding_adjustment
- `covariate_adjusted_logistic`: mean 0.414199; range 0.388434 to 0.46318; n=128
- `unadjusted_rate_comparison`: mean 0.0845753; range 0.0780798 to 0.0926919; n=128

## missing_search_handling
- `complete_case`: mean 0.250024; range 0.0780798 to 0.46318; n=120
- `missing_as_no_search`: mean 0.249014; range 0.0780798 to 0.46318; n=70
- `report_missing_as_separate_status`: mean 0.248626; range 0.0780798 to 0.46318; n=66

## race_variable_definition
- `raw_race_black_white`: mean 0.247661; range 0.0780798 to 0.46318; n=156
- `subject_race_black_white`: mean 0.257817; range 0.0889211 to 0.433617; n=50
- `subject_race_with_unknown_as_white`: mean 0.246345; range 0.0796381 to 0.419482; n=50

## search_outcome_definition
- `any_person_or_vehicle_search`: mean 0.248994; range 0.080762 to 0.448625; n=90
- `person_search_only`: mean 0.252764; range 0.0780798 to 0.46318; n=46
- `search_conducted`: mean 0.247713; range 0.0809738 to 0.444683; n=90
- `vehicle_search_only`: mean 0.250413; range 0.0798132 to 0.457268; n=30

## stop_scope
- `all_dataset_rows`: mean 0.246788; range 0.0781567 to 0.433617; n=152
- `durham_county_only`: mean 0.236364; range 0.0780798 to 0.400653; n=52
- `durham_police_only`: mean 0.270009; range 0.086957 to 0.46318; n=52

## uncertainty_dependence
- `department_cluster_robust`: mean 0.249718; range 0.0780798 to 0.46318; n=96
- `iid_two_proportion`: mean 0.249189; range 0.0780798 to 0.46318; n=80
- `officer_cluster_robust`: mean 0.249189; range 0.0780798 to 0.46318; n=80

## Standardization
Unadjusted estimates are scaled by the SDs of race and outcome; adjusted coefficients are for a one-SD race-indicator contrast. Cluster choices use cluster-robust sandwich covariance.
