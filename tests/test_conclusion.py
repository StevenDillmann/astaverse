"""Structured conclusion stage and its evidence boundary."""

from __future__ import annotations

from astaverse.core.schemas import (
    Decision,
    DecisionKind,
    DecisionSpec,
    Option,
    UniverseResult,
    UniverseStats,
    Verdict,
)
from astaverse.core.stages import s9_conclusion
from astaverse.core.stages.s7_verdicts import CurveSummary, VerdictsArtifact
from astaverse.core.store import Run
from astaverse.integrations.astra_io import write_astra_yaml


def _prepared_run(tmp_path) -> Run:
    csv = tmp_path / "data.csv"
    csv.write_text("x,y\n1,2\n")
    run_obj = Run.create(tmp_path / "runs", "X increases Y", str(csv))
    spec = DecisionSpec(
        id="test",
        name="test",
        hypothesis="X increases Y",
        dataset_path=str(csv),
        decisions={
            "population": Decision(
                label="Population",
                rationale="The claim may differ by population.",
                default="all",
                kind=DecisionKind.variable_choice,
                options={
                    "all": Option(label="All participants"),
                    "older": Option(label="Older participants"),
                },
            ),
            "verdict_rule": Decision(
                label="Verdict rule",
                default="directional",
                kind=DecisionKind.verdict_rule,
                post_hoc=True,
                options={"directional": Option(label="Directional p < .05")},
            ),
        },
    )
    write_astra_yaml(spec, run_obj.artifact_path("decisions"))
    stats = UniverseStats(
        universe_id="universe_000",
        decisions={"population": "all"},
        estimate=0.3,
        estimate_standardized=0.3,
        p_value=0.01,
        direction="positive",
    )
    result = UniverseResult(
        universe_id="universe_000",
        decisions={"population": "all", "verdict_rule": "directional"},
        stats=stats,
        verdict=Verdict.supported,
        verdict_rule="alpha_05_directional",
        is_default=True,
    )
    artifact = VerdictsArtifact(
        results=[result],
        verdict_rules=["alpha_05_directional"],
        curve_summary=CurveSummary(
            scale="standardized",
            n_universes=1,
            n_estimates=1,
            n_with_ci=0,
            minimum=0.3,
            q25=0.3,
            median=0.3,
            q75=0.3,
            maximum=0.3,
            n_significant_positive=1,
            n_significant_negative=0,
            n_indeterminate=0,
        ),
        n_expected=1,
        n_reported=1,
    )
    run_obj.write_artifact("verdicts", artifact)
    return run_obj


def test_response_keeps_evidence_status_independent_from_refinement():
    response = s9_conclusion._ConclusionResponse(
        evidence_status="partially_supported",
        requires_refinement=True,
        answer="The broad claim depends on population.",
        rationale="The population contrast is consequential.",
        refinement_reason="Effects differ by population.",
        refinement_dimensions=["Population"],
        suggested_hypotheses=["X increases Y among older participants."],
    )

    assert response.evidence_status == "partially_supported"
    assert response.requires_refinement is True
    assert response.refinement_dimensions == ["Population"]


def test_response_clears_stray_refinement_fields_when_flag_is_false():
    response = s9_conclusion._ConclusionResponse(
        evidence_status="robustly_supported",
        requires_refinement=False,
        answer="The claim is robust.",
        rationale="Results agree.",
        refinement_reason="Ignore this.",
        refinement_dimensions=["Population"],
        suggested_hypotheses=["Ignore this too."],
    )

    assert response.refinement_reason is None
    assert response.refinement_dimensions == []
    assert response.suggested_hypotheses == []


def test_stage_uses_grounded_snapshot_and_writes_artifact(tmp_path, monkeypatch):
    run_obj = _prepared_run(tmp_path)
    captured = {}

    def fake_call(prompt, schema, model, **kwargs):
        captured.update(prompt=prompt, schema=schema, model=model, kwargs=kwargs)
        return [
            schema(
                evidence_status="robustly_supported",
                requires_refinement=False,
                answer="X consistently increases Y in the analyzed specifications.",
                rationale="The only comparable estimate is positive and significant.",
                key_evidence=["1 of 1 estimates is positive and significant."],
            )
        ]

    monkeypatch.setattr(s9_conclusion, "structured_call", fake_call)
    conclusion = s9_conclusion.run(run_obj, model="openai/test-model")

    assert conclusion.evidence_status == "robustly_supported"
    assert conclusion.model == "openai/test-model"
    assert conclusion.evidence_snapshot["curve_summary"]["median"] == 0.3
    assert "surprisal" not in conclusion.evidence_snapshot
    assert "verdict_rule" not in conclusion.evidence_snapshot["decisions"]
    assert "X increases Y" in captured["prompt"]
    assert captured["kwargs"]["temperature"] == 0.0
    assert run_obj.artifact_path("conclusion").exists()
    assert run_obj.status()["conclusion"] == "complete"
