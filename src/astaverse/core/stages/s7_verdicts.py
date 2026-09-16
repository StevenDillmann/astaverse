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
import math
import random
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from pydantic import BaseModel

from ...integrations.astra_io import read_astra_yaml
from ..schemas import (
    DecisionSpec,
    UniverseResult,
    UniverseSet,
    UniverseStats,
    Verdict,
)
from ..store import Run
from .s6_execute import ExecuteArtifact


class DecisionFlips(BaseModel):
    """How often changing one decision, alone, changes the conclusion.

    Computed over *matched pairs*: two universes identical in every decision
    but one. That isolates the decision's effect from everything else, and
    answers the question people actually ask of a multiverse — "does this
    choice change the answer?" — in a way a spread of means does not.
    """

    decision_id: str
    n_pairs: int
    n_flips: int
    flip_rate: float
    # ("option_a -> option_b", number of flips), worst first.
    flip_examples: list[str] = []


class CurveSummary(BaseModel):
    """Descriptive statistics for one comparable specification curve."""

    scale: str
    n_universes: int = 0
    n_estimates: int
    n_with_ci: int
    minimum: float
    q25: float
    median: float
    q75: float
    maximum: float
    n_significant_positive: int
    n_significant_negative: int
    n_indeterminate: int
    n_unavailable: int = 0


class OptionPairSensitivity(BaseModel):
    """Matched-pair comparison of two options of one decision.

    The decision-level score pools every option comparison, which hides
    whether the sensitivity comes from A vs B or A vs C. This keeps them apart
    and keeps the sign: `median_shift` is effect(B) - effect(A), so a positive
    value means switching from A to B raises the estimate.
    """

    option_a: str
    option_b: str
    n_pairs: int
    n_effect_pairs: int = 0
    median_abs_change: float | None = None
    median_shift: float | None = None
    normalized_shift: float | None = None
    inference_flip_rate: float | None = None


class DecisionSensitivityResult(BaseModel):
    """Matched-pair effect and inference sensitivity for one decision."""

    decision_id: str
    scale: str
    n_pairs: int
    n_effect_pairs: int
    n_inference_pairs: int
    median_abs_effect_change: float | None = None
    normalized_effect_change: float | None = None
    normalized_ci_low: float | None = None
    normalized_ci_high: float | None = None
    # Tail of the matched-pair changes: a decision that is decisive in a few
    # cells shows up here even when its median change is modest.
    effect_change_p90: float | None = None
    effect_change_max: float | None = None
    # Continuous inference shift across matched pairs, unlike the thresholded
    # flip rate: median |log10 p_a - log10 p_b|.
    median_abs_log10p_change: float | None = None
    # Sobol / functional-ANOVA shares of the curve's variance. First-order is
    # the decision's own effect; total includes every interaction it takes part
    # in. Exact on a complete grid, and only computed there.
    variance_share_first_order: float | None = None
    variance_share_total: float | None = None
    inference_flip_rate: float | None = None
    #: Pairs where one universe is significantly positive and the other
    #: significantly negative — the same data, two defensible analyses, opposite
    #: signed conclusions. Strictly stronger than `inference_flip_rate`.
    sign_reversal_rate: float | None = None
    option_medians: dict[str, float] = {}
    # Per option pair, ordered by option id, so A vs B, A vs C and B vs C are
    # reported separately underneath the pooled score above.
    option_pairs: list[OptionPairSensitivity] = []


class VerdictsArtifact(BaseModel):
    results: list[UniverseResult]
    verdict_rules: list[str]
    decision_flips: list[DecisionFlips] = []
    curve_summary: CurveSummary | None = None
    decision_sensitivity: list[DecisionSensitivityResult] = []
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
            std_error_standardized=row.get("std_error_standardized"),
            ci_low_standardized=row.get("ci_low_standardized"),
            ci_high_standardized=row.get("ci_high_standardized"),
            p_value=row.get("p_value"),
            n=row.get("n"),
            direction=row.get("direction"),
            converged=bool(row.get("converged", True)),
            notes=row.get("notes"),
        )
    return out


