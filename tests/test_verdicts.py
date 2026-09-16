"""Verdict assignment.

The load-bearing property: a verdict is a pure function of the reported
statistics. If an LLM ever enters this path, the multiverse stops measuring
analytic decisions and starts measuring the judge.
"""

from __future__ import annotations

import inspect

import pytest

from astaverse.core.schemas import UniverseResult, UniverseStats, Verdict
from astaverse.core.stages import s7_verdicts
from astaverse.core.stages.s7_verdicts import VERDICT_RULES, apply_verdict


def stats(**kwargs) -> UniverseStats:
    base = {
        "universe_id": "universe_000",
        "estimate": 0.24,
        "std_error": 0.1,
        "p_value": 0.019,
        "n": 92,
        "direction": "positive",
        "converged": True,
    }
    base.update(kwargs)
    return UniverseStats(**base)


@pytest.mark.parametrize("rule", sorted(VERDICT_RULES))
def test_every_rule_is_deterministic(rule):
    s = stats()
    assert apply_verdict(s, rule) == apply_verdict(s, rule)


def test_alpha_thresholds_differ_on_the_same_numbers():
    s = stats(p_value=0.019)
    assert apply_verdict(s, "alpha_05_two_sided") is Verdict.supported
    assert apply_verdict(s, "alpha_01_two_sided") is Verdict.not_supported


def test_directional_rule_rejects_a_significant_effect_pointing_the_wrong_way():
    s = stats(p_value=0.001, estimate=-0.4, direction="negative")
    assert apply_verdict(s, "alpha_05_two_sided") is Verdict.supported
    assert apply_verdict(s, "alpha_05_directional") is Verdict.not_supported


def test_non_convergence_is_failed_not_not_supported():
    # A model that did not fit is an absence of evidence, not evidence of absence.
    s = stats(converged=False)
    for rule in VERDICT_RULES:
        assert apply_verdict(s, rule) is Verdict.failed


def test_missing_p_value_is_failed():
    for rule in VERDICT_RULES:
        assert apply_verdict(stats(p_value=None), rule) is Verdict.failed


def test_boundary_p_value_is_not_supported():
    # p == alpha is not significance; the comparison must stay strict.
    assert apply_verdict(stats(p_value=0.05), "alpha_05_two_sided") is Verdict.not_supported
    assert apply_verdict(stats(p_value=0.01), "alpha_01_two_sided") is Verdict.not_supported


def test_unknown_rule_raises_rather_than_defaulting():
    with pytest.raises(KeyError):
        apply_verdict(stats(), "alpha_10_made_up")


def test_no_llm_in_the_verdict_path():
    """Bias control 2, asserted structurally rather than by convention."""
    source = inspect.getsource(s7_verdicts)
    for forbidden in ("litellm", "structured_call", "openai", "completion("):
        assert forbidden not in source, f"{forbidden} must not appear in the verdict path"


def result(
    universe_id: str,
    decisions: dict[str, str],
    estimate: float,
    p_value: float,
) -> UniverseResult:
    universe_stats = stats(
        universe_id=universe_id,
        decisions=decisions,
        estimate=estimate,
        estimate_standardized=estimate,
        std_error_standardized=0.1,
        ci_low_standardized=estimate - 0.196,
        ci_high_standardized=estimate + 0.196,
        p_value=p_value,
        direction="positive" if estimate > 0 else "negative",
    )
    return UniverseResult(
        universe_id=universe_id,
        decisions=decisions,
        stats=universe_stats,
        verdict=apply_verdict(universe_stats, "alpha_05_directional"),
        verdict_rule="alpha_05_directional",
        agent="test-agent",
    )


def test_curve_summary_uses_one_comparable_estimate_per_universe():
    results = [
        result("u0", {"d1": "a", "d2": "x"}, 0.1, 0.2),
        result("u1", {"d1": "b", "d2": "x"}, 0.7, 0.001),
        result("u2", {"d1": "a", "d2": "y"}, 0.3, 0.01),
        result("u3", {"d1": "b", "d2": "y"}, 0.9, 0.001),
    ]
    summary = s7_verdicts.compute_curve_summary(results)
    assert summary is not None
    assert summary.scale == "standardized"
    assert summary.n_estimates == 4
    assert summary.n_with_ci == 4
    assert summary.minimum == pytest.approx(0.1)
    assert summary.median == pytest.approx(0.5)
    assert summary.q25 == pytest.approx(0.25)
    assert summary.q75 == pytest.approx(0.75)
    assert summary.maximum == pytest.approx(0.9)
    assert summary.n_significant_positive == 3
    assert summary.n_significant_negative == 0
    assert summary.n_indeterminate == 1


