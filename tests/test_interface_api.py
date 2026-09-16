"""Contracts used by the Hypothesis / Experiment interface."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from astaverse.core.schemas import Column, StudySpec
from astaverse.core.store import Run


@pytest.fixture
def runs_dir(tmp_path, monkeypatch):
    directory = tmp_path / "runs"
    directory.mkdir()
    monkeypatch.setenv("ASTAVERSE_RUNS", str(directory))
    monkeypatch.setenv("ASTAVERSE_HYPOTHESES", str(tmp_path / "hypotheses"))
    return directory


@pytest.fixture
def client(runs_dir):
    from astaverse.adapters import api

    return TestClient(api.app)


@pytest.fixture
def experiment(runs_dir, tmp_path):
    csv = tmp_path / "data.csv"
    csv.write_text("x,y\n1,2\n")
    run = Run.create(runs_dir, "X changes Y", str(csv))
    run.write_artifact(
        "study",
        StudySpec(
            hypothesis="X changes Y",
            dataset_path=str(csv),
            dataset_name="data",
            n_rows=1,
            columns=[Column(name="x", dtype="number")],
        ),
    )
    run.record_stage("study")
    return run


def test_overview_uses_interface_vocabulary(client, experiment):
    payload = client.get("/api/overview").json()
    assert set(payload) == {"hypotheses", "experiments", "datasets"}
    assert payload["hypotheses"][0]["hypothesis"] == "X changes Y"
    assert payload["experiments"][0]["id"] == experiment.run_id


def test_old_mode_names_load_but_api_emits_public_names(client, experiment):
    manifest = experiment.manifest()
    manifest["config"] = {"decisions": {"mode": "plan_diff"}}
    experiment.write_manifest(manifest)

    payload = client.get(f"/api/experiments/{experiment.run_id}").json()

    assert payload["config"]["decisions"]["mode"] == "sample_plans"


def test_command_preview_is_method_aware(client):
    response = client.post(
        "/api/command-preview",
        json={
            "experiment_id": "exp-1",
            "config": {
                "decisions": {"mode": "direct"},
                "through": "verdicts",
            },
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert "plans" not in payload["planned_stages"]
    assert "--decisions.mode direct" in payload["run"]
    assert payload["run"].startswith("astaverse run exp-1")


def test_command_preview_exposes_conclusion_as_final_stage(client):
    response = client.post(
        "/api/command-preview",
        json={
            "experiment_id": "exp-1",
            "config": {"through": "conclusion"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["planned_stages"][-1] == "conclusion"
    assert "astaverse stage exp-1 conclusion" in payload["stages"]["conclusion"]


def test_application_defaults_are_snapshotted_on_creation(client, runs_dir, tmp_path):
    saved = client.put(
        "/api/settings",
        json={
            "default_experiment": {
                "decisions": {"mode": "direct"},
                "universes": {"cap": 7},
            },
            "review_before_execute": False,
        },
    )
    assert saved.status_code == 200

    csv = tmp_path / "fresh.csv"
    csv.write_text("a,b\n1,2\n")
    created = client.post(
        "/api/hypotheses",
        json={"hypothesis": "A predicts B", "dataset": str(csv)},
    )
    assert created.status_code == 200
    assert Run.list_all(runs_dir) == []

    experiment = client.post(
        f"/api/hypotheses/{created.json()['id']}/experiments",
        json={},
    )
    assert experiment.status_code == 200
    run = Run.load(runs_dir, experiment.json()["run_id"])
    manifest = run.manifest()
    assert manifest["config"]["decisions"]["mode"] == "direct"
    assert manifest["config"]["universes"]["cap"] == 7
    assert manifest["review_before_execute"] is False


def test_new_experiment_generates_a_fresh_plan_instead_of_inheriting_seed(
    client, experiment, runs_dir
):
    manifest = experiment.manifest()
    manifest["seed"] = {
        "source_path": "/tmp/autodiscovery-plans.jsonl",
        "normalized_id": "seed-1",
    }
    experiment.write_manifest(manifest)
    claim_id = client.get("/api/hypotheses").json()[0]["id"]

    created = client.post(
        f"/api/hypotheses/{claim_id}/experiments",
        json={"config": {"decisions": {"mode": "audit_plan"}}},
    )

    assert created.status_code == 200
    fresh = Run.load(runs_dir, created.json()["run_id"])
    assert "seed" not in fresh.manifest()


def test_review_gate_pauses_then_allows_continuation(client, experiment, monkeypatch):
    from astaverse.core import runner

    manifest = experiment.manifest()
    manifest["config"] = {"through": "verdicts"}
    manifest["review_before_execute"] = True
    experiment.write_manifest(manifest)
    seen: list[str] = []
    monkeypatch.setattr(
        runner,
        "start_sequence",
        lambda run, through=None, force=False: seen.append(through) or {"running": True},
    )

    first = client.post(f"/api/experiments/{experiment.run_id}/run")
    assert first.status_code == 200
    assert seen == ["decisions"]

    experiment.record_stage("decisions")
    approved = client.post(f"/api/experiments/{experiment.run_id}/review")
    assert approved.status_code == 200
    second = client.post(f"/api/experiments/{experiment.run_id}/run?confirm=true")
    assert second.status_code == 200
    assert seen[-1] == "verdicts"


def test_billable_execution_requires_explicit_confirmation(client, experiment, monkeypatch):
    from astaverse.core import runner

    manifest = experiment.manifest()
    manifest["config"] = {"through": "verdicts"}
    manifest["review_before_execute"] = False
    experiment.write_manifest(manifest)
    started = False

    def start(*args, **kwargs):
        nonlocal started
        started = True
        return {"running": True}

    monkeypatch.setattr(runner, "start_sequence", start)

    blocked = client.post(f"/api/experiments/{experiment.run_id}/run")
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["requires_confirmation"] is True
    assert started is False

    accepted = client.post(f"/api/experiments/{experiment.run_id}/run?confirm=true")
    assert accepted.status_code == 200
    assert started is True


def test_deletion_requires_dependents_to_be_removed_first(client, runs_dir, tmp_path):
    csv = tmp_path / "delete-me.csv"
    csv.write_text("x,y\n1,2\n")
    created = client.post(
        "/api/hypotheses",
        json={"hypothesis": "X predicts Y", "dataset": str(csv)},
    ).json()
    hypothesis_id = created["id"]
    experiment = client.post(
        f"/api/hypotheses/{hypothesis_id}/experiments",
        json={},
    ).json()

    blocked = client.delete(f"/api/hypotheses/{hypothesis_id}")
    assert blocked.status_code == 409

    deleted_experiment = client.delete(f"/api/experiments/{experiment['run_id']}")
    assert deleted_experiment.status_code == 200
    assert not (runs_dir / experiment["run_id"]).exists()

    deleted_hypothesis = client.delete(f"/api/hypotheses/{hypothesis_id}")
    assert deleted_hypothesis.status_code == 200


def test_dataset_deletion_is_blocked_by_hypotheses(client, tmp_path, monkeypatch):
    root = tmp_path / "datasets"
    folder = root / "sample"
    folder.mkdir(parents=True)
    (folder / "data.csv").write_text("x,y\n1,2\n")
    (folder / "info.json").write_text(
        '{"data_desc":{"dataset_description":"Sample","num_rows":1,"fields":[]}}'
    )
    monkeypatch.setenv("ASTAVERSE_DATASETS", str(root))

    hypothesis = client.post(
        "/api/hypotheses",
        json={"hypothesis": "X predicts Y", "dataset": "sample"},
    ).json()

    blocked = client.delete("/api/datasets/sample")
    assert blocked.status_code == 409

    assert client.delete(f"/api/hypotheses/{hypothesis['id']}").status_code == 200
    assert client.delete("/api/datasets/sample").status_code == 200
    assert not folder.exists()
