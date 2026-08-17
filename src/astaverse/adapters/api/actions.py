"""Mutations: everything that changes state.

Kept apart from the read models because they have different risks. A read is
cheap and idempotent; an action can spend money, overwrite configuration, or
supersede artifacts, and each of those needs a guard rather than a shape.
"""

from __future__ import annotations

import traceback
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...core import claims as claims_core
from ...core import config as run_cfg
from ...core import runner
from ...core.stages import s1_study, s2_plans
from ...core.store import STAGES, Run
from ...integrations import plans_index
from .deps import get_analysis, runs_dir

router = APIRouter(prefix="/api", tags=["actions"])


class NewClaim(BaseModel):
    hypothesis: str
    dataset: str
    description: str | None = None
    #: When the hypothesis came from an AutoDiscovery record, carry its plan so
    #: the decision space describes the plan under evaluation.
    seed_dataset: str | None = None
    seed_normalized_id: str | None = None
    config: dict[str, Any] | None = None


class NewAttempt(BaseModel):
    """Another attempt at an existing claim, under a different configuration."""

    config: dict[str, Any] | None = None


@router.post("/claims")
def create_claim(request: NewClaim) -> dict[str, Any]:
    try:
        analysis = Run.create(runs_dir(), request.hypothesis, request.dataset)
        if request.config:
            run_cfg.update(analysis, request.config)
        if request.seed_dataset and request.seed_normalized_id:
            record = plans_index.get(request.seed_dataset, request.seed_normalized_id)
            if record is None:
                raise ValueError(f"no plan record '{request.seed_normalized_id}'")
            manifest = analysis.manifest()
            manifest["seed"] = {
                "normalized_id": record.normalized_id,
                "dataset": record.dataset,
                "source_path": record.source_path,
            }
            analysis.write_manifest(manifest)
        s1_study.run(analysis, request.hypothesis, request.dataset, request.description)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, str(exc)) from exc

    manifest = analysis.manifest()
    return {
        "run_id": analysis.run_id,
        "claim_id": claims_core.claim_id(manifest["hypothesis"], manifest["dataset"]),
    }


@router.post("/claims/{claim_id}/attempts")
def create_attempt(claim_id: str, request: NewAttempt | None = None) -> dict[str, Any]:
    """Start another attempt, inheriting the last one's configuration.

    Inheriting matters: a comparison is only readable if the attempts differ
    in what you deliberately changed, rather than in every knob that happened
    to default differently.
    """
    claim = claims_core.get_claim(runs_dir(), claim_id)
    if claim is None or not claim.attempts:
        raise HTTPException(404, f"no such claim: {claim_id}")

    previous = get_analysis(claim.attempts[0].id)
    previous_manifest = previous.manifest()

    try:
        analysis = Run.create(runs_dir(), claim.hypothesis, claim.dataset)
        run_cfg.save(analysis, run_cfg.load(previous))
        if request and request.config:
            run_cfg.update(analysis, request.config)
        if previous_manifest.get("seed"):
            manifest = analysis.manifest()
            manifest["seed"] = previous_manifest["seed"]
            analysis.write_manifest(manifest)
        s1_study.run(analysis, claim.hypothesis, claim.dataset)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, str(exc)) from exc

    return {"run_id": analysis.run_id, "claim_id": claim_id}


@router.put("/runs/{run_id}/config")
def set_config(run_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    """Merge a partial configuration, section by section."""
    analysis = get_analysis(run_id)
    try:
        return run_cfg.update(analysis, patch).model_dump()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, str(exc)) from exc


@router.post("/runs/{run_id}/stages/{stage}")
def run_stage(run_id: str, stage: str) -> dict[str, Any]:
    if stage not in STAGES:
        raise HTTPException(404, f"unknown stage '{stage}'")
    analysis = get_analysis(run_id)

    if runner.is_running(run_id):
        raise HTTPException(409, detail={"error": "a run is already in progress"})

    # A disabled button is not a guard: the client can be stale, and execute
    # spends real money.
    status = analysis.status()
    missing = [s for s in STAGES[: STAGES.index(stage)] if status.get(s) != "complete"]
    if missing:
        raise HTTPException(
            409,
            detail={
                "stage": stage,
                "error": (
                    f"cannot run '{stage}': {', '.join(missing)} "
                    f"{'has' if len(missing) == 1 else 'have'} not completed"
                ),
                "missing": missing,
            },
        )

    try:
        runner.run_stage(analysis, stage)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            500,
            detail={
                "stage": stage,
                "error": str(exc),
                "traceback": traceback.format_exc(limit=5),
            },
        ) from exc

    return {"id": analysis.run_id, "stage": stage, "status": analysis.status()}


@router.post("/runs/{run_id}/run")
def run_all(run_id: str, through: str | None = None, force: bool = False) -> dict[str, Any]:
    """Run every stage up to the configured target, in the background."""
    analysis = get_analysis(run_id)
    try:
        return runner.start_sequence(analysis, through=through, force=force)
    except RuntimeError as exc:
        raise HTTPException(409, detail={"error": str(exc)}) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/runs/{run_id}/seed")
def set_seed(run_id: str, source_path: str, normalized_id: str = "") -> dict[str, Any]:
    analysis = get_analysis(run_id)
    try:
        text = s2_plans.load_seed_plan(jsonl=source_path, normalized_id=normalized_id or None)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, str(exc)) from exc
    if not text:
        raise HTTPException(404, f"no plan found in {source_path}")
    manifest = analysis.manifest()
    manifest["seed"] = {"source_path": source_path, "normalized_id": normalized_id}
    analysis.write_manifest(manifest)
    return manifest["seed"]
