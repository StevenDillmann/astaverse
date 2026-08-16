"""Verdict assignment.

The load-bearing property: a verdict is a pure function of the reported
statistics. If an LLM ever enters this path, the multiverse stops measuring
analytic decisions and starts measuring the judge.
"""

from __future__ import annotations

import inspect

import pytest

from astaverse.core.schemas import UniverseStats, Verdict
from astaverse.core.stages import s7_verdicts
from astaverse.core.stages.s7_verdicts import VERDICT_RULES, apply_verdict


def stats(**kwargs) -> UniverseStats:
    base = dict(
        universe_id="universe_000",
        estimate=0.24,
        std_error=0.1,
        p_value=0.019,
        n=92,
        direction="positive",
        converged=True,
    )
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
