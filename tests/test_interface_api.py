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
    run = Run.load(runs_dir, created.json()["run_id"])
    manifest = run.manifest()
    assert manifest["config"]["decisions"]["mode"] == "direct"
    assert manifest["config"]["universes"]["cap"] == 7
    assert manifest["review_before_execute"] is False


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
