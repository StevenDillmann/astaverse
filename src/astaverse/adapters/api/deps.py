"""Shared plumbing for the HTTP adapter.

The routers are thin: they resolve an analysis, call into `core`, and shape
the result. Anything that looks like a decision belongs in `core`, not here.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import yaml
from fastapi import HTTPException

from ...core.store import Run


def runs_dir() -> Path:
    return Path(os.environ.get("ASTAVERSE_RUNS", Path.cwd() / "runs"))


def get_analysis(analysis_id: str) -> Run:
    try:
        return Run.load(runs_dir(), analysis_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc


def artifact(analysis: Run, stage: str) -> Any:
    path = analysis.artifact_path(stage)
    if not path.exists():
        return None
    if path.suffix == ".yaml":
        return yaml.safe_load(path.read_text())
    return json.loads(path.read_text())