def compute_decision_flips(results: list[UniverseResult]) -> list[DecisionFlips]:
    """Rank decisions by how often flipping only that one flips the verdict.

    Groups results by "all decisions except D"; every pair inside a group
    differs in D alone. Linear in the number of results per decision rather
    than quadratic over all of them.
    """
    if not results:
        return []

    decision_ids = sorted({d for r in results for d in r.decisions})
    out: list[DecisionFlips] = []

    for did in decision_ids:
        # key = the rest of the specification, held fixed
        groups: dict[tuple, list[UniverseResult]] = defaultdict(list)
        for r in results:
            if did not in r.decisions:
                continue
            key = tuple(sorted((k, v) for k, v in r.decisions.items() if k != did))
            # Two agents running the same universe are not a matched pair.
            groups[(r.agent, key)].append(r)

        n_pairs = 0
        n_flips = 0
        flips_by_swap: Counter[str] = Counter()
        for members in groups.values():
            for i in range(len(members)):
                for j in range(i + 1, len(members)):
                    a, b = members[i], members[j]
                    if a.decisions[did] == b.decisions[did]:
                        continue
                    n_pairs += 1
                    if a.verdict != b.verdict:
                        n_flips += 1
                        lo, hi = sorted([a.decisions[did], b.decisions[did]])
                        flips_by_swap[f"{lo} vs {hi}"] += 1
        if n_pairs:
            out.append(
                DecisionFlips(
                    decision_id=did,
                    n_pairs=n_pairs,
                    n_flips=n_flips,
                    flip_rate=n_flips / n_pairs,
                    flip_examples=[f"{swap} ({n})" for swap, n in flips_by_swap.most_common(3)],
                )
            )

    out.sort(key=lambda d: (d.flip_rate, d.n_flips), reverse=True)
    return out


def _is_finite(value: float | None) -> bool:
    return value is not None and math.isfinite(value)


def _quantile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _rule_priority(result: UniverseResult) -> int:
    if result.verdict_rule == "alpha_05_directional":
        return 3
    if result.verdict_rule == "alpha_05_two_sided":
        return 2
    return 1


def _preferred_results(results: list[UniverseResult]) -> list[UniverseResult]:
    """Use one verdict rule per universe and agent, avoiding duplicated statistics."""
    selected: dict[tuple[str | None, str], UniverseResult] = {}
    for result in results:
        key = (result.agent, result.universe_id)
        current = selected.get(key)
        if current is None or _rule_priority(result) > _rule_priority(current):
            selected[key] = result
    return list(selected.values())


def _curve_scale(results: list[UniverseResult]) -> str:
    usable = [
        result.stats
        for result in results
        if result.stats.converged
        and (_is_finite(result.stats.estimate_standardized) or _is_finite(result.stats.estimate))
    ]
    if usable and all(_is_finite(stats.estimate_standardized) for stats in usable):
        return "standardized"
    return "raw"


def _effect_value(stats: UniverseStats, scale: str) -> float | None:
    value = stats.estimate_standardized if scale == "standardized" else stats.estimate
    return value if _is_finite(value) else None


def _standardized_se(stats: UniverseStats) -> float | None:
    if _is_finite(stats.std_error_standardized):
        return abs(stats.std_error_standardized)
    # Backward compatibility for artifacts created before standardized
    # uncertainty was required. This is valid when standardization is a linear
    # rescaling, as required by the execution contract.
    if (
        _is_finite(stats.std_error)
        and _is_finite(stats.estimate)
        and _is_finite(stats.estimate_standardized)
        and stats.estimate != 0
    ):
        return abs(stats.std_error * stats.estimate_standardized / stats.estimate)
    return None


