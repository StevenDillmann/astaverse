"""FastAPI backend for the pipeline viewer.

Every endpoint calls the same stage function the CLI does — there is one
implementation of each pipeline step, not two.
"""

from __future__ import annotations

import json
import os
import traceback
from pathlib import Path
from typing import Any

import yaml
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .schemas import PlanSet, RobustSurprisal, StudySpec, UniverseSet
from .stages import (
    s1_study,
    s2_plans,
    s3_decisions,
    s4_universes,
    s5_task,
    s6_execute,
    s7_verdicts,
    s8_surprisal,
)
from .stages.s5_task import TaskArtifact
from .stages.s6_execute import ExecuteArtifact
from .stages.s7_verdicts import VerdictsArtifact
from .store import STAGES, Run

app = FastAPI(title="Astaverse", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

WEB_DIST = Path(__file__).resolve().parents[2] / "web" / "dist"


def runs_dir() -> Path:
    return Path(os.environ.get("ASTAVERSE_RUNS", Path.cwd() / "runs"))


def _run(run_id: str) -> Run:
    try:
        return Run.load(runs_dir(), run_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc


# --------------------------------------------------------------------------
# reads
# --------------------------------------------------------------------------


class NewRunRequest(BaseModel):
    hypothesis: str
    dataset: str
    description: str | None = None


class StageRequest(BaseModel):
    """Per-stage options. Unused keys are ignored by the stage that runs."""

    k: int = 5
    model: str | None = None
    temperature: float = 0.9
    max_decisions: int = 6
    cap: int = 24
    include: list[str] | None = None
    exclude: list[str] | None = None
    agent: str = "terminus-2"
    models: list[str] | None = None
    dry_run: bool = False
    n_samples: int = 5


@app.get("/api/stages")
def list_stages() -> list[str]:
    return STAGES


@app.get("/api/runs")
def list_runs() -> list[dict[str, Any]]:
    out = []
    for run_obj in Run.list_all(runs_dir()):
        manifest = run_obj.manifest()
        status = run_obj.status()
        out.append(
            {
                "run_id": run_obj.run_id,
                "hypothesis": manifest.get("hypothesis"),
                "dataset": manifest.get("dataset"),
                "created_at": manifest.get("created_at"),
                "status": status,
                "n_complete": sum(1 for v in status.values() if v == "complete"),
            }
        )
    return out


@app.post("/api/runs")
def create_run(request: NewRunRequest) -> dict[str, Any]:
    try:
        run_obj = Run.create(runs_dir(), request.hypothesis, request.dataset)
        s1_study.run(run_obj, request.hypothesis, request.dataset, request.description)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, str(exc)) from exc
    return {"run_id": run_obj.run_id, "status": run_obj.status()}


def _artifact(run_obj: Run, stage: str) -> Any:
    path = run_obj.artifact_path(stage)
    if not path.exists():
        return None
    if path.suffix == ".yaml":
        return yaml.safe_load(path.read_text())
    return json.loads(path.read_text())


@app.get("/api/runs/{run_id}")
def get_run(run_id: str) -> dict[str, Any]:
    run_obj = _run(run_id)
    return {
        "run_id": run_obj.run_id,
        "manifest": run_obj.manifest(),
        "status": run_obj.status(),
        "artifacts": {stage: _artifact(run_obj, stage) for stage in STAGES},
    }


@app.get("/api/runs/{run_id}/log")
def get_log(run_id: str) -> dict[str, str]:
    run_obj = _run(run_id)
    log_path = run_obj.root / "run.log"
    return {"log": log_path.read_text() if log_path.exists() else ""}


@app.get("/api/runs/{run_id}/mermaid")
def get_mermaid(run_id: str) -> dict[str, str]:
    """Decision space as a mermaid graph.

    Stands in for `astra viz --format mermaid` until astra-tools is adopted.
    """
    run_obj = _run(run_id)
    path = run_obj.artifact_path("decisions")
    if not path.exists():
        raise HTTPException(404, "decision spec not generated yet")
    from .astra_io import read_astra_yaml

    spec = read_astra_yaml(path)
    lines = ["graph LR"]
    for did, decision in spec.decisions.items():
        label = decision.label.replace('"', "'")
        lines.append(f'  {did}["{label}"]')
        for oid, option in decision.options.items():
            node = f"{did}__{oid}"
            opt_label = option.label.replace('"', "'")
            marker = " ✓" if oid == decision.default else ""
            lines.append(f'  {node}("{opt_label}{marker}")')
            lines.append(f"  {did} --> {node}")
    return {"mermaid": "\n".join(lines)}


# --------------------------------------------------------------------------
# writes — run a stage
# --------------------------------------------------------------------------

_MODELS = {
    "study": StudySpec,
    "plans": PlanSet,
    "universes": UniverseSet,
    "task": TaskArtifact,
    "execute": ExecuteArtifact,
    "verdicts": VerdictsArtifact,
    "surprisal": RobustSurprisal,
}


@app.post("/api/runs/{run_id}/stages/{stage}")
def run_stage(run_id: str, stage: str, request: StageRequest | None = None) -> dict[str, Any]:
    if stage not in STAGES:
        raise HTTPException(404, f"unknown stage '{stage}'")
    run_obj = _run(run_id)
    req = request or StageRequest()

    try:
        if stage == "study":
            manifest = run_obj.manifest()
            s1_study.run(run_obj, manifest["hypothesis"], manifest["dataset"])
        elif stage == "plans":
            s2_plans.run(run_obj, k=req.k, model=req.model, temperature=req.temperature)
        elif stage == "decisions":
            s3_decisions.run(run_obj, model=req.model, max_decisions=req.max_decisions)
        elif stage == "universes":
            s4_universes.run(run_obj, cap=req.cap, include=req.include, exclude=req.exclude)
        elif stage == "task":
            s5_task.run(run_obj)
        elif stage == "execute":
            s6_execute.run(run_obj, agent=req.agent, models=req.models, dry_run=req.dry_run)
        elif stage == "verdicts":
            s7_verdicts.run(run_obj)
        elif stage == "surprisal":
            s8_surprisal.run(run_obj, model=req.model, n_samples=req.n_samples)
    except Exception as exc:  # noqa: BLE001 - surface the real error to the UI
        raise HTTPException(
            500,
            detail={
                "stage": stage,
                "error": str(exc),
                "traceback": traceback.format_exc(limit=5),
            },
        ) from exc

    return {
        "run_id": run_obj.run_id,
        "stage": stage,
        "status": run_obj.status(),
        "artifact": _artifact(run_obj, stage),
    }


# --------------------------------------------------------------------------
# static SPA
# --------------------------------------------------------------------------

if WEB_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(WEB_DIST / "index.html")

else:

    @app.get("/")
    def index_missing() -> dict[str, str]:
        return {
            "message": (
                "Web UI not built. Run `npm install && npm run build` in web/, "
                "or `npm run dev` for the dev server on :5173."
            )
        }
