# Multiverse analysis

The parameterised `analyze` function selects the sending-off definition, skin-tone rule, analysis unit, Poisson mean structure, and standard-error method from each universe. It uses Poisson exposure offsets, a skin-tone predictor standardized before fitting, sparse fitting for the large dyad data, and outcome-SD scaling for comparable standardized effects. The requested model-based, player-clustered, and two-way player/referee uncertainty options are selected from the universe decisions.

All 112 universe YAML files were processed through the same driver and selection-driven code path; 112 converged and 0 failed.

The standardized estimate ranged from -0.0129207 to 3.13033, with median 0.316036. Positive values indicate a higher exposure-adjusted sending-off rate for dark-skinned players.

## Decision-specific movement

- **poisson_mean_structure**: group-mean spread 1.7667; observed range -0.0129207 to 3.13033. Means: exposure_only=0.0454052; player_and_league_adjusted=1.81211; player_referee_random_effects=0.420666; referee_fixed_effects=0.420666.
- **analysis_unit**: group-mean spread 0.728205; observed range -0.0129207 to 3.13033. Means: player_aggregate=0.0868279; player_referee_dyad=0.815033.
- **sending_off_definition**: group-mean spread 0.321167; observed range -0.0129207 to 3.13033. Means: straight_and_second_yellow=0.55042; straight_reds_only=0.871587.
- **standard_error_method**: group-mean spread 0.242735; observed range -0.0129207 to 3.13033. Means: model_based=0.572298; player_cluster_robust=0.815033; two_way_cluster_robust=0.815033.
- **skin_tone_binary_rule**: group-mean spread 0.106612; observed range -0.0129207 to 3.13033. Means: both_at_least_050=0.700861; either_at_least_050=0.66784; mean_at_least_050=0.700861; mean_at_least_075=0.774452.

The decision with the largest movement in group means is listed first. These are descriptive specification-curve comparisons, not a separate hypothesis test.