def test_decision_sensitivity_uses_matched_pairs_and_reports_both_axes():
    results = [
        result("u0", {"d1": "a", "d2": "x"}, 0.1, 0.2),
        result("u1", {"d1": "b", "d2": "x"}, 0.7, 0.001),
        result("u2", {"d1": "a", "d2": "y"}, 0.3, 0.01),
        result("u3", {"d1": "b", "d2": "y"}, 0.9, 0.001),
    ]
    sensitivities = {
        item.decision_id: item for item in s7_verdicts.compute_decision_sensitivity(results)
    }
    assert sensitivities["d1"].n_pairs == 2
    assert sensitivities["d1"].median_abs_effect_change == pytest.approx(0.6)
    assert sensitivities["d1"].normalized_effect_change == pytest.approx(1.2)
    assert sensitivities["d1"].inference_flip_rate == pytest.approx(0.5)
    assert sensitivities["d2"].median_abs_effect_change == pytest.approx(0.2)
    assert sensitivities["d2"].normalized_effect_change == pytest.approx(0.4)


def test_decision_sensitivity_reports_when_no_matched_pairs_exist():
    results = [
        result("u0", {"d1": "a", "d2": "x"}, 0.1, 0.2),
        result("u1", {"d1": "b", "d2": "y"}, 0.9, 0.001),
    ]
    sensitivities = {
        item.decision_id: item for item in s7_verdicts.compute_decision_sensitivity(results)
    }
    assert set(sensitivities) == {"d1", "d2"}
    assert sensitivities["d1"].n_pairs == 0
    assert sensitivities["d1"].normalized_effect_change is None
    assert sensitivities["d1"].inference_flip_rate is None


def test_decision_sensitivity_does_not_normalize_by_numerical_zero_iqr():
    results = [
        result("u0", {"d1": "a"}, 0.1, 0.2),
        result("u1", {"d1": "b"}, 0.7, 0.001),
    ]
    summary = s7_verdicts.CurveSummary(
        scale="standardized",
        n_universes=2,
        n_estimates=2,
        n_with_ci=2,
        minimum=0.0031,
        q25=0.003151525164399588,
        median=0.003151525164399588,
        q75=0.0031515251643995895,
        maximum=0.0032,
        n_significant_positive=1,
        n_significant_negative=0,
        n_indeterminate=1,
    )
    sensitivity = s7_verdicts.compute_decision_sensitivity(results, summary)[0]
    assert sensitivity.median_abs_effect_change == pytest.approx(0.6)
    assert sensitivity.normalized_effect_change is None


def test_decision_sensitivity_reports_variance_shares_and_tails_on_a_full_grid():
    results = [
        result("u0", {"d1": "a", "d2": "x"}, 0.1, 0.2),
        result("u1", {"d1": "b", "d2": "x"}, 0.7, 0.001),
        result("u2", {"d1": "a", "d2": "y"}, 0.3, 0.01),
        result("u3", {"d1": "b", "d2": "y"}, 0.9, 0.001),
    ]
    sensitivities = {
        item.decision_id: item for item in s7_verdicts.compute_decision_sensitivity(results)
    }
    # Additive grid: d1 explains 90% of the variance, d2 the remaining 10%,
    # and with no interaction the total shares equal the first-order ones.
    assert sensitivities["d1"].variance_share_first_order == pytest.approx(0.9)
    assert sensitivities["d1"].variance_share_total == pytest.approx(0.9)
    assert sensitivities["d2"].variance_share_first_order == pytest.approx(0.1)
    assert sensitivities["d2"].variance_share_total == pytest.approx(0.1)
    assert sensitivities["d1"].effect_change_p90 == pytest.approx(0.6)
    assert sensitivities["d1"].effect_change_max == pytest.approx(0.6)
    # Pairs for d1: p 0.2 vs 0.001 (2.30 decades) and 0.01 vs 0.001 (1 decade).
    assert sensitivities["d1"].median_abs_log10p_change == pytest.approx(1.65, abs=0.01)