def _effect_interval(stats: UniverseStats, scale: str) -> tuple[float, float] | None:
    estimate = _effect_value(stats, scale)
    if estimate is None:
        return None
    if (
        scale == "standardized"
        and _is_finite(stats.ci_low_standardized)
        and _is_finite(stats.ci_high_standardized)
    ):
        return (stats.ci_low_standardized, stats.ci_high_standardized)
    se = _standardized_se(stats) if scale == "standardized" else stats.std_error
    if not _is_finite(se):
        return None
    return estimate - 1.96 * abs(se), estimate + 1.96 * abs(se)


def _inference_class(result: UniverseResult, scale: str) -> str | None:
    estimate = _effect_value(result.stats, scale)
    p_value = result.stats.p_value
    if estimate is None or not _is_finite(p_value) or not result.stats.converged:
        return None
    alpha = 0.01 if "alpha_01" in result.verdict_rule else 0.05
    if p_value >= alpha or estimate == 0:
        return "indeterminate"
    return "positive" if estimate > 0 else "negative"


def compute_curve_summary(results: list[UniverseResult]) -> CurveSummary | None:
    preferred = _preferred_results(results)
    scale = _curve_scale(preferred)
    usable = [
        result
        for result in preferred
        if result.stats.converged and _effect_value(result.stats, scale) is not None
    ]
    values = [_effect_value(result.stats, scale) for result in usable]
    finite_values = [value for value in values if value is not None]
    if not finite_values:
        return None
    classes = [_inference_class(result, scale) for result in usable]
    n_classified = sum(value is not None for value in classes)
    return CurveSummary(
        scale=scale,
        n_universes=len(preferred),
        n_estimates=len(finite_values),
        n_with_ci=sum(_effect_interval(result.stats, scale) is not None for result in usable),
        minimum=min(finite_values),
        q25=_quantile(finite_values, 0.25),
        median=statistics.median(finite_values),
        q75=_quantile(finite_values, 0.75),
        maximum=max(finite_values),
        n_significant_positive=classes.count("positive"),
        n_significant_negative=classes.count("negative"),
        n_indeterminate=classes.count("indeterminate"),
        n_unavailable=len(preferred) - n_classified,
    )


def _bootstrap_median_ci(
    values: list[float], decision_id: str, samples: int = 1000
) -> tuple[float, float] | None:
    if not values:
        return None
    if len(values) == 1:
        return values[0], values[0]
    rng = random.Random(f"astaverse:{decision_id}")
    medians = [statistics.median(rng.choices(values, k=len(values))) for _ in range(samples)]
    return _quantile(medians, 0.025), _quantile(medians, 0.975)


def _conditional_mean_variance(
    rows: list[tuple[dict[str, str], float]], by: tuple[str, ...], grand_mean: float
) -> float:
    """Variance of E[Y | the decisions in `by`], weighted by cell size."""
    groups: dict[tuple, list[float]] = defaultdict(list)
    for selections, value in rows:
        groups[tuple(selections[decision] for decision in by)].append(value)
    return sum(
        len(values) * (statistics.fmean(values) - grand_mean) ** 2 for values in groups.values()
    ) / len(rows)


