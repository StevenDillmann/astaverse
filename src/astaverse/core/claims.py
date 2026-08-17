"""Claims, and the runs that attempt them.

A **claim** is a hypothesis about a dataset. A **run** is one attempt at it,
under one configuration. The distinction matters because the scientifically
interesting question is rarely "what did this run say" — it is "do my attempts
agree, and if not, which choice made them differ".

Grouping is derived rather than stored, from the hypothesis text and the
resolved dataset path, so it applies retroactively to runs created before this
existed and needs no migration. Two runs of the same claim are attempts; two
runs of different claims are different science.

Comparison across attempts surfaces three things a single run cannot:

* **Decision coverage** — which forks each attempt found, and which only one
  of them found. This is how you tell that `schema_lint` sees a fork
  `plan_diff` is structurally blind to.
* **Robustness agreement** — whether the attempts reach the same verdict about
  fragility. Disagreement indicts the method, not the data.
* **What it cost** — coverage of the grid, so an attempt that ran 24 of 216
  universes is never compared as an equal to one that ran all of them.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .store import STAGES, Run


def normalize_hypothesis(text: str) -> str:
    """Whitespace and case are not scientific differences."""
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def claim_id(hypothesis: str, dataset: str) -> str:
    """Stable id for a hypothesis-and-dataset pair.

    Derived, not stored, so existing runs group correctly without migration.
    """
    basis = f"{normalize_hypothesis(hypothesis)}||{str(dataset).strip().rstrip('/')}"
    return hashlib.sha1(basis.encode()).hexdigest()[:12]


@dataclass
class Attempt:
    """One run, summarised for comparison against its siblings."""

    id: str
    created_at: str
    status: dict[str, str]
    n_complete: int
    running: bool

    # What was different about this attempt.
    mode: str | None = None
    models: list[str] = field(default_factory=list)
    critique: bool = False
    cap: int | None = None
    seeded: str | None = None
    agent_models: list[str] = field(default_factory=list)

    # What it found.
    n_plans: int | None = None
    decisions: list[str] = field(default_factory=list)
    n_universes: int | None = None
    n_grid: int | None = None
    verdicts: dict[str, int] = field(default_factory=dict)
    joint_surprisal: float | None = None
    fragility: float | None = None
    top_flip: str | None = None
    top_flip_rate: float | None = None

    @property
    def coverage(self) -> float | None:
        if not self.n_grid or self.n_universes is None:
            return None
        return self.n_universes / self.n_grid

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["coverage"] = self.coverage
        return d


@dataclass
class Claim:
    id: str
    hypothesis: str
    dataset: str
    attempts: list[Attempt]

    @property
    def dataset_name(self) -> str:
        return Path(self.dataset).name

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "hypothesis": self.hypothesis,
            "dataset": self.dataset,
            "dataset_name": self.dataset_name,
            "n_attempts": len(self.attempts),
            "attempts": [a.to_dict() for a in self.attempts],
            **comparison(self.attempts),
        }


def _read(analysis: Run, stage: str) -> Any:
    path = analysis.artifact_path(stage)
    if not path.exists():
        return None
    try:
        if path.suffix == ".yaml":
            import yaml

            return yaml.safe_load(path.read_text())
        return json.loads(path.read_text())
    except Exception:  # noqa: BLE001 - a malformed artifact must not hide the run
        return None


def summarise(analysis: Run) -> Attempt:
    """Pull the comparable facts out of one run's artifacts."""
    from . import runner

    manifest = analysis.manifest()
    status = analysis.status()
    config = manifest.get("config") or {}
    decisions_cfg = config.get("decisions") or {}
    seed = manifest.get("seed") or {}

    attempt = Attempt(
        id=analysis.run_id,
        created_at=manifest.get("created_at", ""),
        status=status,
        n_complete=sum(1 for v in status.values() if v == "complete"),
        running=runner.is_running(analysis.run_id),
        mode=decisions_cfg.get("mode"),
        models=list(decisions_cfg.get("models") or []),
        critique=bool(decisions_cfg.get("critique")),
        cap=(config.get("universes") or {}).get("cap"),
        seeded=seed.get("normalized_id") or None,
        agent_models=list((config.get("execute") or {}).get("models") or []),
    )

    plans = _read(analysis, "plans")
    if plans:
        attempt.n_plans = len(plans.get("plans") or [])

    spec = _read(analysis, "decisions")
    if spec:
        attempt.decisions = sorted(spec.get("decisions") or {})

    universes = _read(analysis, "universes")
    if universes:
        attempt.n_universes = len(universes.get("universes") or [])
        attempt.n_grid = universes.get("n_total_grid")

    verdicts = _read(analysis, "verdicts")
    if verdicts:
        counts: dict[str, int] = {}
        for r in verdicts.get("results") or []:
            counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
        attempt.verdicts = counts
        flips = verdicts.get("decision_flips") or []
        if flips:
            attempt.top_flip = flips[0]["decision_id"]
            attempt.top_flip_rate = flips[0]["flip_rate"]

    surprisal = _read(analysis, "surprisal")
    if surprisal:
        attempt.joint_surprisal = surprisal.get("joint_surprisal")
        attempt.fragility = surprisal.get("fragility_index")

    return attempt


