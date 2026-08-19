"""The read models the screens are built on.

These endpoints exist so the client never joins or derives. The tests check
exactly that: that what a screen needs arrives whole, already computed, and
that the derived fields are right — because if the frontend has to fix them
up, the logic moves somewhere it cannot be tested.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from astaverse.core import config as run_cfg
from astaverse.core.schemas import Column, StudySpec
from astaverse.core.store import Run


@pytest.fixture
def runs_dir(tmp_path, monkeypatch):
    d = tmp_path / "runs"
    d.mkdir()
    monkeypatch.setenv("ASTAVERSE_RUNS", str(d))
    return d


@pytest.fixture
def client(runs_dir):
    from astaverse.adapters import api

    return TestClient(api.app)


def make(runs_dir, tmp_path, hypothesis, dataset="d.csv", config=None):
    csv = tmp_path / dataset
    csv.write_text("a,b\n1,2\n")
    a = Run.create(runs_dir, hypothesis, str(csv))
    a.write_artifact(
        "study",
        StudySpec(
            hypothesis=hypothesis,
            dataset_path=str(csv),
            dataset_name=dataset.replace(".csv", ""),
            n_rows=1,
            columns=[Column(name="a", dtype="number")],
        ),
    )
    a.record_stage("study")
    if config:
        run_cfg.update(a, config)
    return a


def test_home_serves_all_three_granularities(client, runs_dir, tmp_path):
    make(runs_dir, tmp_path, "X causes Y")
    make(runs_dir, tmp_path, "X causes Y")  # same claim, second attempt
    make(runs_dir, tmp_path, "Z causes W")

    home = client.get("/api/home").json()
    assert set(home) == {"claims", "runs", "datasets"}
    assert len(home["claims"]) == 2, "attempts must collapse into their claim"
    assert len(home["runs"]) == 3, "runs stay individual"


def test_home_needs_no_client_side_joining(client, runs_dir, tmp_path):
    """Every row must be drawable without fetching anything else."""
    make(runs_dir, tmp_path, "X causes Y")
    home = client.get("/api/home").json()

    claim = home["claims"][0]
    for key in ("hypothesis", "dataset_name", "support", "n_attempts", "updated_at"):
        assert key in claim, f"claim row missing {key}"

    run = home["runs"][0]
    for key in ("hypothesis", "dataset_name", "config_label", "status", "n_complete"):
        assert key in run, f"run row missing {key}"

    dataset = home["datasets"][0]
    for key in ("name", "n_claims", "n_attempts", "n_fragile"):
        assert key in dataset, f"dataset row missing {key}"


def test_run_rows_carry_a_label_that_distinguishes_them(client, runs_dir, tmp_path):
    """Two attempts differing only in config must be tellable apart."""
    make(runs_dir, tmp_path, "X causes Y", config={"decisions": {"mode": "direct"}})
    make(runs_dir, tmp_path, "X causes Y", config={"decisions": {"mode": "audit_plan"}})

    labels = {r["config_label"] for r in client.get("/api/home").json()["runs"]}
    assert labels == {"direct", "audit_plan"}


def test_a_default_configuration_is_labelled_default(client, runs_dir, tmp_path):
    """The label names what changed, so sample_plans — the default — reads as such.

    Restating a default tells the reader nothing and makes every row look
    configured.
    """
    make(runs_dir, tmp_path, "X causes Y", config={"decisions": {"mode": "sample_plans"}})
    labels = [r["config_label"] for r in client.get("/api/home").json()["runs"]]
    assert labels == ["default"]


def test_only_non_default_settings_appear_in_the_label(client, runs_dir, tmp_path):
    make(
        runs_dir,
        tmp_path,
        "X causes Y",
        config={"decisions": {"mode": "direct", "critique": True}, "universes": {"cap": 24}},
    )
    label = client.get("/api/home").json()["runs"][0]["config_label"]
    assert "direct" in label and "+critique" in label
    assert "cap" not in label, "the default cap must not clutter the label"


def test_identical_configs_still_get_distinct_labels(client, runs_dir, tmp_path):
    """Attempts predating a knob both read 'default'; that cannot collide."""
    make(runs_dir, tmp_path, "X causes Y")
    make(runs_dir, tmp_path, "X causes Y")
    labels = [r["config_label"] for r in client.get("/api/home").json()["runs"]]
    assert len(set(labels)) == 2, f"labels collided: {labels}"


def test_datasets_row_counts_claims_not_runs(client, runs_dir, tmp_path):
    make(runs_dir, tmp_path, "X causes Y")
    make(runs_dir, tmp_path, "X causes Y")  # same claim
    make(runs_dir, tmp_path, "Z causes W")  # different claim, same dataset

    dataset = client.get("/api/home").json()["datasets"][0]
    assert dataset["n_claims"] == 2
    assert dataset["n_attempts"] == 3


def test_run_detail_carries_its_claim_so_the_ui_can_navigate_up(client, runs_dir, tmp_path):
    analysis = make(runs_dir, tmp_path, "X causes Y")
    detail = client.get(f"/api/runs/{analysis.run_id}").json()
    assert detail["claim_id"]
    assert client.get(f"/api/claims/{detail['claim_id']}").status_code == 200


def test_run_detail_includes_config_and_artifacts(client, runs_dir, tmp_path):
    analysis = make(runs_dir, tmp_path, "X causes Y", config={"universes": {"cap": 7}})
    detail = client.get(f"/api/runs/{analysis.run_id}").json()
    assert detail["config"]["universes"]["cap"] == 7
    assert detail["artifacts"]["study"]["n_rows"] == 1
    assert detail["artifacts"]["plans"] is None


def test_unknown_claim_is_a_404_not_an_empty_page(client):
    assert client.get("/api/claims/nope").status_code == 404


def test_home_is_empty_but_valid_with_no_runs(client):
    home = client.get("/api/home").json()
    assert home == {"claims": [], "runs": [], "datasets": []}