def _variance_shares(
    preferred: list[UniverseResult], scale: str, decision_ids: list[str]
) -> dict[str, tuple[float, float]]:
    """(first-order, total) variance share per decision — Sobol indices.

    On a complete, balanced grid the estimate is a deterministic function of
    the decisions, so its variance decomposes exactly: the first-order share is
    Var(E[Y | D]) / Var(Y), the total share is 1 - Var(E[Y | all but D]) / Var(Y),
    and the gap between them is the variance D contributes through interactions.
    The decomposition is only exact on a full grid, so an agent whose reported
    universes do not cover every combination exactly once contributes nothing;
    several complete agents are averaged.
    """
    per_agent: dict[str | None, list[tuple[dict[str, str], float]]] = defaultdict(list)
    for result in preferred:
        value = _effect_value(result.stats, scale)
        if value is None or not result.stats.converged:
            continue
        selections = {k: v for k, v in result.decisions.items() if k in decision_ids}
        if len(selections) != len(decision_ids):
            continue
        per_agent[result.agent].append((selections, value))

    accumulated: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for rows in per_agent.values():
        options = {d: {sel[d] for sel, _ in rows} for d in decision_ids}
        expected = math.prod(len(o) for o in options.values())
        cells = {tuple(sel[d] for d in decision_ids) for sel, _ in rows}
        if len(rows) != expected or len(cells) != expected:
            continue
        values = [value for _, value in rows]
        grand_mean = statistics.fmean(values)
        total = sum((value - grand_mean) ** 2 for value in values) / len(values)
        if total <= 0:
            continue
        for decision in decision_ids:
            first = _conditional_mean_variance(rows, (decision,), grand_mean)
            others = tuple(d for d in decision_ids if d != decision)
            rest = _conditional_mean_variance(rows, others, grand_mean) if others else 0.0
            accumulated[decision].append((first / total, 1 - rest / total))
    return {
        decision: (
            statistics.fmean(first for first, _ in shares),
            statistics.fmean(total for _, total in shares),
        )
        for decision, shares in accumulated.items()
    }


