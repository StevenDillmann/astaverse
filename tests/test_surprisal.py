"""Belief maths and the robust-surprisal summary."""

from __future__ import annotations

import math

import pytest

from astaverse.core.schemas import DecisionSpec, Decision, Option, UniverseSurprisal, Verdict
from astaverse.core.stages.s8_surprisal import (
    JEFFREYS,
    _between_agent_spread,
    _decision_sensitivity,
    _iqr,
    beta_from_counts,
    posterior_from_prior,
    theoretical_max_shift,
)


def test_normalizer_matches_autodiscovery_reference_value():
    """Ported formula must agree with asta-autodiscovery's documented value.

    See test_normalized_surprisal.py there: N=30, w=1, Jeffreys prior.
    """
    assert theoretical_max_shift(30, 1.0, JEFFREYS) == pytest.approx(0.7729916774697783)


def test_normalizer_is_bounded_and_increases_with_evidence():
    values = [theoretical_max_shift(n, 1.0, JEFFREYS) for n in (1, 5, 15, 30, 100)]
    assert all(0.0 < v < 1.0 for v in values)
    assert values == sorted(values)


def test_zero_evidence_cannot_shift_belief():
    assert theoretical_max_shift(0, 1.0, JEFFREYS) == 1.0  # guard branch, no division by zero


def test_beta_from_counts_maps_categories_to_scores():
    # 4 definitely_true (1.0) + 0 else -> alpha dominated
    belief = beta_from_counts({"definitely_true": 4})
    assert belief.alpha == pytest.approx(4 * 1.0 + 0.5)
    assert belief.beta == pytest.approx(0.0 + 0.5)
    assert belief.mean > 0.85


def test_uncertain_draws_leave_the_mean_at_one_half():
    belief = beta_from_counts({"uncertain": 6})
    assert belief.mean == pytest.approx(0.5)


def test_cannot_comment_draws_are_excluded_from_n():
    belief = beta_from_counts({"definitely_true": 2, "cannot_comment": 3})
    assert belief.n_samples == 2  # the three abstentions carry no weight


def test_posterior_moves_toward_the_evidence():
    prior = beta_from_counts({"uncertain": 5})
    up = posterior_from_prior(prior, {"definitely_true": 5}, weight=2.0)
    down = posterior_from_prior(prior, {"definitely_false": 5}, weight=2.0)
    assert up.mean > prior.mean > down.mean


def test_evidence_weight_scales_the_update():
    prior = beta_from_counts({"uncertain": 5})
    light = posterior_from_prior(prior, {"definitely_true": 5}, weight=1.0)
    heavy = posterior_from_prior(prior, {"definitely_true": 5}, weight=4.0)
    assert heavy.mean > light.mean


def test_observed_shift_never_exceeds_the_theoretical_max():
    n = 5
    weight = 2.0
    prior = beta_from_counts({"uncertain": n})
    posterior = posterior_from_prior(prior, {"definitely_true": n}, weight=weight)
    shift = posterior.mean - prior.mean
    assert shift <= theoretical_max_shift(n, weight, JEFFREYS) + 1e-9


# --------------------------------------------------------------------------
# summary statistics
# --------------------------------------------------------------------------


def _universe(uid, surprisal, decisions, agent=None, is_default=False):
    return UniverseSurprisal(
        universe_id=uid,
        decisions=decisions,
        verdict=Verdict.supported,
        posterior_mean=0.5 + surprisal / 2,
        surprisal=surprisal,
        is_default=is_default,
        agent=agent,
    )


def test_iqr_of_a_split_distribution():
    assert _iqr([0.0, 0.0, 1.0, 1.0]) == pytest.approx(1.0)
    assert _iqr([0.5]) == 0.0


def test_decision_sensitivity_ranks_the_consequential_decision_first():
    """A decision that flips the sign must outrank one that changes nothing."""
    universes = [
        _universe("u0", 0.4, {"direction": "raw", "weighting": "none"}),
        _universe("u1", 0.4, {"direction": "raw", "weighting": "weighted"}),
        _universe("u2", -0.4, {"direction": "flipped", "weighting": "none"}),
        _universe("u3", -0.4, {"direction": "flipped", "weighting": "weighted"}),
    ]
    spec = DecisionSpec(
        id="s",
        name="s",
        hypothesis="h",
        dataset_path="/d.csv",
        decisions={
            "direction": Decision(
                label="Direction",
                default="raw",
                options={"raw": Option(label="raw"), "flipped": Option(label="flipped")},
            ),
            "weighting": Decision(
                label="Weighting",
                default="none",
                options={"none": Option(label="none"), "weighted": Option(label="weighted")},
            ),
        },
    )
    sensitivity = _decision_sensitivity(universes, spec)
    assert sensitivity[0].decision_id == "direction"
    assert sensitivity[0].spread == pytest.approx(0.8)
    assert sensitivity[1].spread == pytest.approx(0.0)


def test_between_agent_spread_needs_at_least_two_agents():
    single = [_universe("u0", 0.4, {}, agent="gpt-5-mini")]
    assert _between_agent_spread(single) is None

    both = single + [_universe("u0", 0.1, {}, agent="gemini-2.5-pro")]
    assert _between_agent_spread(both) == pytest.approx(0.3)


def test_fragility_is_visible_when_the_default_is_atypical():
    """The motivating case: the single-universe answer sits far from the median."""
    import statistics

    universes = [
        _universe("u0", 0.45, {}, is_default=True),
        _universe("u1", 0.02, {}),
        _universe("u2", -0.01, {}),
        _universe("u3", 0.03, {}),
    ]
    values = [u.surprisal for u in universes]
    median = statistics.median(values)
    default = next(u.surprisal for u in universes if u.is_default)
    assert abs(default - median) > 0.2  # the single universe would have misled
