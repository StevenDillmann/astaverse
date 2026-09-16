"""Archiving hides items from listings without deleting or orphaning them."""

from __future__ import annotations

import pytest

from astaverse.core import claims as claims_core
from astaverse.core import settings as app_settings


def test_set_archived_round_trip(tmp_path):
    app_settings.set_archived(tmp_path, "experiment", "run-a", True)
    app_settings.set_archived(tmp_path, "experiment", "run-b", True)
    assert app_settings.load(tmp_path).archived_experiments == ["run-a", "run-b"]

    # Restoring one leaves the other alone — no read-modify-write clobbering.
    app_settings.set_archived(tmp_path, "experiment", "run-a", False)
    assert app_settings.load(tmp_path).archived_experiments == ["run-b"]


def test_archiving_twice_does_not_duplicate(tmp_path):
    app_settings.set_archived(tmp_path, "experiment", "run-a", True)
    app_settings.set_archived(tmp_path, "experiment", "run-a", True)
    assert app_settings.load(tmp_path).archived_experiments == ["run-a"]


def test_dataset_names_are_case_insensitive(tmp_path):
    app_settings.set_archived(tmp_path, "dataset", "Hurricane", True)
    archive = app_settings.archive(tmp_path)
    assert archive.has_dataset("hurricane")
    assert archive.has_dataset("HURRICANE")
    # And restoring under a different case still removes it.
    app_settings.set_archived(tmp_path, "dataset", "hurricane", False)
    assert not app_settings.archive(tmp_path).has_dataset("Hurricane")


def test_unknown_kind_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="unknown archive kind"):
        app_settings.set_archived(tmp_path, "universe", "x", True)


def test_empty_id_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="id is required"):
        app_settings.set_archived(tmp_path, "experiment", "   ", True)


@pytest.fixture(autouse=True)
def isolated_hypotheses(tmp_path, monkeypatch):
    """The stored-hypothesis directory is repo-global; keep tests off it."""
    monkeypatch.setenv("ASTAVERSE_HYPOTHESES", str(tmp_path / "hypotheses"))


def _seed(runs_dir, hypothesis, dataset):
    from astaverse.core.store import Run

    return Run.create(runs_dir, hypothesis, dataset)


def test_archived_experiment_drops_its_derived_claim(tmp_path):
    runs = tmp_path / "runs"
    analysis = _seed(runs, "X causes Y", "data/datasets/demo")
    cid = claims_core.claim_id("X causes Y", "data/datasets/demo")
    assert [c.id for c in claims_core.all_claims(runs)] == [cid]

    app_settings.set_archived(runs, "experiment", analysis.run_id, True)
    # The claim was derived only from that run, so nothing is left to show.
    assert claims_core.all_claims(runs) == []
    # But it is still reachable by id, and still listed when asked for.
    assert claims_core.get_claim(runs, cid) is not None
    assert [c.id for c in claims_core.all_claims(runs, include_archived=True)] == [cid]


def test_archiving_a_hypothesis_hides_it_with_its_experiments(tmp_path):
    runs = tmp_path / "runs"
    _seed(runs, "X causes Y", "data/datasets/demo")
    cid = claims_core.claim_id("X causes Y", "data/datasets/demo")

    app_settings.set_archived(runs, "hypothesis", cid, True)
    assert claims_core.all_claims(runs) == []
    assert claims_core.get_claim(runs, cid) is not None


def test_archiving_a_dataset_hides_every_claim_on_it(tmp_path):
    runs = tmp_path / "runs"
    _seed(runs, "X causes Y", "data/datasets/demo")
    _seed(runs, "P causes Q", "data/datasets/demo")
    _seed(runs, "M causes N", "data/datasets/other")
    assert len(claims_core.all_claims(runs)) == 3

    app_settings.set_archived(runs, "dataset", "demo", True)
    remaining = claims_core.all_claims(runs)
    assert [c.dataset_name for c in remaining] == ["other"]
