"""Grid enumeration: constraints, capping, and the default universe."""

from __future__ import annotations

import pytest

from astaverse.integrations.astra_io import (
    enumerate_universes,
    read_astra_yaml,
    satisfies_constraints,
    write_astra_yaml,
    write_universe_files,
)
from astaverse.core.schemas import Decision, DecisionKind, DecisionSpec, Option


def _decisions() -> dict[str, Decision]:
    return {
        "scaling": Decision(
            label="Scaling",
            default="standard",
            options={
                "none": Option(label="None"),
                "standard": Option(label="Standard"),
                "minmax": Option(label="MinMax", incompatible_with=["model.svm"]),
            },
        ),
        "model": Decision(
            label="Model",
            default="ols",
            kind=DecisionKind.model,
            options={
                "ols": Option(label="OLS"),
                "svm": Option(label="SVM", requires=["scaling.standard"]),
            },
        ),
    }


def test_default_universe_is_first_and_flagged():
    result = enumerate_universes(_decisions())
    assert result.universes[0].is_default
    assert result.universes[0].decisions == {"scaling": "standard", "model": "ols"}
    assert sum(u.is_default for u in result.universes) == 1


def test_constraints_prune_invalid_combinations():
    result = enumerate_universes(_decisions())
    # svm requires scaling.standard, so svm+none and svm+minmax are both out.
    for universe in result.universes:
        if universe.decisions["model"] == "svm":
            assert universe.decisions["scaling"] == "standard"
    assert result.n_total_grid == 6
    assert len(result.universes) == 4
    assert result.n_dropped_constraints == 2


def test_incompatible_with_is_symmetric_in_effect():
    # minmax declares incompatible_with model.svm; svm requires scaling.standard.
    # Either constraint alone removes the pair, and the pair must not appear.
    result = enumerate_universes(_decisions())
    pairs = {(u.decisions["scaling"], u.decisions["model"]) for u in result.universes}
    assert ("minmax", "svm") not in pairs


def test_cap_truncates_and_reports_rather_than_silently_dropping():
    result = enumerate_universes(_decisions(), cap=2)
    assert len(result.universes) == 2
    assert result.n_dropped_cap == 2
    assert result.truncated
    # The default universe survives truncation: it is the comparison baseline.
    assert result.universes[0].is_default


def test_exclude_removes_a_decision_from_the_grid():
    result = enumerate_universes(_decisions(), exclude=["model"])
    assert all(set(u.decisions) == {"scaling"} for u in result.universes)
    assert len(result.universes) == 3


def test_constraints_against_excluded_decisions_are_ignored_not_violated():
    # With `model` excluded, minmax's incompatible_with model.svm is moot.
    result = enumerate_universes(_decisions(), exclude=["model"])
    assert {u.decisions["scaling"] for u in result.universes} == {"none", "standard", "minmax"}


def test_unknown_option_fails_constraint_check():
    assert not satisfies_constraints({"scaling": "nonexistent"}, _decisions())


@pytest.fixture
def spec() -> DecisionSpec:
    return DecisionSpec(
        id="demo",
        name="Demo",
        hypothesis="X causes Y",
        dataset_path="/data.csv",
        decisions=_decisions(),
    )


def test_astra_yaml_round_trips(tmp_path, spec):
    path = tmp_path / "astra.yaml"
    write_astra_yaml(spec, path)
    loaded = read_astra_yaml(path)

    assert loaded.hypothesis == spec.hypothesis
    assert loaded.dataset_path == spec.dataset_path
    assert set(loaded.decisions) == set(spec.decisions)
    assert loaded.decisions["model"].kind is DecisionKind.model
    assert loaded.decisions["model"].options["svm"].requires == ["scaling.standard"]
    assert loaded.decisions["scaling"].default == "standard"


def test_hand_written_astra_yaml_without_extensions_loads(tmp_path):
    """A spec can be hand-authored to skip plan generation and extraction."""
    path = tmp_path / "astra.yaml"
    path.write_text(
        """
id: manual
name: Manual
inputs:
  - id: dataset
    type: data
    source: /data.csv
decisions:
  outlier:
    label: Outlier handling
    default: keep
    options:
      keep: {label: Keep all}
      drop: {label: Drop beyond 3 SD}
prior_insights:
  hypothesis:
    claim: X causes Y
"""
    )
    loaded = read_astra_yaml(path)
    assert loaded.hypothesis == "X causes Y"
    assert loaded.decisions["outlier"].default == "keep"
    assert not loaded.decisions["outlier"].post_hoc


def test_universe_files_are_astra_shaped(tmp_path):
    import yaml

    result = enumerate_universes(_decisions())
    paths = write_universe_files(result, tmp_path)
    assert len(paths) == len(result.universes)

    doc = yaml.safe_load(paths[0].read_text())
    assert doc["id"] == "universe_000"
    assert {d["decision_id"] for d in doc["decisions"]} == {"scaling", "model"}
    assert all({"decision_id", "option_id"} == set(d) for d in doc["decisions"])


def test_rewriting_universes_clears_stale_files(tmp_path):
    write_universe_files(enumerate_universes(_decisions()), tmp_path)
    write_universe_files(enumerate_universes(_decisions(), cap=2), tmp_path)
    assert len(list(tmp_path.glob("universe_*.yaml"))) == 2


def _wide_decisions() -> dict[str, Decision]:
    """Three independent 3-option decisions: 27 combinations, no constraints."""
    return {
        name: Decision(
            label=name,
            default="a",
            options={o: Option(label=o) for o in ("a", "b", "c")},
        )
        for name in ("first", "second", "third")
    }


def test_cap_samples_across_the_grid_rather_than_taking_a_prefix():
    """A prefix would hold the leading decisions fixed and make them look inert.

    itertools.product varies the LAST decision fastest, so valid[:cap] pins
    `first` to its earliest option. Every decision must stay represented.
    """
    result = enumerate_universes(_wide_decisions(), cap=9)
    assert len(result.universes) == 9
    assert result.n_dropped_cap == 18

    for decision in ("first", "second", "third"):
        seen = {u.decisions[decision] for u in result.universes}
        assert seen == {"a", "b", "c"}, f"{decision} lost options under the cap: {seen}"


def test_cap_keeps_the_default_universe_first():
    result = enumerate_universes(_wide_decisions(), cap=5)
    assert result.universes[0].is_default
    assert result.universes[0].decisions == {"first": "a", "second": "a", "third": "a"}


def test_cap_returns_distinct_universes():
    result = enumerate_universes(_wide_decisions(), cap=9)
    keys = [tuple(sorted(u.decisions.items())) for u in result.universes]
    assert len(set(keys)) == len(keys)


def test_cap_of_one_yields_just_the_default():
    result = enumerate_universes(_wide_decisions(), cap=1)
    assert len(result.universes) == 1
    assert result.universes[0].is_default
