"""Per-analysis configuration — the one place a knob is defined.

This module is the single source of truth for everything a human decides
about how an analysis runs. Three surfaces are generated from it rather than
written by hand:

* the CLI, via tyro — every field becomes a flag, and `description` becomes
  its help text;
* the UI form, via `model_json_schema()` — the same descriptions become field
  labels and hints;
* the stored record, in the analysis manifest, so a finished analysis carries
  the choices that produced it.

Adding a knob therefore means adding a field here, and nothing else. The
previous design hand-wrote each flag in the CLI, again in the API request
model, and again as UI widgets, with tests to check the three agreed.

Write `description` for every field as though it were the only documentation,
because for the CLI and the UI it is.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from .store import STAGES, Run

Stage = Literal[
    "study", "plans", "decisions", "universes", "task", "verdicts", "execute", "surprisal"
]

ExtractionMode = Literal["plan_diff", "plan_audit", "direct", "schema_lint", "union"]


class PlansConfig(BaseModel):
    """Stage 2 — sampling candidate analysis plans."""

    k: int = Field(
        5,
        ge=1,
        le=20,
        description="How many independent plans to sample. Where they disagree is what stage 3 extracts.",
    )
    model: str | None = Field(
        None,
        description="Model for plan generation. Defaults to ASTAVERSE_PLAN_MODEL.",
    )
    temperature: float = Field(
        0.9,
        ge=0.0,
        le=2.0,
        description="Sampling temperature. Ignored by models that pin it, such as the gpt-5 family.",
    )


class DecisionsConfig(BaseModel):
    """Stage 3 — finding the analytic forks."""

    mode: ExtractionMode = Field(
        "plan_diff",
        description=(
            "Extraction strategy. plan_diff: where sampled plans disagree, blind to "
            "steps no plan mentions. plan_audit: one plan, audited for what it leaves "
            "unsaid. direct: hypothesis and schema only. schema_lint: what the data "
            "itself forces, such as a variable that runs opposite to its peers. "
            "union: several merged, since their blind spots differ."
        ),
    )
    models: list[str] = Field(
        default_factory=list,
        description="Models to extract with. More than one unions the results, covering one model's blind spots.",
    )
    critique: bool = Field(
        False,
        description="Add a second pass that asks what the extraction missed.",
    )
    union_modes: list[str] = Field(
        default_factory=list,
        description="With mode=union, which strategies to combine. Empty means a sensible default set.",
    )
    max_decisions: int = Field(
        6,
        ge=1,
        le=20,
        description="Cap on extracted decisions. Each one multiplies the grid.",
    )


class UniversesConfig(BaseModel):
    """Stage 4 — enumerating the grid."""

    cap: int = Field(
        24,
        ge=1,
        le=512,
        description=(
            "Most universes to execute. Beyond this the grid is sampled by an even "
            "stride, never truncated to a prefix, and the drop count is reported."
        ),
    )
    include: list[str] = Field(
        default_factory=list,
        description="Only vary these decisions. Empty means all of them.",
    )
    exclude: list[str] = Field(
        default_factory=list,
        description="Hold these decisions at their default instead of varying them.",
    )


class ExecuteConfig(BaseModel):
    """Stage 6 — running the sweep. The only stage that costs money."""

    agent: str = Field("terminus-2", description="Harbor agent to run the task.")
    models: list[str] = Field(
        default_factory=list,
        description=(
            "Models to run the sweep with. More than one estimates implementation "
            "bias: agreement between them is what licenses reading the multiverse as "
            "a statement about the analysis rather than about the agent."
        ),
    )
    dry_run: bool = Field(
        False, description="Print the harbor command without running anything."
    )


class SurprisalConfig(BaseModel):
    """Stage 8 — belief update and fragility."""

    model: str | None = Field(
        None, description="Model for belief elicitation. Defaults to ASTAVERSE_BELIEF_MODEL."
    )
    n_samples: int = Field(
        5,
        ge=1,
        le=50,
        description="Categorical draws per elicitation. More is steadier and costs more.",
    )


class RunConfig(BaseModel):
    """Everything a human decides about how one analysis runs."""

    plans: PlansConfig = Field(default_factory=PlansConfig)
    decisions: DecisionsConfig = Field(default_factory=DecisionsConfig)
    universes: UniversesConfig = Field(default_factory=UniversesConfig)
    execute: ExecuteConfig = Field(default_factory=ExecuteConfig)
    surprisal: SurprisalConfig = Field(default_factory=SurprisalConfig)

    through: Stage = Field(
        "universes",
        description=(
            "How far `run` goes. Defaults to stopping before execute, the only stage "
            "that launches a billable agent, so spending money is always deliberate."
        ),
    )

    def stages_through(self) -> list[str]:
        if self.through not in STAGES:
            raise ValueError(f"unknown stage '{self.through}'")
        return STAGES[: STAGES.index(self.through) + 1]

    def spends_money(self) -> bool:
        return "execute" in self.stages_through()


def load(analysis: Run) -> RunConfig:
    return RunConfig.model_validate(analysis.manifest().get("config") or {})


def save(analysis: Run, config: RunConfig) -> RunConfig:
    manifest = analysis.manifest()
    manifest["config"] = config.model_dump()
    analysis.write_manifest(manifest)
    return config


def update(analysis: Run, patch: dict[str, Any]) -> RunConfig:
    """Merge a partial config, section by section."""
    current = load(analysis).model_dump()
    for section, values in patch.items():
        if isinstance(values, dict) and isinstance(current.get(section), dict):
            current[section].update(values)
        else:
            current[section] = values
    return save(analysis, RunConfig.model_validate(current))


def json_schema() -> dict[str, Any]:
    """The schema the UI renders its form from — the same one tyro reads."""
    return RunConfig.model_json_schema()
