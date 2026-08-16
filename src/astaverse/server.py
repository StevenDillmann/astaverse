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

from . import config as run_config
from . import datasets, plans_index, runner
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
    # When the hypothesis came from an AutoDiscovery record, carry the plan
    # with it: the multiverse should describe the plan under evaluation, not
    # one invented from scratch.
    seed_dataset: str | None = None
    seed_normalized_id: str | None = None


class StageRequest(BaseModel):
    """Optional config patch applied before the stage runs."""

    config: dict[str, Any] | None = None


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
        if request.seed_dataset and request.seed_normalized_id:
            record = plans_index.get(request.seed_dataset, request.seed_normalized_id)
            if record is None:
                raise ValueError(
                    f"no plan record '{request.seed_normalized_id}' in {request.seed_dataset}"
                )
            manifest = run_obj.manifest()
            manifest["seed"] = {
                "normalized_id": record.normalized_id,
                "dataset": record.dataset,
                "source_path": record.source_path,
            }
            run_obj.write_manifest(manifest)
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


@app.get("/api/datasets")
def list_datasets() -> list[dict[str, Any]]:
    """Datasets available to start a study from, with AutoDiscovery plan counts."""
    out = []
    for d in datasets.discover():
        entry = d.to_dict()
        entry["n_autodiscovery_hypotheses"] = plans_index.count_for_dataset(d.name)
        out.append(entry)
    return out


@app.get("/api/datasets/{name}/hypotheses")
def list_hypotheses(name: str, q: str = "", limit: int = 300) -> dict[str, Any]:
    """AutoDiscovery's own hypotheses for a dataset.

    A BLADE dataset has one published research question; AutoDiscovery has
    generated hundreds against the same data, each with the plan it produced.
    """
    records = plans_index.for_dataset(name)
    if q:
        needle = q.lower()
        records = [r for r in records if needle in r.hypothesis.lower()]
    return {
        "dataset": name,
        "total": plans_index.count_for_dataset(name),
        "matched": len(records),
        "hypotheses": [r.to_dict() for r in records[:limit]],
    }


# Files worth surfacing in the browser. Everything else in a run directory is
# either an artifact already rendered by its stage, or container plumbing.
BROWSABLE_SUFFIXES = {".json", ".yaml", ".yml", ".md", ".py", ".txt", ".jsonl", ".toml", ".log", ".sh"}
MAX_FILE_BYTES = 2_000_000


@app.get("/api/runs/{run_id}/files")
def list_files(run_id: str) -> list[dict[str, Any]]:
    """Every readable file in the run, including agent output and history.

    This is the "go back and investigate" surface: superseded artifacts live
    under history/, and what the agent actually wrote lives under jobs/.
    """
    run_obj = _run(run_id)
    out: list[dict[str, Any]] = []
    for path in sorted(run_obj.root.rglob("*")):
        if not path.is_file() or path.suffix not in BROWSABLE_SUFFIXES:
            continue
        rel = path.relative_to(run_obj.root)
        parts = rel.parts
        if parts[0] == "history":
            category = "history"
        elif parts[0] == "jobs":
            category = "agent output" if "artifacts" in parts else "job"
        elif parts[0] == "harbor_task":
            category = "task"
        elif parts[0] == "universes":
            category = "universes"
        else:
            category = "artifact"
        stat = path.stat()
        out.append(
            {
                "path": str(rel),
                "name": path.name,
                "category": category,
                "bytes": stat.st_size,
                "modified": stat.st_mtime,
            }
        )
    return out


