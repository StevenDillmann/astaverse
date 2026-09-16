"""Mutations: everything that changes state.

Kept apart from the read models because they have different risks. A read is
cheap and idempotent; an action can spend money, overwrite configuration, or
supersede artifacts, and each of those needs a guard rather than a shape.
"""

from __future__ import annotations

import json
import shutil
import traceback
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from ...core import claims as claims_core
from ...core import config as run_cfg
from ...core import runner
from ...core import settings as app_settings
from ...core.stages import s1_study, s2_plans
from ...core.store import STAGES, Run, utcnow
from ...integrations import datasets, hypotheses, plans_index
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
    review_before_execute: bool | None = None


class NewAttempt(BaseModel):
    """Another attempt at an existing claim, under a different configuration."""

    config: dict[str, Any] | None = None
    review_before_execute: bool | None = None


def _parse_column_descriptions(raw: str | None) -> dict[str, str]:
    if not raw or not raw.strip():
        return {}
    parsed = json.loads(raw)
    if isinstance(parsed, list):
        out: dict[str, str] = {}
        for item in parsed:
            if not isinstance(item, dict):
                raise TypeError("column_descriptions entries must be objects")
            name = str(item.get("name") or item.get("column") or "").strip()
            if not name:
                continue
            out[name] = str(item.get("description") or "")
        return out
    if isinstance(parsed, dict):
        return {str(key): str(value) for key, value in parsed.items()}
    raise ValueError("column_descriptions must be a JSON object or array")


async def _read_upload(file: UploadFile) -> bytes:
    if not file.filename:
        raise ValueError("a CSV file is required")
    if not file.filename.lower().endswith(".csv"):
        raise ValueError("only CSV files are supported")
    content = await file.read()
    await file.close()
    return content


@router.post("/datasets/preview")
async def preview_dataset(
    file: Annotated[UploadFile, File()],
    name: Annotated[str, Form()] = "",
    description: Annotated[str, Form()] = "",
    column_descriptions: Annotated[str, Form()] = "",
) -> dict[str, Any]:
    try:
        content = await _read_upload(file)
        resolved_name = name.strip() or Path(file.filename or "dataset").stem
        descriptions = _parse_column_descriptions(column_descriptions)
        return datasets.preview_upload(
            content,
            name=resolved_name,
            description=description.strip() or None,
            column_descriptions=descriptions or None,
        )
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/datasets")
async def create_dataset(
    file: Annotated[UploadFile, File()],
    name: Annotated[str, Form()],
    description: Annotated[str, Form()] = "",
    column_descriptions: Annotated[str, Form()] = "",
) -> dict[str, Any]:
    try:
        content = await _read_upload(file)
        if not name.strip():
            raise ValueError("dataset name is required")
        descriptions = _parse_column_descriptions(column_descriptions)
        created = datasets.import_upload(
            content,
            name=name.strip(),
            description=description.strip() or None,
            column_descriptions=descriptions or None,
        )
        entry = created.to_dict(include_fields=True)
        entry["n_autodiscovery_hypotheses"] = plans_index.count_for_dataset(created.name)
        return entry
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/claims")
@router.post("/hypotheses")
def create_claim(request: NewClaim) -> dict[str, Any]:
    try:
        selected = datasets.get(request.dataset)
        dataset_path = selected.path if selected else str(Path(request.dataset).expanduser())
        if not Path(dataset_path).exists():
            raise ValueError(f"no such dataset: {request.dataset}")
        hypothesis_id = claims_core.claim_id(request.hypothesis, dataset_path)
        record = hypotheses.save(
            hypothesis_id,
            request.hypothesis,
            dataset_path,
            request.description,
        )
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc

    return {
        **record.to_dict(),
        "dataset_name": Path(record.dataset).name,
        "n_attempts": 0,
    }


@router.post("/claims/{claim_id}/attempts")
@router.post("/hypotheses/{claim_id}/experiments")
def create_attempt(claim_id: str, request: NewAttempt | None = None) -> dict[str, Any]:
    """Start another attempt, inheriting configuration but generating a fresh plan.

    Inheriting matters: a comparison is only readable if the attempts differ
    in what you deliberately changed, rather than in every knob that happened
    to default differently. A seed plan is not configuration: carrying it over
    would silently reuse the previous AutoDiscovery plan.
    """
    claim = claims_core.get_claim(runs_dir(), claim_id)
    if claim is None:
        raise HTTPException(404, f"no such claim: {claim_id}")

    try:
        analysis = Run.create(runs_dir(), claim.hypothesis, claim.dataset)
        if claim.attempts:
            previous = get_analysis(claim.attempts[0].id)
            run_cfg.save(analysis, run_cfg.load(previous))
        else:
            app_settings.apply_to_manifest(analysis, app_settings.load(runs_dir()))
        if request and request.config:
            run_cfg.update(analysis, request.config)
        if request and request.review_before_execute is not None:
            manifest = analysis.manifest()
            manifest["review_before_execute"] = request.review_before_execute
            analysis.write_manifest(manifest)
        s1_study.run(analysis, claim.hypothesis, claim.dataset)
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc

    return {"run_id": analysis.run_id, "claim_id": claim_id}


@router.delete("/datasets/{name}")
def delete_dataset(name: str) -> dict[str, Any]:
    dependents = [
        claim.id
        for claim in claims_core.all_claims(runs_dir())
        if claim.dataset_name == name
    ]
    if dependents:
        raise HTTPException(
            409,
            f"delete the dataset's {len(dependents)} hypothesis"
            f"{'es' if len(dependents) != 1 else ''} first",
        )
    try:
        if not datasets.delete(name):
            raise HTTPException(404, f"no such dataset: {name}")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"deleted": name}


