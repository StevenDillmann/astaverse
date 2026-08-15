"""s7 — verdicts: universe statistics -> verdicts, assigned here.

The agent reports numbers; astaverse decides what they mean. This is bias
control 2, and it is also the more correct design: the verdict rule is itself
an under-specified analytic decision, so it belongs in the decision space,
applied deterministically to the same statistics.

There is deliberately no LLM in this module. A verdict must be reproducible
from `universes.jsonl` alone — `tests/test_verdicts.py` asserts it.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from ..astra_io import read_astra_yaml
from ..schemas import (
    DecisionSpec,
    StudySpec,
    UniverseResult,
    UniverseSet,
    UniverseStats,
    Verdict,
)
from ..store import Run
from .s6_execute import ExecuteArtifact


class VerdictsArtifact(BaseModel):
    results: list[UniverseResult]
    verdict_rules: list[str]
    n_expected: int
    n_reported: int
    missing_universe_ids: list[str] = []
    unexpected_universe_ids: list[str] = []
    rubric_scores: dict[str, float] = {}

    @property
    def complete(self) -> bool:
        return not self.missing_universe_ids and not self.unexpected_universe_ids


# --------------------------------------------------------------------------
# verdict rules — pure functions of the reported statistics
# --------------------------------------------------------------------------


def _threshold_rule(stats: UniverseStats, alpha: float, directional: bool) -> Verdict:
    if not stats.converged:
        return Verdict.failed
    if stats.p_value is None:
        return Verdict.failed
    if stats.p_value >= alpha:
        return Verdict.not_supported
    if directional and stats.direction == "negative":
        # Significant, but pointing against the hypothesis.
        return Verdict.not_supported
    if directional and stats.direction not in ("positive", "negative", "none", None):
        return Verdict.mixed
    return Verdict.supported


VERDICT_RULES = {
    "alpha_05_two_sided": lambda s: _threshold_rule(s, 0.05, directional=False),
    "alpha_01_two_sided": lambda s: _threshold_rule(s, 0.01, directional=False),
    "alpha_05_directional": lambda s: _threshold_rule(s, 0.05, directional=True),
}

DEFAULT_RULE = "alpha_05_two_sided"


def apply_verdict(stats: UniverseStats, rule: str) -> Verdict:
    """Apply a named verdict rule to one universe's statistics."""
    fn = VERDICT_RULES.get(rule)
    if fn is None:
        raise KeyError(f"unknown verdict rule '{rule}' (have: {', '.join(VERDICT_RULES)})")
    return fn(stats)


# --------------------------------------------------------------------------
# artifact collection
# --------------------------------------------------------------------------


def _find_universes_jsonl(job_dir: Path) -> Path | None:
    matches = sorted(job_dir.rglob("artifacts/app/universes.jsonl"))
    return matches[0] if matches else None


def _read_rubric_score(job_dir: Path) -> float | None:
    for reward in sorted(job_dir.rglob("verifier/reward.json")):
        try:
            return float(json.loads(reward.read_text()).get("rubric"))
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
    return None


def _parse_stats(path: Path) -> dict[str, UniverseStats]:
    out: dict[str, UniverseStats] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        uid = row.get("universe_id")
        if not uid:
            continue
        out[uid] = UniverseStats(
            universe_id=uid,
            decisions=row.get("decisions") or {},
            estimate=row.get("estimate"),
            estimate_standardized=row.get("estimate_standardized"),
            std_error=row.get("std_error"),
            p_value=row.get("p_value"),
            n=row.get("n"),
            direction=row.get("direction"),
            converged=bool(row.get("converged", True)),
            notes=row.get("notes"),
        )
    return out


def run(run_obj: Run, universes_jsonl: str | None = None) -> VerdictsArtifact:
    spec: DecisionSpec = read_astra_yaml(run_obj.artifact_path("decisions"))
    universe_set: UniverseSet = run_obj.read_artifact("universes", UniverseSet)

    # Which verdict rules to apply: every option of the post-hoc verdict_rule
    # decision, or just the default if the spec has none.
    verdict_decision = spec.decisions.get("verdict_rule")
    rules = list(verdict_decision.options) if verdict_decision else [DEFAULT_RULE]
    rules = [r for r in rules if r in VERDICT_RULES] or [DEFAULT_RULE]

    # Gather per-agent statistics.
    sources: list[tuple[str | None, Path]] = []
    if universes_jsonl:
        sources.append((None, Path(universes_jsonl)))
    else:
        execute: ExecuteArtifact = run_obj.read_artifact("execute", ExecuteArtifact)
        for job in execute.jobs:
            if not job.job_dir:
                continue
            found = _find_universes_jsonl(Path(job.job_dir))
            if found:
                sources.append((job.model or job.agent, found))
            else:
                run_obj.log("verdicts", f"no universes.jsonl in {job.job_dir}")
    if not sources:
        raise FileNotFoundError(
            "no universes.jsonl found — run `astaverse execute`, or pass --universes-jsonl"
        )

    expected = {u.id: u for u in universe_set.universes}
    results: list[UniverseResult] = []
    missing: set[str] = set()
    unexpected: set[str] = set()
    rubric_scores: dict[str, float] = {}

    for agent, path in sources:
        stats_by_id = _parse_stats(path)
        missing |= set(expected) - set(stats_by_id)
        unexpected |= set(stats_by_id) - set(expected)
        score = _read_rubric_score(path.parents[2]) if path.parents[2].exists() else None
        if score is not None and agent:
            rubric_scores[agent] = score

        for uid, stats in stats_by_id.items():
            universe = expected.get(uid)
            if universe is None:
                continue
            for rule in rules:
                results.append(
                    UniverseResult(
                        universe_id=uid,
                        decisions={**universe.decisions, "verdict_rule": rule},
                        stats=stats,
                        verdict=apply_verdict(stats, rule),
                        verdict_rule=rule,
                        agent=agent,
                        is_default=universe.is_default
                        and rule == (verdict_decision.default if verdict_decision else DEFAULT_RULE),
                    )
                )

    artifact = VerdictsArtifact(
        results=results,
        verdict_rules=rules,
        n_expected=len(expected) * len(rules) * len(sources),
        n_reported=len(results),
        missing_universe_ids=sorted(missing),
        unexpected_universe_ids=sorted(unexpected),
        rubric_scores=rubric_scores,
    )
    run_obj.write_artifact("verdicts", artifact)
    run_obj.record_stage(
        "verdicts",
        n_results=len(results),
        rules=rules,
        complete=artifact.complete,
        missing=sorted(missing),
    )
    msg = f"{len(results)} results from {len(sources)} source(s) x {len(rules)} verdict rule(s)"
    if missing:
        msg += f"; INCOMPLETE — {len(missing)} universes missing: {', '.join(sorted(missing)[:5])}"
    run_obj.log("verdicts", msg)
    return artifact