@app.get("/api/runs/{run_id}/file")
def read_file(run_id: str, path: str) -> dict[str, Any]:
    run_obj = _run(run_id)
    target = (run_obj.root / path).resolve()
    # Refuse anything outside the run directory: `path` is client-supplied.
    if not str(target).startswith(str(run_obj.root)) or not target.is_file():
        raise HTTPException(404, f"no such file in run: {path}")
    if target.suffix not in BROWSABLE_SUFFIXES:
        raise HTTPException(415, f"not a readable text file: {path}")
    size = target.stat().st_size
    if size > MAX_FILE_BYTES:
        raise HTTPException(413, f"file is {size} bytes, too large to display")
    return {
        "path": path,
        "bytes": size,
        "content": target.read_text(errors="replace"),
    }


@app.get("/api/runs/{run_id}/history")
def get_history(run_id: str) -> list[dict[str, Any]]:
    """Artifact sets superseded by re-running an earlier stage, newest first."""
    return _run(run_id).history()


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
    """Run one stage, using the run's saved configuration.

    Any knobs in the body are merged into that config first, so running a
    stage from the UI and running it as part of "run all" cannot diverge.
    """
    if stage not in STAGES:
        raise HTTPException(404, f"unknown stage '{stage}'")
    run_obj = _run(run_id)

    if runner.is_running(run_id):
        raise HTTPException(409, detail={"error": "a sequential run is already in progress"})

    # Refuse a stage whose inputs are not ready. A disabled button in the UI is
    # not a guard — the client can be stale, and `execute` in particular spends
    # real money on an agent run.
    status = run_obj.status()
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

    if request is not None and request.config:
        run_config.update(run_obj, request.config)

    try:
        runner.run_stage(run_obj, stage)
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


@app.get("/api/runs/{run_id}/config")
def get_config(run_id: str) -> dict[str, Any]:
    return run_config.load(_run(run_id)).model_dump()


@app.put("/api/runs/{run_id}/config")
def put_config(run_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    """Merge a partial config. Sections are merged, not replaced wholesale."""
    run_obj = _run(run_id)
    try:
        return run_config.update(run_obj, patch).model_dump()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/runs/{run_id}/run-all")
def run_all(run_id: str, through: str | None = None, force: bool = False) -> dict[str, Any]:
    """Run every stage up to the configured target, in the background.

    Returns immediately; poll /progress. An agent sweep takes many minutes,
    which is far too long to hold a request open.
    """
    run_obj = _run(run_id)
    try:
        return runner.start_sequence(run_obj, through=through, force=force)
    except RuntimeError as exc:
        raise HTTPException(409, detail={"error": str(exc)}) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/api/runs/{run_id}/progress")
def get_progress(run_id: str) -> dict[str, Any]:
    _run(run_id)
    return runner.progress_for(run_id) or {"running": False, "finished": True}


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


@app.get("/api/extraction-modes")
def list_extraction_modes() -> list[dict[str, Any]]:
    """Stage-3 strategies, with what each is blind to.

    Surfaced so the choice is made knowingly: these modes fail differently,
    and picking one is a methodological decision, not a preference.
    """
    from .stages.s3_decisions import ExtractionMode

    blurbs = {
        ExtractionMode.plan_diff: (
            "Where K sampled plans disagree. Grounded in what analysts do; "
            "blind to steps no plan mentions at all."
        ),
        ExtractionMode.plan_audit: (
            "One plan, audited for what it leaves an implementer to decide. "
            "Targets under-specification by silence; no disagreement signal."
        ),
        ExtractionMode.direct: (
            "Hypothesis and schema only, no plans. Cheapest; tends toward "
            "textbook axes rather than ones this study would hit."
        ),
        ExtractionMode.schema_lint: (
            "What the data itself forces — orientation, scale, missingness. "
            "Catches forks that appear in code but never in plan text."
        ),
        ExtractionMode.union: (
            "Several modes merged. The blind spots differ, so the union "
            "covers more than any single mode; costs one call per mode."
        ),
    }
    needs_plans = {ExtractionMode.plan_diff, ExtractionMode.plan_audit}
    return [
        {
            "id": m.value,
            "description": blurbs[m],
            "needs_plans": m in needs_plans,
        }
        for m in ExtractionMode
    ]