@router.delete("/claims/{claim_id}")
@router.delete("/hypotheses/{claim_id}")
def delete_hypothesis(claim_id: str) -> dict[str, Any]:
    claim = claims_core.get_claim(runs_dir(), claim_id)
    if claim is None:
        raise HTTPException(404, f"no such hypothesis: {claim_id}")
    if claim.attempts:
        count = len(claim.attempts)
        raise HTTPException(
            409,
            f"delete the hypothesis's {count} experiment"
            f"{'s' if count != 1 else ''} first",
        )
    if not hypotheses.delete(claim_id):
        raise HTTPException(404, f"hypothesis is not independently stored: {claim_id}")
    return {"deleted": claim_id}


@router.delete("/runs/{run_id}")
@router.delete("/experiments/{run_id}")
def delete_experiment(run_id: str) -> dict[str, Any]:
    analysis = get_analysis(run_id)
    if runner.is_running(run_id):
        raise HTTPException(409, "stop the running experiment before deleting it")
    manifest = analysis.manifest()
    hypothesis = manifest.get("hypothesis") or ""
    dataset = manifest.get("dataset") or ""
    hypothesis_id = claims_core.claim_id(hypothesis, dataset)
    hypotheses.save(hypothesis_id, hypothesis, dataset)
    shutil.rmtree(analysis.root)
    return {"deleted": run_id, "hypothesis_id": hypothesis_id}


@router.post("/archive")
def set_archived(request: dict[str, Any]) -> dict[str, Any]:
    """Archive or restore datasets, hypotheses or experiments.

    Takes `id` for one or `ids` for a batch; a batch is applied under a single
    read-modify-write so a bulk selection cannot half-apply.
    """
    raw = request.get("ids")
    ids = [str(item) for item in raw] if isinstance(raw, list) else [str(request.get("id", ""))]
    try:
        updated = app_settings.set_archived_many(
            runs_dir(),
            str(request.get("kind", "")),
            ids,
            bool(request.get("archived", True)),
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return updated.model_dump()


@router.put("/settings")
def set_settings(patch: dict[str, Any]) -> dict[str, Any]:
    try:
        return app_settings.update(runs_dir(), patch).model_dump()
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


@router.put("/runs/{run_id}/config")
@router.put("/experiments/{run_id}/config")
def set_config(run_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    """Merge a partial configuration, section by section."""
    analysis = get_analysis(run_id)
    try:
        return run_cfg.update(analysis, patch).model_dump()
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/runs/{run_id}/stages/{stage}")
@router.post("/experiments/{run_id}/stages/{stage}")
def run_stage(run_id: str, stage: str, confirm: bool = False) -> dict[str, Any]:
    if stage not in STAGES:
        raise HTTPException(404, f"unknown stage '{stage}'")
    analysis = get_analysis(run_id)

    if runner.is_running(run_id):
        raise HTTPException(409, detail={"error": "a run is already in progress"})

    # A disabled button is not a guard: the client can be stale, and execute
    # spends real money.
    status = analysis.status()
    cfg = run_cfg.load(analysis)
    required = cfg.stages_through(stage)
    missing = [s for s in required[:-1] if status.get(s) != "complete"]
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
    if stage == "execute" and not cfg.execute.dry_run and not confirm:
        raise HTTPException(
            409,
            detail={
                "stage": stage,
                "error": "execution launches billable coding agents; confirm explicitly",
                "requires_confirmation": True,
            },
        )

    try:
        runner.run_stage(analysis, stage)
    except Exception as exc:
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
@router.post("/experiments/{run_id}/run")
def run_all(
    run_id: str,
    through: str | None = None,
    force: bool = False,
    confirm: bool = False,
) -> dict[str, Any]:
    """Run every stage up to the configured target, in the background."""
    analysis = get_analysis(run_id)
    try:
        cfg = run_cfg.load(analysis)
        target = through or cfg.through
        manifest = analysis.manifest()
        if (
            manifest.get("review_before_execute", True)
            and not manifest.get("decision_reviewed_at")
            and STAGES.index(target) > STAGES.index("decisions")
        ):
            target = "decisions"
        if (
            "execute" in cfg.stages_through(target)
            and not cfg.execute.dry_run
            and not confirm
        ):
            raise HTTPException(
                409,
                detail={
                    "stage": "execute",
                    "error": "execution launches billable coding agents; confirm explicitly",
                    "requires_confirmation": True,
                },
            )
        return runner.start_sequence(analysis, through=target, force=force)
    except RuntimeError as exc:
        raise HTTPException(409, detail={"error": str(exc)}) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/experiments/{run_id}/review")
def approve_decisions(run_id: str) -> dict[str, Any]:
    """Approve the extracted decision space before universe generation."""
    analysis = get_analysis(run_id)
    if analysis.status().get("decisions") != "complete":
        raise HTTPException(409, detail={"error": "decision extraction is not complete"})
    manifest = analysis.manifest()
    manifest["decision_reviewed_at"] = utcnow()
    analysis.write_manifest(manifest)
    return {"id": run_id, "decision_reviewed_at": manifest["decision_reviewed_at"]}


@router.post("/runs/{run_id}/seed")
def set_seed(run_id: str, source_path: str, normalized_id: str = "") -> dict[str, Any]:
    analysis = get_analysis(run_id)
    try:
        text = s2_plans.load_seed_plan(jsonl=source_path, normalized_id=normalized_id or None)
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc
    if not text:
        raise HTTPException(404, f"no plan found in {source_path}")
    manifest = analysis.manifest()
    manifest["seed"] = {"source_path": source_path, "normalized_id": normalized_id}
    analysis.write_manifest(manifest)
    return manifest["seed"]
