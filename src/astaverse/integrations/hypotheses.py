"""Persistence for hypotheses that do not have an experiment yet."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

from ..core.store import utcnow
from ..paths import REPO_ROOT

DEFAULT_ROOT = REPO_ROOT / "data" / "hypotheses"


@dataclass(frozen=True)
class StoredHypothesis:
    id: str
    hypothesis: str
    dataset: str
    description: str | None
    created_at: str

    def to_dict(self) -> dict:
        return asdict(self)


def root() -> Path:
    configured = os.environ.get("ASTAVERSE_HYPOTHESES")
    return Path(configured).expanduser() if configured else DEFAULT_ROOT


def list_all() -> list[StoredHypothesis]:
    directory = root()
    if not directory.is_dir():
        return []
    records: list[StoredHypothesis] = []
    for path in sorted(directory.glob("*.json")):
        try:
            records.append(StoredHypothesis(**json.loads(path.read_text())))
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            continue
    return records


def get(hypothesis_id: str) -> StoredHypothesis | None:
    return next((record for record in list_all() if record.id == hypothesis_id), None)


def save(
    hypothesis_id: str,
    hypothesis: str,
    dataset: str,
    description: str | None = None,
) -> StoredHypothesis:
    text = hypothesis.strip()
    if not text:
        raise ValueError("hypothesis is required")
    directory = root()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{hypothesis_id}.json"
    existing = get(hypothesis_id)
    record = StoredHypothesis(
        id=hypothesis_id,
        hypothesis=text,
        dataset=dataset,
        description=description.strip() if description and description.strip() else None,
        created_at=existing.created_at if existing else utcnow(),
    )
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(record.to_dict(), indent=2) + "\n")
    temporary.replace(path)
    return record


def delete(hypothesis_id: str) -> bool:
    path = root() / f"{hypothesis_id}.json"
    if not path.is_file():
        return False
    path.unlink()
    return True