def comparison(attempts: list[Attempt]) -> dict[str, Any]:
    """What differs across attempts at the same claim.

    Reports decisions found by every attempt versus by only some. The second
    set is the interesting one: a fork only one strategy sees is either a
    false positive or a blind spot in the others, and either way it is what
    you want to look at first.
    """
    scored = [a for a in attempts if a.decisions]
    if not scored:
        return {
            "shared_decisions": [],
            "unique_decisions": {},
            "agreement": None,
            "fragility_range": None,
        }

    sets = [set(a.decisions) for a in scored]
    shared = set.intersection(*sets) if sets else set()
    everything = set.union(*sets) if sets else set()

    unique: dict[str, list[str]] = {}
    for decision in sorted(everything - shared):
        finders = [a.id for a in scored if decision in a.decisions]
        unique[decision] = finders

    fragilities = [a.fragility for a in attempts if a.fragility is not None]
    fragility_range = (
        {"min": min(fragilities), "max": max(fragilities), "n": len(fragilities)}
        if fragilities
        else None
    )

    # Do the attempts that got far enough agree on whether the claim is fragile?
    agreement: str | None = None
    if len(fragilities) > 1:
        fragile = [f > 0.1 for f in fragilities]
        agreement = "agree" if len(set(fragile)) == 1 else "disagree"

    return {
        "shared_decisions": sorted(shared),
        "unique_decisions": unique,
        "agreement": agreement,
        "fragility_range": fragility_range,
    }


def all_claims(runs_dir: Path) -> list[Claim]:
    """Every claim, newest attempt first, with its attempts newest first."""
    grouped: dict[str, Claim] = {}
    for analysis in Run.list_all(runs_dir):
        manifest = analysis.manifest()
        hypothesis = manifest.get("hypothesis") or ""
        dataset = manifest.get("dataset") or ""
        cid = claim_id(hypothesis, dataset)
        claim = grouped.get(cid)
        if claim is None:
            claim = Claim(id=cid, hypothesis=hypothesis, dataset=dataset, attempts=[])
            grouped[cid] = claim
        claim.attempts.append(summarise(analysis))

    for claim in grouped.values():
        claim.attempts.sort(key=lambda a: a.created_at, reverse=True)
    return sorted(
        grouped.values(),
        key=lambda c: c.attempts[0].created_at if c.attempts else "",
        reverse=True,
    )


def get_claim(runs_dir: Path, cid: str) -> Claim | None:
    for claim in all_claims(runs_dir):
        if claim.id == cid:
            return claim
    return None


def stages_done(attempt: Attempt) -> str:
    return f"{attempt.n_complete}/{len(STAGES)}"
