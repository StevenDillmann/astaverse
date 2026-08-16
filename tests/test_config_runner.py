"""Per-run configuration and the sequential runner.

The load-bearing property: a stage run on its own and the same stage run as
part of "run all" use the same settings. Two sets of defaults — one in the
CLI, one in the UI — would make a finished study impossible to interpret.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from astaverse import config as run_config
from astaverse import runner
from astaverse.schemas import Column, StudySpec
from astaverse.store import Run


@pytest.fixture
def runs_dir(tmp_path, monkeypatch):
    d = tmp_path / "runs"
    d.mkdir()
    monkeypatch.setenv("ASTAVERSE_RUNS", str(d))
    return d


@pytest.fixture
def run_obj(runs_dir, tmp_path):
    csv = tmp_path / "data.csv"
    csv.write_text("a,b\n1,2\n3,4\n")
    r = Run.create(runs_dir, "X causes Y", str(csv))
    r.write_artifact(
        "study",
        StudySpec(
            hypothesis="X causes Y",
            dataset_path=str(csv),
            dataset_name="d",
            n_rows=2,
            columns=[Column(name="a", dtype="number")],
        ),
    )
    r.record_stage("study")
    return r


@pytest.fixture
def client(runs_dir):
    from astaverse import server

    return TestClient(server.app)


# -- config ----------------------------------------------------------------


def test_defaults_stop_before_spending_money(run_obj):
    """`through` must not default past `execute`, which launches an agent."""
    cfg = run_config.load(run_obj)
    assert cfg.through == "universes"
    assert "execute" not in cfg.stages_through()


def test_update_merges_sections_rather_than_replacing(run_obj):
    run_config.update(run_obj, {"decisions": {"mode": "schema_lint"}})
    run_config.update(run_obj, {"decisions": {"critique": True}})
    cfg = run_config.load(run_obj)
    # The second update must not have discarded the first.
    assert cfg.decisions.mode == "schema_lint"
    assert cfg.decisions.critique is True


def test_config_survives_a_reload(run_obj, runs_dir):
    run_config.update(run_obj, {"universes": {"cap": 7}})
    reloaded = Run.load(runs_dir, run_obj.run_id)
    assert run_config.load(reloaded).universes.cap == 7


def test_stages_through_rejects_an_unknown_target(run_obj):
    cfg = run_config.load(run_obj)
    cfg.through = "nonsense"
    with pytest.raises(ValueError):
        cfg.stages_through()


def test_config_endpoints_round_trip(client, run_obj):
    response = client.put(
        f"/api/runs/{run_obj.run_id}/config",
        json={"plans": {"k": 9}, "through": "decisions"},
    )
    assert response.status_code == 200
    assert response.json()["plans"]["k"] == 9

    fetched = client.get(f"/api/runs/{run_obj.run_id}/config").json()
    assert fetched["plans"]["k"] == 9
    assert fetched["through"] == "decisions"


# -- runner ----------------------------------------------------------------


def test_run_stage_uses_the_saved_config(run_obj, monkeypatch):
    """The whole point: the runner supplies config, callers do not."""
    seen = {}

    def fake_plans(run, k=None, model=None, temperature=None, seed_plan=None):
        seen.update(k=k, model=model, temperature=temperature)

    monkeypatch.setattr(runner.s2_plans, "run", fake_plans)
    run_config.update(
        run_obj, {"plans": {"k": 4, "model": "openai/x", "temperature": 0.3}}
    )
    runner.run_stage(run_obj, "plans")
    assert seen == {"k": 4, "model": "openai/x", "temperature": 0.3}


def test_sequence_skips_completed_stages(run_obj, monkeypatch):
    ran: list[str] = []
    monkeypatch.setattr(runner, "run_stage", lambda r, s: ran.append(s))

    progress = runner.run_sequence(run_obj, through="plans")
    assert "study" in progress.skipped
    assert ran == ["plans"]
    assert progress.failed is None
    assert progress.finished


def test_sequence_stops_at_the_first_failure(run_obj, monkeypatch):
    """A later stage must not run on the output of a stage that failed."""
    ran: list[str] = []

    def flaky(_run, stage):
        ran.append(stage)
        if stage == "plans":
            raise RuntimeError("no api key")

    monkeypatch.setattr(runner, "run_stage", flaky)
    progress = runner.run_sequence(run_obj, through="universes")

    assert progress.failed == "plans"
    assert "no api key" in (progress.error or "")
    assert "decisions" not in ran and "universes" not in ran
    assert progress.finished


def test_failure_is_reported_not_raised(run_obj, monkeypatch):
    """The runner is called from a server thread; it must not crash it."""
    monkeypatch.setattr(
        runner, "run_stage", lambda r, s: (_ for _ in ()).throw(ValueError("boom"))
    )
    progress = runner.run_sequence(run_obj, through="plans")
    assert progress.failed == "plans"
    assert "ValueError" in (progress.error or "")


def test_force_reruns_completed_stages(run_obj, monkeypatch):
    ran: list[str] = []
    monkeypatch.setattr(runner, "run_stage", lambda r, s: ran.append(s))
    runner.run_sequence(run_obj, through="study", force=True)
    assert ran == ["study"]


def test_api_refuses_a_single_stage_while_a_sequence_runs(client, run_obj, monkeypatch):
    monkeypatch.setattr(runner, "is_running", lambda run_id: True)
    response = client.post(f"/api/runs/{run_obj.run_id}/stages/plans")
    assert response.status_code == 409
    assert "already in progress" in response.json()["detail"]["error"]