def test_variance_shares_separate_main_effects_from_interactions():
    # A pure interaction: neither decision moves the mean on its own, yet
    # together they determine the estimate completely.
    results = [
        result("u0", {"d1": "a", "d2": "x"}, 0.0, 0.5),
        result("u1", {"d1": "b", "d2": "x"}, 1.0, 0.5),
        result("u2", {"d1": "a", "d2": "y"}, 1.0, 0.5),
        result("u3", {"d1": "b", "d2": "y"}, 0.0, 0.5),
    ]
    sensitivities = {
        item.decision_id: item for item in s7_verdicts.compute_decision_sensitivity(results)
    }
    assert sensitivities["d1"].variance_share_first_order == pytest.approx(0.0)
    assert sensitivities["d1"].variance_share_total == pytest.approx(1.0)
    assert sensitivities["d1"].median_abs_effect_change == pytest.approx(1.0)


def test_variance_shares_need_a_complete_grid():
    results = [
        result("u0", {"d1": "a", "d2": "x"}, 0.1, 0.2),
        result("u1", {"d1": "b", "d2": "x"}, 0.7, 0.001),
        result("u2", {"d1": "a", "d2": "y"}, 0.3, 0.01),
    ]
    sensitivities = {
        item.decision_id: item for item in s7_verdicts.compute_decision_sensitivity(results)
    }
    assert sensitivities["d1"].variance_share_first_order is None
    assert sensitivities["d1"].variance_share_total is None
    # The matched-pair measures still work on the pairs that do exist.
    assert sensitivities["d1"].n_pairs == 1
    assert sensitivities["d1"].median_abs_effect_change == pytest.approx(0.6)


def test_option_pairs_keep_comparisons_and_their_direction_apart():
    # d1 has three options; the pooled score hides that a->c is the big jump.
    results = [
        result("u0", {"d1": "a", "d2": "x"}, 0.1, 0.2),
        result("u1", {"d1": "b", "d2": "x"}, 0.3, 0.2),
        result("u2", {"d1": "c", "d2": "x"}, 0.9, 0.001),
        result("u3", {"d1": "a", "d2": "y"}, 0.2, 0.2),
        result("u4", {"d1": "b", "d2": "y"}, 0.4, 0.2),
        result("u5", {"d1": "c", "d2": "y"}, 1.2, 0.001),
    ]
    sensitivities = {
        item.decision_id: item for item in s7_verdicts.compute_decision_sensitivity(results)
    }
    pairs = {(pair.option_a, pair.option_b): pair for pair in sensitivities["d1"].option_pairs}
    assert set(pairs) == {("a", "b"), ("a", "c"), ("b", "c")}
    assert pairs[("a", "b")].n_pairs == 2
    assert pairs[("a", "b")].median_shift == pytest.approx(0.2)
    assert pairs[("a", "c")].median_shift == pytest.approx(0.9)  # (0.8 + 1.0) / 2
    assert pairs[("b", "c")].median_shift == pytest.approx(0.7)
    assert pairs[("a", "c")].median_abs_change == pytest.approx(0.9)
    # Only the switches into option c cross the significance threshold.
    assert pairs[("a", "b")].inference_flip_rate == pytest.approx(0.0)
    assert pairs[("a", "c")].inference_flip_rate == pytest.approx(1.0)
    # The pooled decision score is the median over all six matched pairs.
    assert sensitivities["d1"].n_pairs == 6
    assert sensitivities["d1"].median_abs_effect_change == pytest.approx(0.7)


def test_option_pair_shift_is_signed_from_a_to_b():
    results = [
        result("u0", {"d1": "a"}, 0.9, 0.001),
        result("u1", {"d1": "b"}, 0.1, 0.2),
    ]
    sensitivities = {
        item.decision_id: item for item in s7_verdicts.compute_decision_sensitivity(results)
    }
    (pair,) = sensitivities["d1"].option_pairs
    assert (pair.option_a, pair.option_b) == ("a", "b")
    assert pair.median_shift == pytest.approx(-0.8)
    assert pair.median_abs_change == pytest.approx(0.8)
