"""Application defaults shared by the CLI and web interface.

Defaults are copied into a new experiment's manifest. Finished experiments
therefore remain reproducible when application defaults change later.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from .config import RunConfig


class AppSettings(BaseModel):
    default_experiment: RunConfig = Field(default_factory=RunConfig)
    review_before_execute: bool = True


def path(runs_dir: Path) -> Path:
    return Path(runs_dir) / ".astaverse-settings.json"


def load(runs_dir: Path) -> AppSettings:
    settings_path = path(runs_dir)
    if not settings_path.exists():
        return AppSettings()
    return AppSettings.model_validate_json(settings_path.read_text())


def save(runs_dir: Path, settings: AppSettings) -> AppSettings:
    runs_dir = Path(runs_dir)
    runs_dir.mkdir(parents=True, exist_ok=True)
    path(runs_dir).write_text(settings.model_dump_json(indent=2) + "\n")
    return settings


def update(runs_dir: Path, patch: dict[str, Any]) -> AppSettings:
    current = load(runs_dir).model_dump()
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(current.get(key), dict):
            merged = current[key]
            for section, section_value in value.items():
                if isinstance(section_value, dict) and isinstance(merged.get(section), dict):
                    merged[section].update(section_value)
                else:
                    merged[section] = section_value
        else:
            current[key] = value
    return save(runs_dir, AppSettings.model_validate(current))


def apply_to_manifest(run_obj: Any, settings: AppSettings) -> RunConfig:
    """Snapshot defaults onto a newly created Run without importing Run here."""
    manifest = run_obj.manifest()
    config = settings.default_experiment
    manifest["config"] = config.model_dump()
    manifest["review_before_execute"] = settings.review_before_execute
    run_obj.write_manifest(manifest)
    return config
