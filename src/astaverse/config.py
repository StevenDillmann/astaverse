"""Per-run configuration — the human decisions, made once.

Every knob that changes what a stage does lives here, stored in the run's
manifest so it survives restarts and is shared by the CLI, the API, and the
sequential runner. Running a stage on its own and running it as part of
"run all" therefore use identical settings; there is no second set of
defaults hiding in the UI.

The config is deliberately a record of intent. It is written before anything
runs, so a finished run carries the choices that produced it.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from .store import STAGES, Run


class PlansConfig(BaseModel):
    k: int = 5
    model: str | None = None
    temperature: float = 0.9


class DecisionsConfig(BaseModel):
    #: plan_diff | plan_audit | direct | schema_lint | union
    mode: str = "plan_diff"
    #: More than one unions across models — a direct check on one model's blind spots.
    models: list[str] = Field(default_factory=list)
    critique: bool = False
    union_modes: list[str] = Field(default_factory=list)
    max_decisions: int = 6


class UniversesConfig(BaseModel):
    cap: int = 24
    include: list[str] = Field(default_factory=list)
    exclude: list[str] = Field(default_factory=list)


class ExecuteConfig(BaseModel):
    agent: str = "terminus-2"
    #: More than one estimates implementation bias (bias control 3).
    models: list[str] = Field(default_factory=list)
    dry_run: bool = False


class SurprisalConfig(BaseModel):
    model: str | None = None
    n_samples: int = 5


class RunConfig(BaseModel):
    plans: PlansConfig = Field(default_factory=PlansConfig)
    decisions: DecisionsConfig = Field(default_factory=DecisionsConfig)
    universes: UniversesConfig = Field(default_factory=UniversesConfig)
    execute: ExecuteConfig = Field(default_factory=ExecuteConfig)
    surprisal: SurprisalConfig = Field(default_factory=SurprisalConfig)

    #: How far "run all" goes. Defaults to stopping before `execute`, which is
    #: the only stage that spends money on an agent — opting into that should
    #: be deliberate.
    through: str = "universes"

    def stages_through(self) -> list[str]:
        if self.through not in STAGES:
            raise ValueError(f"unknown stage '{self.through}'")
        return STAGES[: STAGES.index(self.through) + 1]


def load(run_obj: Run) -> RunConfig:
    return RunConfig.model_validate(run_obj.manifest().get("config") or {})


def save(run_obj: Run, config: RunConfig) -> RunConfig:
    manifest = run_obj.manifest()
    manifest["config"] = config.model_dump()
    run_obj.write_manifest(manifest)
    return config


def update(run_obj: Run, patch: dict[str, Any]) -> RunConfig:
    """Merge a partial config, one section at a time."""
    current = load(run_obj).model_dump()
    for section, values in patch.items():
        if isinstance(values, dict) and isinstance(current.get(section), dict):
            current[section].update(values)
        else:
            current[section] = values
    return save(run_obj, RunConfig.model_validate(current))
