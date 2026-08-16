"""Guards around the stages that can spend money or corrupt a run.

These all came from a real incident: clicking Run on `execute` in the UI for a
run whose task path resolved wrongly. Harbor crashed, and the stage was
recorded as complete anyway — which would have let `verdicts` read a
nonexistent sweep and report an empty multiverse as a result.
"""

from __future__ import annotations

import pytest
from pathlib import Path  # noqa: F401  (used by the absolute-path test)
from fastapi.testclient import TestClient

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
    from astaverse.adapters import api as server

    return TestClient(server.app)


@pytest.fixture
def bare_run(runs_dir, tmp_path):
    csv = tmp_path / "data.csv"
    csv.write_text("a,b\n1,2\n3,4\n")
    run_obj = Run.create(runs_dir, "X causes Y", str(csv))
    run_obj.write_artifact(
        "study",
        StudySpec(
            hypothesis="X causes Y",
            dataset_path=str(csv),
            dataset_name="d",
            n_rows=2,
            columns=[Column(name="a", dtype="number")],
        ),
    )
    run_obj.record_stage("study")
    return run_obj


def test_run_root_is_always_absolute(runs_dir, monkeypatch, tmp_path):
    """A relative runs dir must not produce relative task paths.

    Stages shell out to harbor and docker with their own cwd; a relative path
    resolves against the wrong directory and the tool fails confusingly.
    """
    monkeypatch.chdir(tmp_path)
    run_obj = Run(runs_dir.name)  # deliberately relative
    assert run_obj.root.is_absolute()
    assert run_obj.task_dir.is_absolute()
    assert run_obj.jobs_dir.is_absolute()


def test_api_refuses_a_stage_whose_inputs_are_missing(client, bare_run):
    """The UI disabling a button is not a guard — the server must check."""
    response = client.post(f"/api/analyses/{bare_run.run_id}/stages/execute")
    assert response.status_code == 409
    detail = response.json()["detail"]
    assert "cannot run 'execute'" in detail["error"]
    assert "plans" in detail["missing"]


def test_api_allows_the_next_ready_stage(client, bare_run):
    """The guard must not block legitimate work — plans is next after study."""
    response = client.post(f"/api/analyses/{bare_run.run_id}/stages/plans")
    # It will fail for want of an API key in the test environment, but it must
    # get past the prerequisite guard to do so.
    assert response.status_code != 409


def test_failed_harbor_run_is_not_recorded_as_complete(bare_run, monkeypatch):
    import subprocess

    from astaverse.core.stages import s6_execute
    from astaverse.core.stages.s5_task import TaskArtifact

    task_dir = bare_run.task_dir
    task_dir.mkdir(parents=True)
    bare_run.write_artifact(
        "task",
        TaskArtifact(task_dir=str(task_dir), task_name="t", n_universes=2, files=[]),
    )

    class Failed:
        returncode = 1

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: Failed())

    with pytest.raises(RuntimeError, match="harbor run failed"):
        s6_execute.run(bare_run, agent="terminus-2", models=["openai/gpt-5.6-luna"])

    # Not marked complete...
    assert "execute" not in bare_run.manifest()["stages"]
    # ...but the attempted command is still on disk for debugging.
    assert bare_run.artifact_path("execute").exists()


def test_dry_run_never_marks_execute_complete(bare_run):
    from astaverse.core.stages import s6_execute
    from astaverse.core.stages.s5_task import TaskArtifact

    task_dir = bare_run.task_dir
    task_dir.mkdir(parents=True)
    bare_run.write_artifact(
        "task",
        TaskArtifact(task_dir=str(task_dir), task_name="t", n_universes=2, files=[]),
    )
    artifact = s6_execute.run(bare_run, dry_run=True)
    assert artifact.dry_run
    assert "execute" not in bare_run.manifest()["stages"]
