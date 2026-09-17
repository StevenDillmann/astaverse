# Multiverse analysis report

The selections-driven analysis constructs the selected skin-tone indicator and any-event outcome, then fits a dyad-level binomial logistic model for every universe. The focal binary predictor is standardized by its sample SD, and estimates, standard errors, and intervals are reported on that comparable scale.

- Universes processed: 256
- Successful fits: 93
- Failed fits: 163
- Standardized estimate range: -0.0258 to 0.0645
- Median standardized estimate: 0.0286
- Positive estimates: 88; negative estimates: 5

## Decision implementation
- Skin tone uses the selected rater combination and threshold.
- The outcome is straight red cards or either sending-off type.
- Games are ignored, used as frequency weights, or adjusted with log(games).
- Covariate sets add league, position, height, weight, and optionally referee-country and bias variables.
- Inference uses the selected iid, player-clustered, two-way clustered, or crossed-group robust path.

## Interpretation
The JSONL contains one record per universe and no verdict; the standardized fields are the comparable specification-curve estimands.

## Decision-level movement
Among successful fits, the following ranges show how much the standardized estimate varied within each option; larger ranges indicate decisions associated with more movement in the specification curve.
- **skin_tone_threshold** (largest within-option range 0.0903): `above_050`: -0.0145 to 0.0622 (n=30); `at_least_050`: -0.0258 to 0.0645 (n=38); `at_least_075`: 0.0076 to 0.0622 (n=25)
- **dependence_inference** (largest within-option range 0.0903): `model_based_iid`: -0.0258 to 0.0645 (n=72); `player_clustered`: 0.0055 to 0.0624 (n=7); `random_intercepts`: 0.0055 to 0.0624 (n=7); `two_way_clustered`: 0.0055 to 0.0624 (n=7)
- **covariate_adjustment** (largest within-option range 0.0903): `player_and_league_covariates`: 0.0034 to 0.0624 (n=27); `skin_tone_only`: -0.0258 to 0.0645 (n=66)
- **skin_tone_rater_combination** (largest within-option range 0.0880): `both_raters_thresholded`: -0.0258 to 0.0622 (n=32); `mean_raters`: -0.0258 to 0.0622 (n=37); `rater1_only`: -0.0136 to 0.0645 (n=24)
- **red_card_outcome_definition** (largest within-option range 0.0697): `any_sending_off`: -0.0258 to 0.0439 (n=42); `straight_red_only`: -0.0026 to 0.0645 (n=51)
- **games_exposure_handling** (largest within-option range 0.0545): `adjust_for_log_games`: 0.0284 to 0.0645 (n=28); `games_frequency_weight`: -0.0258 to 0.0287 (n=27); `unweighted_dyads`: 0.0034 to 0.0502 (n=38)
