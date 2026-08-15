"""Dataset discovery for the run-creation UI.

Scans one or more roots for usable datasets so a study can be started by
picking one, rather than by typing a path. BLADE folders carry their own
`info.json` with research questions and per-column descriptions, which is
enough to prefill a hypothesis; a bare CSV is still offered, just with less
context.
"""

from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path

# Roots to scan, in order. Override with ASTAVERSE_DATASETS (os.pathsep list).
DEFAULT_ROOTS = [
    Path.home() / "Desktop/Asta/autodiscovery-execution-experiments/data/datasets/blade",
    Path.home() / "Desktop/Asta/autodiscovery-execution-experiments/data/datasets",
]


@dataclass
class DatasetInfo:
    name: str
    path: str
    csv_path: str
    kind: str  # "blade" | "csv"
    n_columns: int
    n_rows: int | None = None
    description: str | None = None
    research_questions: list[str] = field(default_factory=list)
    columns: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def roots() -> list[Path]:
    env = os.environ.get("ASTAVERSE_DATASETS")
    if env:
        return [Path(p).expanduser() for p in env.split(os.pathsep) if p]
    return DEFAULT_ROOTS


def _count_rows(csv_path: Path, limit: int = 200_000) -> int | None:
    """Row count without loading pandas — this runs on every listing."""
    try:
        with csv_path.open(newline="") as fh:
            return max(sum(1 for _ in csv.reader(fh)) - 1, 0)
    except (OSError, csv.Error):
        return None


def _header(csv_path: Path) -> list[str]:
    try:
        with csv_path.open(newline="") as fh:
            return next(csv.reader(fh), [])
    except (OSError, csv.Error, StopIteration):
        return []


def _from_blade(folder: Path) -> DatasetInfo | None:
    info_path = folder / "info.json"
    csv_path = folder / "data.csv"
    if not (info_path.exists() and csv_path.exists()):
        return None
    try:
        info = json.loads(info_path.read_text())
    except json.JSONDecodeError:
        return None
    desc = (info.get("data_desc") or {}).get("dataset_description")
    columns = [f["column"] for f in (info.get("data_desc") or {}).get("fields") or []]
    return DatasetInfo(
        name=folder.name,
        path=str(folder),
        csv_path=str(csv_path),
        kind="blade",
        n_columns=len(columns) or len(_header(csv_path)),
        n_rows=_count_rows(csv_path),
        description=desc,
        research_questions=list(info.get("research_questions") or []),
        columns=columns or _header(csv_path),
    )


def _from_csv(csv_path: Path) -> DatasetInfo:
    header = _header(csv_path)
    return DatasetInfo(
        name=csv_path.stem,
        path=str(csv_path),
        csv_path=str(csv_path),
        kind="csv",
        n_columns=len(header),
        n_rows=_count_rows(csv_path),
        columns=header,
    )


def discover() -> list[DatasetInfo]:
    """All datasets found across the configured roots, de-duplicated by path."""
    found: dict[str, DatasetInfo] = {}
    for root in roots():
        if not root.is_dir():
            continue
        for entry in sorted(root.iterdir()):
            if entry.is_dir():
                blade = _from_blade(entry)
                if blade and blade.path not in found:
                    found[blade.path] = blade
            elif entry.suffix == ".csv" and entry.name != "data.csv":
                info = _from_csv(entry)
                if info.path not in found:
                    found[info.path] = info
    return sorted(found.values(), key=lambda d: d.name)


def get(name: str) -> DatasetInfo | None:
    for dataset in discover():
        if dataset.name == name:
            return dataset
    return None