def compute_decision_sensitivity(
    results: list[UniverseResult],
    summary: CurveSummary | None = None,
) -> list[DecisionSensitivityResult]:
    """Measure decisions using universes matched on every other analytic choice.

    Three complementary readings per decision, all descriptive (universes share
    one dataset, so none of this is inference about the world):

    * matched pairs — median, 90th percentile and maximum absolute change in
      the estimate when only this decision changes, in outcome units and as a
      share of the curve's interquartile range;
    * variance shares — how much of the curve's spread the decision explains
      alone and through interactions (complete grids only);
    * inference — how often the significance class flips across a pair, and
      the median shift in log10 p.
    """
    preferred = _preferred_results(results)
    summary = summary or compute_curve_summary(preferred)
    if summary is None:
        return []
    scale = summary.scale
    curve_iqr = summary.q75 - summary.q25
    normalization_scale = (
        None if math.isclose(summary.q25, summary.q75, rel_tol=1e-9, abs_tol=1e-12) else curve_iqr
    )
    decision_ids = sorted(
        {
            decision
            for result in preferred
            for decision in result.decisions
            if decision != "verdict_rule"
        }
    )
    variance_shares = _variance_shares(preferred, scale, decision_ids)
    output: list[DecisionSensitivityResult] = []

    for decision_id in decision_ids:
        groups: dict[tuple, list[UniverseResult]] = defaultdict(list)
        option_values: dict[str, list[float]] = defaultdict(list)
        for result in preferred:
            if decision_id not in result.decisions:
                continue
            rest = tuple(
                sorted(
                    (key, value)
                    for key, value in result.decisions.items()
                    if key not in {decision_id, "verdict_rule"}
                )
            )
            groups[(result.agent, rest)].append(result)
            value = _effect_value(result.stats, scale)
            if value is not None:
                option_values[result.decisions[decision_id]].append(value)

        n_pairs = 0
        inference_pairs = 0
        inference_flips = 0
        sign_reversals = 0
        effect_changes: list[float] = []
        log10p_changes: list[float] = []
        pair_counts: Counter[tuple[str, str]] = Counter()
        pair_shifts: dict[tuple[str, str], list[float]] = defaultdict(list)
        pair_inference: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0])
        for members in groups.values():
            for index, left in enumerate(members):
                for right in members[index + 1 :]:
                    if left.decisions[decision_id] == right.decisions[decision_id]:
                        continue
                    n_pairs += 1
                    # Orient every pair the same way (A before B by option id)
                    # so shifts from different matched pairs can be pooled.
                    first, second = sorted(
                        (left, right), key=lambda result: result.decisions[decision_id]
                    )
                    key = (first.decisions[decision_id], second.decisions[decision_id])
                    pair_counts[key] += 1
                    first_value = _effect_value(first.stats, scale)
                    second_value = _effect_value(second.stats, scale)
                    if first_value is not None and second_value is not None:
                        effect_changes.append(abs(second_value - first_value))
                        pair_shifts[key].append(second_value - first_value)
                    left_p, right_p = left.stats.p_value, right.stats.p_value
                    if _is_finite(left_p) and _is_finite(right_p) and left_p > 0 and right_p > 0:
                        log10p_changes.append(abs(math.log10(left_p) - math.log10(right_p)))
                    left_class = _inference_class(left, scale)
                    right_class = _inference_class(right, scale)
                    if left_class is not None and right_class is not None:
                        inference_pairs += 1
                        inference_flips += left_class != right_class
                        sign_reversals += {left_class, right_class} == {
                            "positive",
                            "negative",
                        }
                        pair_inference[key][0] += 1
                        pair_inference[key][1] += left_class != right_class

        option_pairs = []
        for key in sorted(pair_counts):
            shifts = pair_shifts.get(key, [])
            median_shift = statistics.median(shifts) if shifts else None
            classified, flipped = pair_inference[key]
            option_pairs.append(
                OptionPairSensitivity(
                    option_a=key[0],
                    option_b=key[1],
                    n_pairs=pair_counts[key],
                    n_effect_pairs=len(shifts),
                    median_abs_change=statistics.median(abs(x) for x in shifts) if shifts else None,
                    median_shift=median_shift,
                    normalized_shift=(
                        median_shift / normalization_scale
                        if median_shift is not None and normalization_scale is not None
                        else None
                    ),
                    inference_flip_rate=flipped / classified if classified else None,
                )
            )

        median_change = statistics.median(effect_changes) if effect_changes else None
        shares = variance_shares.get(decision_id)
        normalized_change = (
            median_change / normalization_scale
            if median_change is not None and normalization_scale is not None
            else None
        )
        bootstrap_ci = _bootstrap_median_ci(effect_changes, decision_id)
        output.append(
            DecisionSensitivityResult(
                decision_id=decision_id,
                scale=scale,
                n_pairs=n_pairs,
                n_effect_pairs=len(effect_changes),
                n_inference_pairs=inference_pairs,
                median_abs_effect_change=median_change,
                normalized_effect_change=normalized_change,
                normalized_ci_low=(
                    bootstrap_ci[0] / normalization_scale
                    if bootstrap_ci is not None and normalization_scale is not None
                    else None
                ),
                normalized_ci_high=(
                    bootstrap_ci[1] / normalization_scale
                    if bootstrap_ci is not None and normalization_scale is not None
                    else None
                ),
                effect_change_p90=_quantile(effect_changes, 0.9) if effect_changes else None,
                effect_change_max=max(effect_changes) if effect_changes else None,
                median_abs_log10p_change=(
                    statistics.median(log10p_changes) if log10p_changes else None
                ),
                variance_share_first_order=shares[0] if shares else None,
                variance_share_total=shares[1] if shares else None,
                inference_flip_rate=(
                    inference_flips / inference_pairs if inference_pairs else None
                ),
                sign_reversal_rate=(
                    sign_reversals / inference_pairs if inference_pairs else None
                ),
                option_medians={
                    option: statistics.median(values)
                    for option, values in option_values.items()
                    if values
                },
                option_pairs=option_pairs,
            )
        )

    output.sort(
        key=lambda item: (
            item.normalized_effect_change if item.normalized_effect_change is not None else -1,
            item.inference_flip_rate if item.inference_flip_rate is not None else -1,
        ),
        reverse=True,
    )
    return output


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
                        and rule
                        == (verdict_decision.default if verdict_decision else DEFAULT_RULE),
                    )
                )

    curve_summary = compute_curve_summary(results)
    decision_sensitivity = compute_decision_sensitivity(results, curve_summary)
    artifact = VerdictsArtifact(
        results=results,
        verdict_rules=rules,
        decision_flips=compute_decision_flips(results),
        curve_summary=curve_summary,
        decision_sensitivity=decision_sensitivity,
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
