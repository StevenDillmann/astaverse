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

* **Decision coverage** — which forks each experiment found, and which only one
  of them found. This is how you tell that `audit_plan` sees a fork
  `sample_plans` is structurally blind to.
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

from .config import normalize_extraction_mode
from . import store as store_module
from .store import STAGES, Run


def normalize_hypothesis(text: str) -> str:
    """Whitespace and case are not scientific differences."""
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def normalize_dataset(dataset: str) -> str:
    """A dataset is identified by its folder name, however it was spelled.

    The same dataset arrives here several ways — a bare name (`caschools`), a
    repo-relative path (`data/datasets/caschools`), an absolute directory, or
    the csv inside it — because manifests, stored hypotheses, and the API each
    record it differently. Every spelling has to yield one claim, or the same
    hypothesis appears once per spelling. Safe because the canonical layout
    gives each dataset its own uniquely named folder under `data/datasets/`.
    """
    path = Path(str(dataset).strip().rstrip("/"))
    if path.name in {"data.csv", "info.json"}:
        return path.parent.name
    return path.name


def claim_id(hypothesis: str, dataset: str) -> str:
    """Stable id for a hypothesis-and-dataset pair.

    Derived, not stored, so existing runs group correctly without migration.
    """
    basis = f"{normalize_hypothesis(hypothesis)}||{normalize_dataset(dataset)}"
    return hashlib.sha1(basis.encode()).hexdigest()[:12]


@dataclass
class Attempt:
    """One run, summarised for comparison against its siblings."""

    id: str
    created_at: str
    status: dict[str, str]
    n_complete: int
    running: bool

    # The short id this run is known by — EXP-14 — assigned once at creation.
    number: int | None = None

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
class Support:
    """What the attempts say, without pretending they measured the same thing.

    Each attempt explores its own decision space, so `4 of 96` from one and
    `9 of 288` from another are not two readings of one quantity — they are
    two estimates of the same underlying robustness over different universes
    of specification. Raw counts therefore cannot be pooled; rates can be
    compared, because "fraction of explored specifications" is at least the
    same kind of number.

    So the claim-level statement is a concordance, not an average: do the
    attempts reach the same verdict, and over what spread of rates. When they
    do not, that disagreement is the finding and is reported as such.
    """

    #: "supported" | "not_supported" | "mixed" | "disputed" | None
    verdict: str | None
    rate_min: float | None
    rate_max: float | None
    #: Attempts that got far enough to have verdicts, and attempts in total.
    n_scored: int
    n_attempts: int
    per_attempt: list[dict[str, Any]] = field(default_factory=list)

    @property
    def corroborated(self) -> bool:
        return self.n_scored > 1

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["corroborated"] = self.corroborated
        return d


def _dominant_verdict(verdicts: dict[str, int]) -> tuple[str | None, float | None]:
    """The verdict most of this attempt's specifications reached, and its rate.

    Failed universes are excluded from the denominator: a specification that
    could not be computed is an absence of evidence, and counting it as
    "not supported" would quietly turn a broken run into a negative result.
    """
    usable = {k: v for k, v in verdicts.items() if k != "failed"}
    total = sum(usable.values())
    if not total:
        return None, None
    supported = usable.get("supported", 0)
    rate = supported / total
    if supported == 0:
        return "not_supported", rate
    if supported == total:
        return "supported", rate
    # A claim holding in some specifications and not others is the ordinary
    # multiverse outcome; which way it leans is what the rate is for.
    return ("supported" if rate > 0.5 else "not_supported"), rate


def support(attempts: list[Attempt]) -> Support:
    scored: list[dict[str, Any]] = []
    for a in attempts:
        verdict, rate = _dominant_verdict(a.verdicts)
        if verdict is None:
            continue
        usable = {k: v for k, v in a.verdicts.items() if k != "failed"}
        scored.append(
            {
                "id": a.id,
                "verdict": verdict,
                "rate": rate,
                "n_supported": usable.get("supported", 0),
                "n_specs": sum(usable.values()),
                "coverage": a.coverage,
            }
        )

    if not scored:
        return Support(
            verdict=None,
            rate_min=None,
            rate_max=None,
            n_scored=0,
            n_attempts=len(attempts),
        )

    verdicts = {s["verdict"] for s in scored}
    rates = [s["rate"] for s in scored]
    return Support(
        verdict="disputed" if len(verdicts) > 1 else next(iter(verdicts)),
        rate_min=min(rates),
        rate_max=max(rates),
        n_scored=len(scored),
        n_attempts=len(attempts),
        per_attempt=scored,
    )


@dataclass
class Claim:
    id: str
    hypothesis: str
    dataset: str
    attempts: list[Attempt]
    description: str | None = None
    created_at: str = ""

    @property
    def dataset_name(self) -> str:
        # Normalised, not the bare basename: a claim recorded against the csv
        # inside a dataset folder must still name the dataset, or it detaches
        # from it in the listings and shows up as "data.csv".
        return normalize_dataset(self.dataset)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "hypothesis": self.hypothesis,
            "dataset": self.dataset,
            "dataset_name": self.dataset_name,
            "description": self.description,
            "created_at": self.created_at,
            "n_attempts": len(self.attempts),
            "attempts": [a.to_dict() for a in self.attempts],
            "support": support(self.attempts).to_dict(),
            "updated_at": max((a.created_at for a in self.attempts), default=self.created_at),
            **comparison(self.attempts),
        }


