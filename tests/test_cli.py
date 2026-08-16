"""The CLI adapter.

The dangerous property here: tyro returns a fully-populated config object, so
"not passed" and "passed at its default" look identical. Saving that object
wholesale silently resets everything the user configured earlier — running
`astaverse run <id>` with no flags would wipe the saved configuration. These
tests pin the merge behaviour that prevents it.
"""

from __future__ import annotations

import pytest

from astaverse.adapters.cli import _explicit_patch
from astaverse.core import config as run_cfg
from astaverse.core.config import RunConfig
from astaverse.core.schemas import Column, StudySpec
from astaverse.core.store import Run


@pytest.fixture
def analysis(tmp_path, monkeypatch):
    runs = tmp_path / "runs"
    runs.mkdir()
    monkeypatch.setenv("ASTAVERSE_RUNS", str(runs))
    csv = tmp_path / "data.csv"
    csv.write_text("a,b\n1,2\n")
    a = Run.create(runs, "X causes Y", str(csv))
    a.write_artifact(
        "study",
        StudySpec(
            hypothesis="X causes Y",
            dataset_path=str(csv),
            dataset_name="d",
            n_rows=1,
            columns=[Column(name="a", dtype="number")],
        ),
    )
    a.record_stage("study")
    return a


def test_no_flags_means_no_patch():
    """The bug this guards: an empty patch, not a config full of defaults."""
    assert _explicit_patch(RunConfig(), argv=["run", "some-id"]) == {}


def test_only_typed_fields_appear_in_the_patch():
    config = RunConfig.model_validate({"plans": {"k": 9}, "universes": {"cap": 3}})
    patch = _explicit_patch(config, argv=["run", "id", "--plans.k", "9"])
    assert patch == {"plans": {"k": 9}}
    assert "universes" not in patch, "a field the user never typed leaked in"


def test_a_value_equal_to_its_default_is_still_honoured():
    """Passing --plans.k 5 explicitly must register, even though 5 is default."""
    patch = _explicit_patch(RunConfig(), argv=["run", "id", "--plans.k", "5"])
    assert patch == {"plans": {"k": 5}}


def test_equals_form_is_recognised():
    config = RunConfig.model_validate({"universes": {"cap": 12}})
    assert _explicit_patch(config, argv=["run", "id", "--universes.cap=12"]) == {
        "universes": {"cap": 12}
    }


def test_boolean_negation_form_is_recognised():
    config = RunConfig.model_validate({"decisions": {"critique": False}})
    patch = _explicit_patch(config, argv=["run", "id", "--decisions.no-critique"])
    assert patch == {"decisions": {"critique": False}}


def test_top_level_field_is_recognised():
    config = RunConfig.model_validate({"through": "surprisal"})
    assert _explicit_patch(config, argv=["run", "id", "--through", "surprisal"]) == {
        "through": "surprisal"
    }


def test_non_config_flags_are_ignored():
    """--force and --yes belong to the command, not the configuration."""
    patch = _explicit_patch(RunConfig(), argv=["run", "id", "--force", "--yes"])
    assert patch == {}


def test_running_with_no_flags_preserves_a_saved_config(analysis):
    """The end-to-end version of the bug: saved settings must survive."""
    run_cfg.update(
        analysis,
        {
            "plans": {"k": 11, "model": "openai/custom"},
            "decisions": {"mode": "schema_lint", "critique": True},
            "universes": {"cap": 3},
        },
    )

    # Simulate `astaverse run <id>` with no configuration flags.
    patch = _explicit_patch(RunConfig(), argv=["run", analysis.run_id])
    if patch:
        run_cfg.update(analysis, patch)

    after = run_cfg.load(analysis)
    assert after.plans.k == 11
    assert after.plans.model == "openai/custom"
    assert after.decisions.mode == "schema_lint"
    assert after.decisions.critique is True
    assert after.universes.cap == 3


def test_one_flag_does_not_reset_its_siblings(analysis):
    """Changing plans.k must not clear plans.model set earlier."""
    run_cfg.update(analysis, {"plans": {"k": 11, "model": "openai/custom"}})

    config = RunConfig.model_validate({"plans": {"k": 4}})
    run_cfg.update(analysis, _explicit_patch(config, argv=["run", "id", "--plans.k", "4"]))

    after = run_cfg.load(analysis)
    assert after.plans.k == 4
    assert after.plans.model == "openai/custom", "sibling field was clobbered"
