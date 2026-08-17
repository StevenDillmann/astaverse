"""Claims: a hypothesis about a dataset, and the runs that attempt it."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...core import claims as claims_core
from ...core import config as run_cfg
from ...core.stages import s1_study
from ...core.store import Run
from .deps import get_analysis, runs_dir

router = APIRouter(prefix="/api/claims", tags=["claims"])


class NewAttempt(BaseModel):
    """Another go at the same claim, under a different configuration.

    The hypothesis and dataset are copied from the run being repeated, so the
    new run groups under the same claim and the two are comparable.
    """

    config: dict[str, Any] | None = None


@router.get("")
def list_claims() -> list[dict[str, Any]]:
    return [c.to_dict() for c in claims_core.all_claims(runs_dir())]


@router.get("/{claim_id}")
def get_claim(claim_id: str) -> dict[str, Any]:
    claim = claims_core.get_claim(runs_dir(), claim_id)
    if claim is None:
        raise HTTPException(404, f"no such claim: {claim_id}")
    return claim.to_dict()


@router.post("/{claim_id}/attempts")
def new_attempt(claim_id: str, request: NewAttempt | None = None) -> dict[str, Any]:
    """Start another attempt at this claim.

    Inherits the most recent attempt's configuration so that a comparison
    differs only in what you deliberately change, rather than in every knob
    that happened to default differently.
    """
    claim = claims_core.get_claim(runs_dir(), claim_id)
    if claim is None:
        raise HTTPException(404, f"no such claim: {claim_id}")
    if not claim.attempts:
        raise HTTPException(400, "claim has no attempts to copy from")

    previous = get_analysis(claim.attempts[0].id)
    manifest = previous.manifest()

    try:
        analysis = Run.create(runs_dir(), claim.hypothesis, claim.dataset)
        inherited = run_cfg.load(previous)
        run_cfg.save(analysis, inherited)
        if request and request.config:
            run_cfg.update(analysis, request.config)
        if manifest.get("seed"):
            fresh = analysis.manifest()
            fresh["seed"] = manifest["seed"]
            analysis.write_manifest(fresh)
        s1_study.run(analysis, claim.hypothesis, claim.dataset)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, str(exc)) from exc

    return {"id": analysis.run_id, "claim_id": claim_id, "status": analysis.status()}
