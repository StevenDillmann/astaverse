# Multiverse analysis report

Evaluated 256 universes; 50 converged.

The single parameterized `analyze` function applies every selection from the universe YAML. Geography and race filters are applied first. Search rate uses all eligible stops; hit rate restricts to searched stops and uses the selected contraband field. Clock/calendar or veil-of-darkness controls are added when selected. Unadjusted results are proportion differences; adjusted results are logistic fits with clustered sandwich uncertainty for officer-clustered specifications. Estimates are standardized by the sample SD of the focal race indicator.

Standardized estimates range from -0.014545 to 0.029118; median 0.0048569. Positive values indicate a higher outcome for the focal black/non-white comparison than white.
- geographic_scope: maximum within-option spread 0.043664
- race_comparison_set: maximum within-option spread 0.028644
- bias_outcome: maximum within-option spread 0.029875
- hit_definition: maximum within-option spread 0.043664
- time_of_day_adjustment: maximum within-option spread 0.039915
- outcome_model_and_inference: maximum within-option spread 0.043664

Failed fits retain null statistics and converged=false; no verdict is included.
