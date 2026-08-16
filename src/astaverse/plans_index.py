"""Index of AutoDiscovery's own hypotheses and plans.

A BLADE dataset carries exactly one published research question, but
AutoDiscovery has generated thousands of hypotheses against the same data —
4,053 across 26 datasets at the time of writing, each with the plan it
produced. Those are the objects this project exists to evaluate, so they need
to be browsable alongside the datasets.

Each record's `query` field IS the experiment plan, in AutoDiscovery's own
format. Selecting a hypothesis here therefore seeds stage 2 with the real plan
(`--seed-jsonl`), which is what makes the resulting decision space describe the
plan under evaluation rather than one invented from scratch.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path

DEFAULT_ROOTS = [
    Path.home() / "Desktop/Asta/autodiscovery-execution-experiments/data/plans/01_normalized",
]


@dataclass
class PlanRecord:
    normalized_id: str
    dataset: str
    hypothesis: str
    source_path: str
    success: bool
    has_code: bool
    query_preview: str
    # MCTS position: siblings under one parent are alternative plans for a
    # related question, which is useful context when choosing.
    level: int | None = None
    parent_idx: int | None = None
    visits: int | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def roots() -> list[Path]:
    env = os.environ.get("ASTAVERSE_PLANS")
    if env:
        return [Path(p).expanduser() for p in env.split(os.pathsep) if p]
    return DEFAULT_ROOTS


@lru_cache(maxsize=32)
def _load(path_str: str) -> tuple[PlanRecord, ...]:
    path = Path(path_str)
    out: list[PlanRecord] = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        hypothesis = (r.get("hypothesis") or "").strip()
        if not hypothesis:
            continue
        meta = r.get("metadata") or {}
        query = r.get("query") or ""
        out.append(
            PlanRecord(
                normalized_id=r.get("normalized_id", ""),
                dataset=r.get("dataset", path.stem),
                hypothesis=hypothesis,
                source_path=str(path),
                success=bool(r.get("success")),
                has_code=bool(r.get("code")),
                query_preview=query[:400],
                level=meta.get("level"),
                parent_idx=meta.get("parent_idx"),
                visits=meta.get("visits"),
            )
        )
    return tuple(out)


def datasets_with_plans() -> dict[str, Path]:
    """Dataset name -> plans jsonl, keyed by file stem (matches BLADE folders)."""
    found: dict[str, Path] = {}
    for root in roots():
        if not root.is_dir():
            continue
        for path in sorted(root.glob("*.jsonl")):
            found.setdefault(path.stem, path)
    return found


def for_dataset(name: str) -> list[PlanRecord]:
    path = datasets_with_plans().get(name)
    return list(_load(str(path))) if path else []


def count_for_dataset(name: str) -> int:
    return len(for_dataset(name))


def get(dataset: str, normalized_id: str) -> PlanRecord | None:
    for record in for_dataset(dataset):
        if record.normalized_id == normalized_id:
            return record
    return None
