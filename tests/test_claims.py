"""Grouping runs into claims, and comparing attempts.

The distinction that makes the tool useful: a re-run under a different
configuration is another *attempt* at the same claim, not a different claim.
Getting the grouping wrong either hides comparisons or invents false ones.
"""

from __future__ import annotations

import pytest

from astaverse.core import claims as claims_core
from astaverse.core.claims import claim_id, comparison, normalize_hypothesis
from astaverse.core.schemas import Column, StudySpec
from astaverse.core.store import Run


@pytest.fixture
def runs_dir(tmp_path, monkeypatch):
    d = tmp_path / "runs"
    d.mkdir()
    monkeypatch.setenv("ASTAVERSE_RUNS", str(d))
    return d


def make(runs_dir, tmp_path, hypothesis, dataset="d.csv"):
    csv = tmp_path / dataset
    csv.write_text("a,b\n1,2\n")
    a = Run.create(runs_dir, hypothesis, str(csv))
    a.write_artifact(
        "study",
        StudySpec(
            hypothesis=hypothesis,
            dataset_path=str(csv),
            dataset_name="d",
            n_rows=1,
            columns=[Column(name="a", dtype="number")],
        ),
    )
    a.record_stage("study")
    return a


# -- identity --------------------------------------------------------------


def test_same_hypothesis_and_dataset_is_one_claim():
    assert claim_id("X causes Y", "/data/a.csv") == claim_id("X causes Y", "/data/a.csv")


def test_whitespace_and_case_are_not_scientific_differences():
    assert claim_id("X  causes\nY", "/d.csv") == claim_id("x causes y", "/d.csv")
    assert normalize_hypothesis("  A   B \n") == "a b"


def test_a_trailing_slash_on_the_dataset_is_not_a_different_claim():
    assert claim_id("X", "/data/blade/hurricane/") == claim_id("X", "/data/blade/hurricane")


def test_same_hypothesis_on_different_data_is_a_different_claim():
    assert claim_id("X causes Y", "/a.csv") != claim_id("X causes Y", "/b.csv")


def test_different_hypotheses_on_the_same_data_are_different_claims():
    assert claim_id("X causes Y", "/a.csv") != claim_id("Y causes X", "/a.csv")


# -- grouping --------------------------------------------------------------


def test_reruns_group_as_attempts_at_one_claim(runs_dir, tmp_path):
    make(runs_dir, tmp_path, "Smaller classes raise scores")
    make(runs_dir, tmp_path, "Smaller classes raise scores")
    make(runs_dir, tmp_path, "Something else entirely")

    found = claims_core.all_claims(runs_dir)
    assert len(found) == 2
    by_count = sorted(c.n_attempts if hasattr(c, "n_attempts") else len(c.attempts) for c in found)
    assert by_count == [1, 2]


def test_attempts_are_newest_first(runs_dir, tmp_path):
    first = make(runs_dir, tmp_path, "H")
    second = make(runs_dir, tmp_path, "H")
    claim = claims_core.all_claims(runs_dir)[0]
    assert [a.id for a in claim.attempts] == sorted(
        [first.run_id, second.run_id], reverse=True
    )


# -- comparison ------------------------------------------------------------


def _attempt(aid, decisions, fragility=None):
    return claims_core.Attempt(
        id=aid,
        created_at="2026-01-01",
        status={},
        n_complete=8,
        running=False,
        decisions=decisions,
        fragility=fragility,
    )


def test_shared_and_unique_decisions_are_separated():
    result = comparison(
        [
            _attempt("a", ["verdict_rule", "outliers", "pressure_orientation"]),
            _attempt("b", ["verdict_rule", "outliers", "model_family"]),
        ]
    )
    assert result["shared_decisions"] == ["outliers", "verdict_rule"]
    assert set(result["unique_decisions"]) == {"pressure_orientation", "model_family"}
    assert result["unique_decisions"]["pressure_orientation"] == ["a"]


def test_a_fork_only_one_strategy_finds_is_attributed_to_it():
    """The motivating case: schema_lint sees an orientation fork plan_diff cannot."""
    result = comparison(
        [
            _attempt("plan_diff_run", ["outliers"]),
            _attempt("schema_lint_run", ["outliers", "pressure_orientation"]),
        ]
    )
    assert result["unique_decisions"] == {"pressure_orientation": ["schema_lint_run"]}


def test_attempts_agreeing_about_fragility_are_reported_as_agreeing():
    result = comparison([_attempt("a", ["x"], 0.19), _attempt("b", ["x"], 0.22)])
    assert result["agreement"] == "agree"


def test_attempts_disagreeing_about_fragility_are_flagged():
    """One fragile, one not: the method is in question, not the data."""
    result = comparison([_attempt("a", ["x"], 0.30), _attempt("b", ["x"], 0.01)])
    assert result["agreement"] == "disagree"
    assert result["fragility_range"] == {"min": 0.01, "max": 0.30, "n": 2}


def test_a_single_attempt_makes_no_agreement_claim():
    assert comparison([_attempt("a", ["x"], 0.3)])["agreement"] is None


def test_comparison_survives_attempts_with_no_decisions_yet():
    assert comparison([_attempt("a", [])])["shared_decisions"] == []


def test_back_to_back_attempts_do_not_collide(runs_dir, tmp_path):
    """Run ids are second-resolution, and attempts are created back to back.

    "New attempt" on a claim, or a script sweeping configurations, will make
    several runs of the same hypothesis within one second. That must produce
    distinct runs rather than raising.
    """
    made = [make(runs_dir, tmp_path, "Same hypothesis every time") for _ in range(4)]
    ids = [a.run_id for a in made]
    assert len(set(ids)) == 4, f"colliding run ids: {ids}"
    assert all((runs_dir / i / "manifest.json").exists() for i in ids)

    # All four are attempts at one claim.
    claims = claims_core.all_claims(runs_dir)
    assert len(claims) == 1
    assert len(claims[0].attempts) == 4
