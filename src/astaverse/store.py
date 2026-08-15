"""Run directories and stage artifacts.

A run is a directory. A stage is a pure function that reads the previous
artifact and writes its own. Nothing else is shared, so any stage can be
re-run from disk, and the CLI and the API can call the identical function.

Re-running a stage invalidates everything downstream rather than leaving
stale artifacts sitting next to fresh ones.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel

# Ordered: index in this list defines what "downstream" means.
STAGES: list[str] = [
    "study",
    "plans",
    "decisions",
    "universes",
    "task",
    "execute",
    "verdicts",
    "surprisal",
]

ARTIFACTS: dict[str, str] = {
    "study": "01_study.json",
    "plans": "02_plans.json",
    "decisions": "03_astra.yaml",
    "universes": "04_universes.json",
    "task": "05_task.json",
    "execute": "06_execute.json",
    "verdicts": "07_verdicts.json",
    "surprisal": "08_surprisal.json",
}


def _slug(text: str, max_len: int = 40) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:max_len].strip("-") or "run"


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Run:
    """Handle on one run directory."""

    def __init__(self, root: Path):
        self.root = Path(root)

    # -- lifecycle ---------------------------------------------------------

    @classmethod
    def create(cls, runs_dir: Path, hypothesis: str, dataset: str) -> "Run":
        runs_dir = Path(runs_dir)
        runs_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        run_id = f"{stamp}__{_slug(hypothesis)}"
        root = runs_dir / run_id
        root.mkdir(parents=True, exist_ok=False)
        run = cls(root)
        run.write_manifest(
            {
                "run_id": run_id,
                "created_at": utcnow(),
                "hypothesis": hypothesis,
                "dataset": str(dataset),
                "stages": {},
            }
        )
        return run

    @classmethod
    def load(cls, runs_dir: Path, run_id: str) -> "Run":
        root = Path(runs_dir) / run_id
        if not root.is_dir():
            raise FileNotFoundError(f"no such run: {run_id} (looked in {runs_dir})")
        return cls(root)

    @classmethod
    def list_all(cls, runs_dir: Path) -> list["Run"]:
        runs_dir = Path(runs_dir)
        if not runs_dir.is_dir():
            return []
        return [cls(p) for p in sorted(runs_dir.iterdir(), reverse=True) if (p / "manifest.json").exists()]

    @property
    def run_id(self) -> str:
        return self.root.name

    # -- manifest ----------------------------------------------------------

    @property
    def manifest_path(self) -> Path:
        return self.root / "manifest.json"

    def manifest(self) -> dict[str, Any]:
        return json.loads(self.manifest_path.read_text())

    def write_manifest(self, data: dict[str, Any]) -> None:
        self.manifest_path.write_text(json.dumps(data, indent=2) + "\n")

    def record_stage(self, stage: str, **extra: Any) -> None:
        """Mark a stage complete and invalidate everything after it."""
        m = self.manifest()
        m.setdefault("stages", {})[stage] = {"completed_at": utcnow(), **extra}
        for downstream in STAGES[STAGES.index(stage) + 1 :]:
            m["stages"].pop(downstream, None)
            path = self.artifact_path(downstream)
            if path.exists():
                path.rename(path.with_suffix(path.suffix + ".stale"))
        self.write_manifest(m)

    def status(self) -> dict[str, str]:
        done = self.manifest().get("stages", {})
        out: dict[str, str] = {}
        blocked = False
        for stage in STAGES:
            if stage in done:
                out[stage] = "complete"
            elif not blocked:
                out[stage] = "ready"
                blocked = True
            else:
                out[stage] = "pending"
        return out

    # -- artifacts ---------------------------------------------------------

    def artifact_path(self, stage: str) -> Path:
        return self.root / ARTIFACTS[stage]

    def write_artifact(self, stage: str, model: BaseModel) -> Path:
        path = self.artifact_path(stage)
        path.write_text(model.model_dump_json(indent=2) + "\n")
        return path

    def read_artifact(self, stage: str, model_cls: type[BaseModel]) -> Any:
        path = self.artifact_path(stage)
        if not path.exists():
            raise FileNotFoundError(
                f"stage '{stage}' has not run for {self.run_id} (expected {path.name})"
            )
        return model_cls.model_validate_json(path.read_text())

    def require(self, stage: str) -> None:
        if not self.artifact_path(stage).exists():
            raise FileNotFoundError(
                f"run '{self.run_id}' needs stage '{stage}' first: astaverse {stage} {self.run_id}"
            )

    # -- subdirectories ----------------------------------------------------

    @property
    def universes_dir(self) -> Path:
        return self.root / "universes"

    @property
    def task_dir(self) -> Path:
        return self.root / "harbor_task"

    @property
    def jobs_dir(self) -> Path:
        return self.root / "jobs"

    def log(self, stage: str, message: str) -> None:
        line = f"[{utcnow()}] {stage}: {message}\n"
        with (self.root / "run.log").open("a") as fh:
            fh.write(line)
