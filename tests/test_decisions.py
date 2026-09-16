"""Decision-space normalization for constraints emitted by an LLM."""

from astaverse.core.schemas import Decision, Option
from astaverse.core.stages.s3_decisions import _normalize_conditional_constraints
from astaverse.integrations.astra_io import (
    default_selections,
    enumerate_universes,
    satisfies_constraints,
)


def test_or_like_requirements_and_conditional_decisions_are_normalized():
    decisions = {
        "measure": Decision(
            label="Measure",
            default="coder",
            options={
                "coder": Option(label="Coder"),
                "crowd": Option(label="Crowd"),
                "average": Option(label="Average"),
                "binary": Option(label="Binary"),
            },
        ),
        "contrast": Decision(
            label="Contrast",
            default="one_unit",
            options={
                "one_unit": Option(label="One unit"),
                "iqr": Option(
                    label="IQR",
                    requires=[
                        "measure.coder",
                        "measure.crowd",
                        "measure.average",
                    ],
                ),
            },
        ),
        "aggregation": Decision(
            label="Aggregation",
            default="raw_mean",
            options={
                "raw_mean": Option(label="Raw mean", requires=["measure.average"]),
                "z_mean": Option(label="Z mean", requires=["measure.average"]),
            },
        ),
    }

    _normalize_conditional_constraints(decisions)

    assert decisions["contrast"].options["iqr"].requires == []
    assert decisions["contrast"].options["iqr"].incompatible_with == ["measure.binary"]
    assert decisions["aggregation"].default == "not_applicable"
    assert decisions["aggregation"].options["not_applicable"].incompatible_with == [
        "measure.average"
    ]
    assert satisfies_constraints(default_selections(decisions), decisions)

    universes = enumerate_universes(decisions, cap=None)
    assert {row.decisions["measure"] for row in universes.universes} == {
        "coder",
        "crowd",
        "average",
        "binary",
    }
    assert {row.decisions["contrast"] for row in universes.universes} == {
        "one_unit",
        "iqr",
    }
