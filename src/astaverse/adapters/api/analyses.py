"""Analyses: create, list, inspect, configure, and run."""

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
from .deps import artifact, get_analysis, runs_dir

router = APIRouter(prefix="/api/analyses", tags=["analyses"])


class NewAnalysis(BaseModel):
    hypothesis: str
    dataset: str
    description: str | None = None
    # When the hypothesis came from an AutoDiscovery record, carry its plan so
    # the decision space describes the plan under evaluation.
    seed_dataset: str | None = None
    seed_normalized_id: str | None = None


class ConfigPatch(BaseModel):
    """A partial config, merged section by section."""

    config: dict[str, Any] | None = None


@router.get("")
def list_analyses() -> list[dict[str, Any]]:
    out = []
    for analysis in Run.list_all(runs_dir()):
        manifest = analysis.manifest()
        status = analysis.status()
        out.append(
            {
                "id": analysis.run_id,
                "hypothesis": manifest.get("hypothesis"),
                "dataset": manifest.get("dataset"),
                "created_at": manifest.get("created_at"),
                "status": status,
                "n_complete": sum(1 for v in status.values() if v == "complete"),
                "running": runner.is_running(analysis.run_id),
            }
        )
    return out


@router.post("")
def create_analysis(request: NewAnalysis) -> dict[str, Any]:
    try:
        analysis = Run.create(runs_dir(), request.hypothesis, request.dataset)
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
    return {"id": analysis.run_id, "status": analysis.status()}


@router.get("/{analysis_id}")
def get_analysis_detail(analysis_id: str) -> dict[str, Any]:
    analysis = get_analysis(analysis_id)
    manifest = analysis.manifest()
    return {
        "id": analysis.run_id,
        "claim_id": claims_core.claim_id(
            manifest.get("hypothesis", ""), manifest.get("dataset", "")
        ),
        "manifest": manifest,
        "status": analysis.status(),
        "config": run_cfg.load(analysis).model_dump(),
        "artifacts": {stage: artifact(analysis, stage) for stage in STAGES},
    }


# -- configuration ---------------------------------------------------------


@router.get("/{analysis_id}/config")
def get_config(analysis_id: str) -> dict[str, Any]:
    return run_cfg.load(get_analysis(analysis_id)).model_dump()


@router.put("/{analysis_id}/config")
def put_config(analysis_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    analysis = get_analysis(analysis_id)
    try:
        return run_cfg.update(analysis, patch).model_dump()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, str(exc)) from exc


# -- running ---------------------------------------------------------------


@router.post("/{analysis_id}/stages/{stage}")
def run_stage(analysis_id: str, stage: str, patch: ConfigPatch | None = None) -> dict[str, Any]:
    """Run one stage using the analysis's saved configuration."""
    if stage not in STAGES:
        raise HTTPException(404, f"unknown stage '{stage}'")
    analysis = get_analysis(analysis_id)

    if runner.is_running(analysis_id):
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

    if patch is not None and patch.config:
        run_cfg.update(analysis, patch.config)

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

    return {
        "id": analysis.run_id,
        "stage": stage,
        "status": analysis.status(),
        "artifact": artifact(analysis, stage),
    }


@router.post("/{analysis_id}/run")
def run_all(analysis_id: str, through: str | None = None, force: bool = False) -> dict[str, Any]:
    """Run every stage up to the configured target, in the background."""
    analysis = get_analysis(analysis_id)
    try:
        return runner.start_sequence(analysis, through=through, force=force)
    except RuntimeError as exc:
        raise HTTPException(409, detail={"error": str(exc)}) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/{analysis_id}/progress")
def get_progress(analysis_id: str) -> dict[str, Any]:
    get_analysis(analysis_id)
    return runner.progress_for(analysis_id) or {"running": False, "finished": True}


@router.post("/{analysis_id}/seed")
def set_seed(analysis_id: str, source_path: str, normalized_id: str = "") -> dict[str, Any]:
    """Attach an AutoDiscovery plan to seed stage 2."""
    analysis = get_analysis(analysis_id)
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
