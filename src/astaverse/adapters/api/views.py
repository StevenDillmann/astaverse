"""Read models, shaped for screens rather than for resources.

One endpoint per screen, returning everything that screen draws. The client
never joins, aggregates, or derives — anything computed happens here, in
Python, where it can be tested. The previous API was resource-shaped and the
frontend ended up joining claims against datasets to build a table, which put
untestable logic in a place that could not be checked.

    GET /api/home        the three granularities: claims, runs, datasets
    GET /api/claims/{id} one claim, its attempts, and their comparison
    GET /api/runs/{id}   one run, everything about it
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from ...core import claims as claims_core
from ...core import commands
from ...core import config as run_cfg
from ...core import runner
from ...core.store import STAGES
from ...integrations import datasets as datasets_integration
from ...integrations import plans_index
from .deps import artifact, get_analysis, runs_dir

router = APIRouter(prefix="/api", tags=["views"])


def _support_rate(attempt: claims_core.Attempt) -> float | None:
    verdict, rate = claims_core._dominant_verdict(attempt.verdicts)
    return rate if verdict else None


def _run_row(
    claim: claims_core.Claim, attempt: claims_core.Attempt, label: str
) -> dict[str, Any]:
    return {
        "id": attempt.id,
        "claim_id": claim.id,
        "hypothesis": claim.hypothesis,
        "dataset_name": claim.dataset_name,
        "config_label": label,
        "status": attempt.status,
        "n_complete": attempt.n_complete,
        "n_stages": len(STAGES),
        "running": attempt.running,
        "n_universes": attempt.n_universes,
        "coverage": attempt.coverage,
        "support_rate": _support_rate(attempt),
        "fragility": attempt.fragility,
        "joint_surprisal": attempt.joint_surprisal,
        "created_at": attempt.created_at,
    }


@router.get("/home")
def home() -> dict[str, Any]:
    """Everything the home screen draws, at all three granularities.

    One call rather than three: the levels are views of the same underlying
    work, and fetching them separately would mean the client stitching them
    back together.
    """
    claims = claims_core.all_claims(runs_dir())

    claim_rows: list[dict[str, Any]] = []
    run_rows: list[dict[str, Any]] = []

    for claim in claims:
        labels = claims_core.config_labels(claim.attempts)
        support = claims_core.support(claim.attempts)
        summary = claims_core.comparison(claim.attempts)

        claim_rows.append(
            {
                "id": claim.id,
                "hypothesis": claim.hypothesis,
                "dataset_name": claim.dataset_name,
                "n_attempts": len(claim.attempts),
                "running": any(a.running for a in claim.attempts),
                "support": support.to_dict(),
                "fragility_range": summary["fragility_range"],
                "agreement": summary["agreement"],
                "n_unique_decisions": len(summary["unique_decisions"]),
                "updated_at": max((a.created_at for a in claim.attempts), default=""),
            }
        )
        for attempt in claim.attempts:
            run_rows.append(_run_row(claim, attempt, labels[attempt.id]))

    run_rows.sort(key=lambda r: r["created_at"], reverse=True)

    # Datasets in use, joined with their profile. Datasets with no work are
    # left out: this screen is about what you have done, and the full catalogue
    # is what the new-claim screen is for.
    available = {d.name: d for d in datasets_integration.discover()}
    dataset_rows: list[dict[str, Any]] = []
    for name in sorted({c.dataset_name for c in claims}):
        on_dataset = [c for c in claims if c.dataset_name == name]
        info = available.get(name)
        dataset_rows.append(
            {
                "name": name,
                "n_rows": info.n_rows if info else None,
                "n_columns": info.n_columns if info else None,
                "research_question": (info.research_questions[0] if info and info.research_questions else None),
                "n_claims": len(on_dataset),
                "n_attempts": sum(len(c.attempts) for c in on_dataset),
                "n_fragile": sum(
                    1
                    for c in on_dataset
                    if any((a.fragility or 0) > 0.1 for a in c.attempts)
                ),
                "n_available_hypotheses": plans_index.count_for_dataset(name),
            }
        )

    return {"claims": claim_rows, "runs": run_rows, "datasets": dataset_rows}


@router.get("/overview")
def overview() -> dict[str, Any]:
    """The interface vocabulary for the same durable claim/run model."""
    data = home()
    return {
        "hypotheses": data["claims"],
        "experiments": data["runs"],
        "datasets": data["datasets"],
    }


@router.get("/claims/{claim_id}")
@router.get("/hypotheses/{claim_id}")
def claim_detail(claim_id: str) -> dict[str, Any]:
    claim = claims_core.get_claim(runs_dir(), claim_id)
    if claim is None:
        raise HTTPException(404, f"no such claim: {claim_id}")

    labels = claims_core.config_labels(claim.attempts)
    summary = claims_core.comparison(claim.attempts)
    return {
        "id": claim.id,
        "hypothesis": claim.hypothesis,
        "dataset": claim.dataset,
        "dataset_name": claim.dataset_name,
        "support": claims_core.support(claim.attempts).to_dict(),
        "attempts": [
            {**a.to_dict(), "config_label": labels[a.id], "support_rate": _support_rate(a)}
            for a in claim.attempts
        ],
        **summary,
    }


@router.get("/runs/{run_id}")
@router.get("/experiments/{run_id}")
def run_detail(run_id: str) -> dict[str, Any]:
    analysis = get_analysis(run_id)
    manifest = analysis.manifest()
    config = run_cfg.load(analysis)
    return {
        "id": analysis.run_id,
        "claim_id": claims_core.claim_id(
            manifest.get("hypothesis", ""), manifest.get("dataset", "")
        ),
        "hypothesis": manifest.get("hypothesis"),
        "dataset": manifest.get("dataset"),
        "seed": manifest.get("seed"),
        "status": analysis.status(),
        "stages": STAGES,
        "config": config.model_dump(),
        "review_before_execute": manifest.get("review_before_execute", True),
        "decision_reviewed_at": manifest.get("decision_reviewed_at"),
        "commands": commands.preview(config, run_id),
        "progress": runner.progress_for(run_id),
        "artifacts": {stage: artifact(analysis, stage) for stage in STAGES},
        "history": analysis.history(),
    }


@router.get("/runs/{run_id}/config")
def run_config(run_id: str) -> dict[str, Any]:
    """The saved configuration on its own.

    Also present inside the run detail, but worth a standalone read: scripts
    and `astaverse config --show` want it without the artifacts attached.
    """
    return run_cfg.load(get_analysis(run_id)).model_dump()


@router.get("/runs/{run_id}/progress")
def run_progress(run_id: str) -> dict[str, Any]:
    get_analysis(run_id)
    return runner.progress_for(run_id) or {"running": False, "finished": True}


@router.get("/runs")
def list_runs() -> list[dict[str, Any]]:
    """Flat list of runs — the CLI's `ls`, for anything that wants it."""
    return home()["runs"]


@router.get("/experiments")
def list_experiments() -> list[dict[str, Any]]:
    return home()["runs"]


@router.get("/hypotheses")
def list_hypotheses() -> list[dict[str, Any]]:
    return home()["claims"]
