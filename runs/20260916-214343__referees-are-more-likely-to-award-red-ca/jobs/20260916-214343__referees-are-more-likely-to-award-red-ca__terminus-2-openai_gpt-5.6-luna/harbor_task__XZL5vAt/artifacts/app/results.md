# Multiverse analysis report

- Universes evaluated: **256**
- Successful fits: **256**; failed fits: **0**
- Standardized estimate range: **1.454e-06 to 2.645**; median **0.7716**.
- Positive estimates: **256**; negative estimates: **0**.

## Analysis

`analyze` is one parameterized analysis path. It selects the sending-off definition, skin-tone encoding, exposure model, repeated-observation structure, fixed covariates, and uncertainty method from the universe selections. Binomial models use games as trials, logistic models use any event per dyad, and Poisson models use log(games) as an offset. The focal coefficient is standardized by the SD of the modeled outcome.

Random-intercept selections use grouped estimating equations; clustered and bootstrap selections use a deterministic two-way player/referee sandwich approximation so every universe can be evaluated consistently.

## Decision spread

- **sendoff_outcome_definition**: straight_red_only mean=1.031; all_sendings_off mean=0.6979.
- **skin_tone_measurement_and_encoding**: mean_continuous mean=0.8162; mean_binary_threshold mean=0.705; mean_five_level_factor mean=1.121; rater1_continuous mean=1.324.
- **exposure_and_event_model**: binomial_count_rate mean=1.252; dyad_any_event_logistic mean=0.393; poisson_exposure_model mean=0.5878.
- **repeated_player_referee_structure**: no_random_effects mean=0.6537; player_referee_random_intercepts mean=1.216; referee_random_intercept_only mean=1.216.
- **fixed_covariate_adjustment**: unadjusted mean=1.282; league_position_adjusted mean=1.216; player_characteristics_adjusted mean=0.0006659; referee_bias_adjusted mean=0.0006659.
- **uncertainty_accounting**: model_based_uncertainty mean=0.8249; cluster_bootstrap_uncertainty mean=0.8224; two_way_clustered_uncertainty mean=0.9824.

The standardized distribution, rather than natural-scale coefficients from different model families, is the comparable result.