def config_label(attempt: Attempt) -> str:
    """What this attempt did *differently*, in as few words as possible.

    Only non-default settings appear. A label listing every knob would be the
    same on every row and so would distinguish nothing — the point is to name
    the change, not to restate the configuration.
    """
    from .config import RunConfig

    defaults = RunConfig()
    bits: list[str] = []

    mode = normalize_extraction_mode(attempt.mode)
    if mode and mode != defaults.decisions.mode:
        bits.append(mode)
    if attempt.critique != defaults.decisions.critique:
        bits.append("+critique" if attempt.critique else "-critique")
    if attempt.models and attempt.models != defaults.decisions.models:
        bits.append("/".join(attempt.models))
    if attempt.cap is not None and attempt.cap != defaults.universes.cap:
        bits.append(f"cap {attempt.cap}")
    if attempt.agent_models and attempt.agent_models != defaults.execute.models:
        bits.append("+".join(attempt.agent_models))
    if attempt.seeded:
        bits.append("seeded")

    return " · ".join(bits) if bits else "default"


def _discriminator(run_id: str) -> str:
    """A short, human-meaningful way to tell two run ids apart.

    Run ids are `YYYYMMDD-HHMMSS__slug`, optionally with a `-N` suffix added
    when two were created in the same second. The time plus that suffix is the
    part that actually varies.
    """
    time = run_id[9:15]
    tail = run_id.rsplit("-", 1)[-1]
    return f"{time}-{tail}" if tail.isdigit() and "__" not in tail else time


def config_labels(attempts: list[Attempt]) -> dict[str, str]:
    """Labels that actually tell attempts apart.

    Two attempts can share a configuration — most obviously when both predate
    a knob, so both read "default". A label that fails to distinguish them
    makes a comparison table unreadable, so collisions fall back to the time,
    and then to a counter, because two runs can share a minute *and* a second.
    """
    summaries = {a.id: config_label(a) for a in attempts}

    counts: dict[str, int] = {}
    for summary in summaries.values():
        counts[summary] = counts.get(summary, 0) + 1

    labelled = {
        aid: (f"{summary} · {_discriminator(aid)}" if counts[summary] > 1 else summary)
        for aid, summary in summaries.items()
    }

    # Belt and braces: whatever happens above, no two attempts may share a
    # label, or the comparison table becomes unreadable in exactly the case
    # that matters most.
    seen: dict[str, int] = {}
    for aid in sorted(labelled):
        label = labelled[aid]
        if label in seen:
            seen[label] += 1
            labelled[aid] = f"{label} #{seen[label]}"
        else:
            seen[label] = 1
    return labelled


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
        number=manifest.get("number") if isinstance(manifest.get("number"), int) else None,
        created_at=manifest.get("created_at", ""),
        status=status,
        n_complete=sum(1 for v in status.values() if v == "complete"),
        running=runner.is_running(analysis.run_id),
        mode=normalize_extraction_mode(decisions_cfg.get("mode")),
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


def all_claims(runs_dir: Path, *, include_archived: bool = False) -> list[Claim]:
    """Stored hypotheses plus run-derived claims, newest first.

    Archived claims and experiments are omitted unless asked for, so every
    listing — CLI and web alike — hides them from one decision here. Lookups by
    id still see everything; see `get_claim`.
    """
    from ..integrations import hypotheses as hypotheses_integration
    from . import settings as app_settings

    # Runs made before numbering get theirs here, so every listing — CLI and
    # web alike — can show a short id.
    store_module.ensure_numbers(runs_dir)

    archive = None if include_archived else app_settings.archive(runs_dir)

    grouped = {
        claim_id(record.hypothesis, record.dataset): Claim(
            id=claim_id(record.hypothesis, record.dataset),
            hypothesis=record.hypothesis,
            dataset=record.dataset,
            attempts=[],
            description=record.description,
            created_at=record.created_at,
        )
        for record in hypotheses_integration.list_all()
    }
    stored = set(grouped)
    for analysis in Run.list_all(runs_dir):
        if archive and archive.has_experiment(analysis.run_id):
            continue
        manifest = analysis.manifest()
        hypothesis = manifest.get("hypothesis") or ""
        dataset = manifest.get("dataset") or ""
        cid = claim_id(hypothesis, dataset)
        claim = grouped.get(cid)
        if claim is None:
            claim = Claim(id=cid, hypothesis=hypothesis, dataset=dataset, attempts=[])
            grouped[cid] = claim
        claim.attempts.append(summarise(analysis))

    if archive:
        grouped = {
            cid: claim
            for cid, claim in grouped.items()
            if not archive.has_hypothesis(cid)
            and not archive.has_dataset(claim.dataset_name)
            # A derived claim left with no unarchived experiments has nothing
            # to show; a stored one is a real record and stays.
            and (claim.attempts or cid in stored)
        }

    for claim in grouped.values():
        claim.attempts.sort(key=lambda a: a.created_at, reverse=True)
    return sorted(
        grouped.values(),
        key=lambda c: c.attempts[0].created_at if c.attempts else c.created_at,
        reverse=True,
    )


def get_claim(runs_dir: Path, cid: str) -> Claim | None:
    """Lookup by id, archived or not — a direct link must keep working."""
    for claim in all_claims(runs_dir, include_archived=True):
        if claim.id == cid:
            return claim
    return None


def stages_done(attempt: Attempt) -> str:
    return f"{attempt.n_complete}/{len(STAGES)}"
