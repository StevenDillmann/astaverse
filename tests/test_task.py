"""Harbor task emission, and the structural check that guards bias control 1.

The check is the only thing standing between "one parametric sweep" and "an
agent quietly hand-writing a different analysis per universe", so it is tested
against a deliberately broken submission, not only a good one.
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from astaverse.astra_io import enumerate_universes, write_astra_yaml, write_universe_files
from astaverse.schemas import (
    Column,
    Decision,
    DecisionKind,
    DecisionSpec,
    Option,
    StudySpec,
)
from astaverse.stages import s5_task
from astaverse.store import Run

GOOD_ANALYSIS = '''
import json, yaml
from pathlib import Path

def analyze(df, selections):
    """One parametric analysis; every choice comes from `selections`."""
    sign = -1 if selections["direction"] == "flipped" else 1
    return {"estimate": 0.2 * sign, "std_error": 0.1,
            "p_value": 0.02, "n": 94, "direction": "positive", "converged": True}

def main():
    for path in sorted(Path("universes").glob("universe_*.yaml")):
        doc = yaml.safe_load(path.read_text())
        selections = {d["decision_id"]: d["option_id"] for d in doc["decisions"]}
        row = {"universe_id": doc["id"], "decisions": selections, **analyze(None, selections)}
        print(json.dumps(row))
'''

BROKEN_SPECIAL_CASE = '''
def analyze(df, selections):
    return {"estimate": 0.2}

def main():
    for uid in ["universe_000", "universe_001"]:
        if uid == "universe_001":          # <- special-cases one cell
            estimate = 0.9
        else:
            estimate = 0.2
'''


@pytest.fixture
def spec() -> DecisionSpec:
    return DecisionSpec(
        id="hurricane_multiverse",
        name="hurricane: multiverse analysis",
        hypothesis="Feminine-named hurricanes cause more deaths.",
        dataset_path="",  # filled in by the fixture below
        decisions={
            "direction": Decision(
                label="Minimum pressure direction",
                rationale="Should minimum pressure be sign-flipped?",
                default="raw",
                kind=DecisionKind.preprocessing,
                options={
                    "raw": Option(label="Raw", description="Use min pressure as recorded."),
                    "flipped": Option(label="Flipped", description="Negate so higher = stronger."),
                },
            ),
            "verdict_rule": Decision(
                label="Verdict decision rule",
                default="alpha_05_two_sided",
                kind=DecisionKind.verdict_rule,
                post_hoc=True,
                options={
                    "alpha_05_two_sided": Option(label="p < 0.05"),
                    "alpha_01_two_sided": Option(label="p < 0.01"),
                },
            ),
        },
    )


@pytest.fixture
def prepared_run(tmp_path, spec) -> Run:
    csv = tmp_path / "data.csv"
    csv.write_text("masfem,deaths,min\n5.5,10,950\n8.1,42,920\n")
    spec.dataset_path = str(csv)

    run_obj = Run.create(tmp_path / "runs", spec.hypothesis, str(csv))
    run_obj.write_artifact(
        "study",
        StudySpec(
            hypothesis=spec.hypothesis,
            dataset_path=str(csv),
            dataset_name="hurricane",
            dataset_description="Test fixture.",
            n_rows=2,
            columns=[Column(name="masfem", dtype="number", description="femininity")],
        ),
    )
    write_astra_yaml(spec, run_obj.artifact_path("decisions"))
    universe_set = enumerate_universes(spec.execution_decisions())
    write_universe_files(universe_set, run_obj.universes_dir)
    run_obj.write_artifact("universes", universe_set)
    return run_obj


def test_task_emits_the_expected_files(prepared_run):
    artifact = s5_task.run(prepared_run)
    files = set(artifact.files)
    for expected in (
        "task.toml",
        "instruction.md",
        "environment/Dockerfile",
        "environment/data.csv",
        "environment/astra.yaml",
        "tests/test.sh",
        "tests/rubric.toml",
        "tests/spec.txt",
        "tests/check_universes.py",
        "solution/solve.sh",
    ):
        assert expected in files, f"missing {expected}"
    assert any(f.startswith("environment/universes/") for f in files)


def test_post_hoc_decisions_are_not_sent_to_the_agent(prepared_run):
    """The verdict rule is applied downstream; the agent must not see it as a fork."""
    s5_task.run(prepared_run)
    instruction = (prepared_run.task_dir / "instruction.md").read_text()
    assert "direction" in instruction
    assert "verdict_rule" not in instruction
    # But the judge's copy of the spec does document it.
    assert "verdict_rule" in (prepared_run.task_dir / "tests" / "spec.txt").read_text()


def test_instruction_forbids_a_verdict_field(prepared_run):
    s5_task.run(prepared_run)
    instruction = (prepared_run.task_dir / "instruction.md").read_text()
    assert "no verdict field" in instruction.lower()


def _run_check(task_dir: Path, app_dir: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(task_dir / "tests" / "check_universes.py")],
        env={"ASTAVERSE_APP_DIR": str(app_dir), "PATH": "/usr/bin:/bin"},
        capture_output=True,
        text=True,
    )


def _write_submission(app_dir: Path, universes: list[dict], analysis: str) -> None:
    app_dir.mkdir(parents=True, exist_ok=True)
    (app_dir / "universes.jsonl").write_text(
        "\n".join(json.dumps(u) for u in universes) + "\n"
    )
    (app_dir / "analysis.py").write_text(textwrap.dedent(analysis))


def _valid_rows(prepared_run) -> list[dict]:
    from astaverse.schemas import UniverseSet

    universe_set = prepared_run.read_artifact("universes", UniverseSet)
    return [
        {
            "universe_id": u.id,
            "decisions": u.decisions,
            "estimate": 0.2,
            "estimate_standardized": 0.18,
            "std_error": 0.1,
            "p_value": 0.02,
            "n": 94,
            "direction": "positive",
            "converged": True,
        }
        for u in universe_set.universes
    ]


def test_check_passes_a_well_formed_submission(prepared_run, tmp_path):
    s5_task.run(prepared_run)
    app = tmp_path / "app"
    _write_submission(app, _valid_rows(prepared_run), GOOD_ANALYSIS)
    result = _run_check(prepared_run.task_dir, app)
    assert result.returncode == 0, result.stdout + result.stderr


def test_check_fails_a_per_universe_special_case(prepared_run, tmp_path):
    """Bias control 1, asserted against a submission that actually cheats."""
    s5_task.run(prepared_run)
    app = tmp_path / "app"
    _write_submission(app, _valid_rows(prepared_run), BROKEN_SPECIAL_CASE)
    result = _run_check(prepared_run.task_dir, app)
    assert result.returncode == 1
    assert "branches on a specific universe id" in result.stdout


def test_check_fails_a_smuggled_verdict_field(prepared_run, tmp_path):
    """Bias control 2: the agent must not pre-empt the verdict."""
    s5_task.run(prepared_run)
    app = tmp_path / "app"
    rows = _valid_rows(prepared_run)
    rows[0]["verdict"] = "supported"
    _write_submission(app, rows, GOOD_ANALYSIS)
    result = _run_check(prepared_run.task_dir, app)
    assert result.returncode == 1
    assert "not allowed" in result.stdout


def test_check_fails_on_missing_universes(prepared_run, tmp_path):
    s5_task.run(prepared_run)
    app = tmp_path / "app"
    _write_submission(app, _valid_rows(prepared_run)[:1], GOOD_ANALYSIS)
    result = _run_check(prepared_run.task_dir, app)
    assert result.returncode == 1
    assert "missing" in result.stdout


def test_check_fails_on_a_duplicated_universe(prepared_run, tmp_path):
    s5_task.run(prepared_run)
    app = tmp_path / "app"
    rows = _valid_rows(prepared_run)
    _write_submission(app, rows + [rows[0]], GOOD_ANALYSIS)
    result = _run_check(prepared_run.task_dir, app)
    assert result.returncode == 1
    assert "more than once" in result.stdout


def test_check_fails_without_a_parametric_analyze(prepared_run, tmp_path):
    s5_task.run(prepared_run)
    app = tmp_path / "app"
    _write_submission(app, _valid_rows(prepared_run), "def run_it(df):\n    return {}\n")
    result = _run_check(prepared_run.task_dir, app)
    assert result.returncode == 1
    assert "no `analyze` function" in result.stdout


def test_check_accepts_nulls_for_a_failed_universe(prepared_run, tmp_path):
    """A universe that cannot be computed must be reportable, not omitted."""
    s5_task.run(prepared_run)
    app = tmp_path / "app"
    rows = _valid_rows(prepared_run)
    rows[0].update(estimate=None, estimate_standardized=None, std_error=None,
                   p_value=None, converged=False)
    _write_submission(app, rows, GOOD_ANALYSIS)
    result = _run_check(prepared_run.task_dir, app)
    assert result.returncode == 0, result.stdout


def test_check_fails_when_the_standardized_estimand_is_not_comparable(prepared_run, tmp_path):
    """The defect a real agent actually produced: raw coefficients across scales.

    Estimates spanning orders of magnitude mean the universes were measured in
    different units, so a specification curve over them would show unit changes
    rather than analytic disagreement.
    """
    s5_task.run(prepared_run)
    app = tmp_path / "app"
    rows = _valid_rows(prepared_run)
    rows[0]["estimate_standardized"] = 0.56
    rows[1]["estimate_standardized"] = 45.7
    _write_submission(app, rows, GOOD_ANALYSIS)
    result = _run_check(prepared_run.task_dir, app)
    assert result.returncode == 1
    assert "comparable scale" in result.stdout


def test_check_accepts_a_genuinely_standardized_estimand(prepared_run, tmp_path):
    s5_task.run(prepared_run)
    app = tmp_path / "app"
    rows = _valid_rows(prepared_run)
    for i, r in enumerate(rows):
        r["estimate_standardized"] = 0.15 + 0.02 * i
    _write_submission(app, rows, GOOD_ANALYSIS)
    result = _run_check(prepared_run.task_dir, app)
    assert result.returncode == 0, result.stdout
