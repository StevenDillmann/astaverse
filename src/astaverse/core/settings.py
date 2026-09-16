"""Application defaults shared by the CLI and web interface.

Defaults are copied into a new experiment's manifest. Finished experiments
therefore remain reproducible when application defaults change later.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from .config import RunConfig


class AppSettings(BaseModel):
    default_experiment: RunConfig = Field(default_factory=RunConfig)
    review_before_execute: bool = True
    # Archived items are omitted from listings but never deleted, and remain
    # reachable by id. Kept here so the CLI and the web interface agree.
    archived_datasets: list[str] = Field(default_factory=list)
    archived_hypotheses: list[str] = Field(default_factory=list)
    archived_experiments: list[str] = Field(default_factory=list)


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


ARCHIVE_KINDS = {
    "dataset": "archived_datasets",
    "hypothesis": "archived_hypotheses",
    "experiment": "archived_experiments",
}


class Archive:
    """The archived ids, as a set per kind, with dataset names case-folded."""

    def __init__(self, settings: AppSettings) -> None:
        self.datasets = {name.strip().lower() for name in settings.archived_datasets}
        self.hypotheses = set(settings.archived_hypotheses)
        self.experiments = set(settings.archived_experiments)

    def has_dataset(self, name: str) -> bool:
        return str(name).strip().lower() in self.datasets

    def has_hypothesis(self, claim_id: str) -> bool:
        return claim_id in self.hypotheses

    def has_experiment(self, run_id: str) -> bool:
        return run_id in self.experiments

    def __bool__(self) -> bool:
        return bool(self.datasets or self.hypotheses or self.experiments)


def archive(runs_dir: Path) -> Archive:
    return Archive(load(runs_dir))


def set_archived(runs_dir: Path, kind: str, identifier: str, archived: bool) -> AppSettings:
    """Add or remove one id, reading and writing under one call.

    Callers pass a single id rather than a whole list, so two clients archiving
    different things cannot clobber each other's entry.
    """
    return set_archived_many(runs_dir, kind, [identifier], archived)


def set_archived_many(
    runs_dir: Path, kind: str, identifiers: Iterable[str], archived: bool
) -> AppSettings:
    """Archive or restore a batch under one read-modify-write.

    Clearing out a dozen runs one request at a time is both slow and racy —
    each call reloads the file, so two in flight can drop each other's entry.
    A batch is one load and one save, and stays a no-op safe operation:
    re-archiving something already archived changes nothing.
    """
    field = ARCHIVE_KINDS.get(kind)
    if field is None:
        raise ValueError(f"unknown archive kind '{kind}' (have: {', '.join(ARCHIVE_KINDS)})")
    wanted = [str(identifier).strip() for identifier in identifiers]
    if not wanted or any(not identifier for identifier in wanted):
        raise ValueError("an id is required")

    same = (
        (lambda a, b: a.strip().lower() == b.strip().lower())
        if kind == "dataset"
        else (lambda a, b: a == b)
    )
    existing: list[str] = list(getattr(load(runs_dir), field))
    remaining = [
        item for item in existing if not any(same(item, identifier) for identifier in wanted)
    ]
    if archived:
        for identifier in wanted:
            # Preserve caller order, and never list the same thing twice.
            if not any(same(identifier, kept) for kept in remaining):
                remaining.append(identifier)
    return update(runs_dir, {field: remaining})
