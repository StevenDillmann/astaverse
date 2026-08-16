"""s8 — robust surprisal: a verdict distribution -> surprisal as a distribution.

Reimplements AutoDiscovery's belief update standalone (see `beliefs.py` and
`run.py` in asta-autodiscovery), then reports the resulting surprisal across
universes rather than at one arbitrary point in the decision space.

The headline number is `fragility_index`: how far the single-universe
(default-option) surprisal sits from the median across the multiverse. That is
the quantity slide 1 cannot see and slide 2 exists to expose.
"""

from __future__ import annotations

import math
import statistics
from collections import Counter, defaultdict

from pydantic import BaseModel, Field

from ...integrations.astra_io import read_astra_yaml
from ...integrations.llm import DEFAULT_BELIEF_MODEL, structured_call
from ..schemas import (
    BeliefDistribution,
    DecisionSensitivity,
    DecisionSpec,
    RobustSurprisal,
    UniverseSurprisal,
    Verdict,
)
from ..store import Run
from .s7_verdicts import VerdictsArtifact

# Categorical belief scale, matching AutoDiscovery's `boolean_cat` mode.
CATEGORY_SCORES = {
    "definitely_false": 0.0,
    "maybe_false": 0.25,
    "uncertain": 0.5,
    "maybe_true": 0.75,
    "definitely_true": 1.0,
}
CANNOT_COMMENT = "cannot_comment"

JEFFREYS = (0.5, 0.5)
DEFAULT_N_SAMPLES = 5
DEFAULT_EVIDENCE_WEIGHT = 2.0
SURPRISAL_WIDTH = 0.2


class _BeliefResponse(BaseModel):
    judgement: str = Field(
        description=(
            "One of: definitely_false, maybe_false, uncertain, maybe_true, "
            "definitely_true, cannot_comment"
        )
    )
    reasoning: str = Field(default="", description="One sentence of justification")


# --------------------------------------------------------------------------
# belief maths
# --------------------------------------------------------------------------


def theoretical_max_shift(
    n_samples: int, weight: float = 1.0, prior_params: tuple[float, float] = JEFFREYS
) -> float:
    """Largest achievable prior->posterior mean shift, for normalisation.

    Ported from asta-autodiscovery's `_theoretical_max_boolean_cat`, derived in
    its `docs/autodiscovery/surprisal_normalization.md`. Verified in
    `tests/test_surprisal.py` against the documented value 0.7729916774697783
    for N=30, w=1, Jeffreys.
    """
    alpha, beta = prior_params
    total = alpha + beta
    d = min(alpha, beta)
    t = weight * n_samples
    if t <= 0:
        return 1.0
    u_star = d + math.sqrt(d * (d + t))
    u_opt = min(max(u_star, total), total + n_samples)
    return (t * (u_opt - d)) / (u_opt * (u_opt + t))


def beta_from_counts(
    counts: dict[str, int], weight: float = 1.0, prior_params: tuple[float, float] = JEFFREYS
) -> BeliefDistribution:
    """Categorical draws -> Beta parameters, as `boolean_cat` does."""
    alpha_obs = sum(counts.get(cat, 0) * score for cat, score in CATEGORY_SCORES.items())
    n_effective = sum(counts.get(cat, 0) for cat in CATEGORY_SCORES)
    return BeliefDistribution(
        alpha=weight * alpha_obs + prior_params[0],
        beta=weight * (n_effective - alpha_obs) + prior_params[1],
        counts=dict(counts),
        n_samples=n_effective,
    )


def posterior_from_prior(
    prior: BeliefDistribution,
    counts: dict[str, int],
    weight: float = DEFAULT_EVIDENCE_WEIGHT,
) -> BeliefDistribution:
    """Explicit Bayesian update of `prior` with new categorical evidence."""
    alpha_obs = sum(counts.get(cat, 0) * score for cat, score in CATEGORY_SCORES.items())
    n_effective = sum(counts.get(cat, 0) for cat in CATEGORY_SCORES)
    return BeliefDistribution(
        alpha=prior.alpha + weight * alpha_obs,
        beta=prior.beta + weight * (n_effective - alpha_obs),
        counts=dict(counts),
        n_samples=n_effective,
    )


# --------------------------------------------------------------------------
# LLM belief elicitation
# --------------------------------------------------------------------------

BELIEF_SYSTEM = (
    "You are a careful scientific referee. You judge how likely a hypothesis is "
    "to be true, given whatever evidence you are shown."
)

PRIOR_PROMPT = """\
How likely is the following hypothesis to be true, based only on your general
knowledge? No experimental evidence is provided.

Hypothesis: {hypothesis}

Answer with one of: definitely_false, maybe_false, uncertain, maybe_true,
definitely_true, cannot_comment.
"""

POSTERIOR_PROMPT = """\
Judge the following hypothesis in light of the evidence from one analysis.

Hypothesis: {hypothesis}

## Analytic choices made in this analysis
{decisions}

## Result
{result}

Answer with one of: definitely_false, maybe_false, uncertain, maybe_true,
definitely_true, cannot_comment.
"""

JOINT_PROMPT = """\
Judge the following hypothesis in light of a multiverse analysis: the same
data analysed under every combination of the analytic choices that reasonable
analysts disagree about.

Hypothesis: {hypothesis}

## How the {n} analyses came out
{summary}

## Where the specifications disagree
{sensitivity}

Weigh this as ONE body of evidence, not as {n} independent studies — every
specification uses the same dataset. What matters is how the conclusion holds
up across defensible choices: a result that survives most specifications is
stronger evidence than any single one, and a result that depends on one
arbitrary choice is weaker than its best specification makes it look.

Answer with one of: definitely_false, maybe_false, uncertain, maybe_true,
definitely_true, cannot_comment.
"""


def _elicit(
    prompt: str, model: str, n_samples: int, run_obj: Run, tag: str
) -> dict[str, int]:
    responses = structured_call(
        prompt,
        _BeliefResponse,
        model,
        system=BELIEF_SYSTEM,
        temperature=1.0,
        n=n_samples,
        log_dir=run_obj.root,
        tag=tag,
    )
    counts: Counter[str] = Counter()
    for r in responses:
        judgement = r.judgement.strip().lower()
        if judgement in CATEGORY_SCORES or judgement == CANNOT_COMMENT:
            counts[judgement] += 1
        else:
            counts[CANNOT_COMMENT] += 1
    return dict(counts)


def _describe_result(result) -> str:
    s = result.stats
    parts = []
    # Prefer the comparable estimand: describing a raw coefficient to the
    # judge invites it to read magnitude differences that are only unit
    # changes between universes.
    if s.estimate_standardized is not None:
        parts.append(f"standardized effect = {s.estimate_standardized:.4g}")
    elif s.estimate is not None:
        parts.append(f"estimate = {s.estimate:.4g}")
    if s.std_error is not None:
        parts.append(f"std. error = {s.std_error:.4g}")
    if s.p_value is not None:
        parts.append(f"p = {s.p_value:.4g}")
    if s.n is not None:
        parts.append(f"n = {s.n}")
    if s.direction:
        parts.append(f"direction = {s.direction}")
    if not s.converged:
        parts.append("the model did not converge")
    body = "; ".join(parts) if parts else "no statistics were reported"
    verdict = {
        Verdict.supported: "On this analysis the hypothesis is supported",
        Verdict.not_supported: "On this analysis the hypothesis is not supported",
        Verdict.mixed: "On this analysis the result is mixed",
        Verdict.failed: "This analysis failed to produce a usable result",
    }[result.verdict]
    # Deliberately does not name the verdict rule. The evidence is the numbers
    # and what they imply; the label attached to the threshold is incidental,
    # and leaving it out lets universes that differ only by rule name share an
    # elicitation.
    return f"{body}. {verdict}."


# --------------------------------------------------------------------------
# the stage
# --------------------------------------------------------------------------


def run(
    run_obj: Run,
    model: str | None = None,
    n_samples: int = DEFAULT_N_SAMPLES,
    evidence_weight: float = DEFAULT_EVIDENCE_WEIGHT,
) -> RobustSurprisal:
    model = model or DEFAULT_BELIEF_MODEL
    spec: DecisionSpec = read_astra_yaml(run_obj.artifact_path("decisions"))
    verdicts: VerdictsArtifact = run_obj.read_artifact("verdicts", VerdictsArtifact)

    if not verdicts.results:
        raise ValueError("no universe results to analyse")
    if not verdicts.complete:
        run_obj.log(
            "surprisal",
            f"WARNING: incomplete grid ({len(verdicts.missing_universe_ids)} universes missing); "
            "the distribution below is over what was actually reported",
        )

    # Prior once, from the hypothesis alone.
    prior_counts = _elicit(
        PRIOR_PROMPT.format(hypothesis=spec.hypothesis),
        model,
        n_samples,
        run_obj,
        "s8_prior",
    )
    prior = beta_from_counts(prior_counts, weight=1.0)
    max_shift = theoretical_max_shift(n_samples, weight=evidence_weight)

    # The belief prompt is a function of the statistics and the verdict, not of
    # which universe produced them. Universes that report the same numbers and
    # land on the same verdict share an elicitation — on a grid where a verdict
    # rule varies without changing the numbers, that alone cuts the call count
    # by the number of rules.
    cache: dict[str, dict[str, int]] = {}
    n_elicited = 0

    per_universe: list[UniverseSurprisal] = []
    for result in verdicts.results:
        # The verdict rule is excluded: it is a reading of the numbers, not an
        # analytic choice made during the analysis.
        decisions_text = "\n".join(
            f"- {did}: {oid}"
            for did, oid in sorted(result.decisions.items())
            if did != "verdict_rule"
        )
        described = _describe_result(result)
        prompt = POSTERIOR_PROMPT.format(
            hypothesis=spec.hypothesis,
            decisions=decisions_text,
            result=described,
        )
        signature = f"{decisions_text}||{described}"
        counts = cache.get(signature)
        if counts is None:
            counts = _elicit(
                prompt,
                model,
                n_samples,
                run_obj,
                f"s8_posterior::{result.universe_id}::{result.verdict_rule}",
            )
            cache[signature] = counts
            n_elicited += 1
        posterior = posterior_from_prior(prior, counts, weight=evidence_weight)
        per_universe.append(
            UniverseSurprisal(
                universe_id=result.universe_id,
                decisions=result.decisions,
                verdict=result.verdict,
                posterior_mean=posterior.mean,
                surprisal=(posterior.mean - prior.mean) / max_shift,
                is_default=result.is_default,
                agent=result.agent,
            )
        )

    # --- the belief update: one posterior conditioned on the whole multiverse
    verdict_counts = Counter(u.verdict.value for u in per_universe)
    summary_lines = [
        f"- {count} of {len(per_universe)} specifications: {verdict.replace('_', ' ')}"
        for verdict, count in verdict_counts.most_common()
    ]
    finite = [
        r.stats.p_value for r in verdicts.results if r.stats.p_value is not None
    ]
    if finite:
        summary_lines.append(f"- median p-value across specifications: {statistics.median(finite):.4g}")
    estimates = [
        r.stats.estimate_standardized
        for r in verdicts.results
        if r.stats.estimate_standardized is not None
    ]
    if estimates:
        summary_lines.append(
            f"- standardized effect ranges {min(estimates):+.3g} to {max(estimates):+.3g}, "
            f"median {statistics.median(estimates):+.3g}"
        )

    sensitivity_preview = _decision_sensitivity(per_universe, spec)
    sensitivity_lines = [
        f"- {s.decision_id}: "
        + ", ".join(f"{oid} -> {mean:+.3f}" for oid, mean in sorted(s.option_means.items()))
        for s in sensitivity_preview[:6]
    ] or ["- (only one specification; no sensitivity to report)"]

    joint_counts = _elicit(
        JOINT_PROMPT.format(
            hypothesis=spec.hypothesis,
            n=len(per_universe),
            summary="\n".join(summary_lines),
            sensitivity="\n".join(sensitivity_lines),
        ),
        model,
        n_samples,
        run_obj,
        "s8_joint",
    )
    joint_posterior = posterior_from_prior(prior, joint_counts, weight=evidence_weight)
    joint_surprisal = (joint_posterior.mean - prior.mean) / max_shift

    values = [u.surprisal for u in per_universe]
    median = statistics.median(values)
    positive = sum(1 for v in values if v > 0)
    modal = max(positive, len(values) - positive)

    defaults = [u.surprisal for u in per_universe if u.is_default]
    single = statistics.mean(defaults) if defaults else None

    robust = RobustSurprisal(
        prior_mean=prior.mean,
        n_universes=len(per_universe),
        joint_surprisal=joint_surprisal,
        joint_posterior_mean=joint_posterior.mean,
        per_universe=per_universe,
        median=median,
        mean=statistics.mean(values),
        iqr=_iqr(values),
        sign_consistency=modal / len(values),
        frac_surprising=sum(1 for v in values if abs(v) >= SURPRISAL_WIDTH) / len(values),
        verdict_distribution=dict(Counter(u.verdict.value for u in per_universe)),
        single_universe_surprisal=single,
        fragility_index=abs(single - median) if single is not None else None,
        decision_sensitivity=_decision_sensitivity(per_universe, spec),
        between_agent_spread=_between_agent_spread(per_universe),
    )

    run_obj.write_artifact("surprisal", robust)
    run_obj.record_stage(
        "surprisal",
        model=model,
        n_universes=len(per_universe),
        joint_surprisal=robust.joint_surprisal,
        median=robust.median,
        fragility_index=robust.fragility_index,
    )
    run_obj.log(
        "surprisal",
        f"{n_elicited} elicitations for {len(per_universe)} results "
        f"({len(per_universe) - n_elicited} cache hits) | "
        f"JOINT={joint_surprisal:+.3f} | "
        f"median={robust.median:.3f} iqr={robust.iqr:.3f} "
        f"sign_consistency={robust.sign_consistency:.2f} "
        f"single_universe={single if single is None else round(single, 3)} "
        f"fragility={robust.fragility_index if robust.fragility_index is None else round(robust.fragility_index, 3)}",
    )
    return robust


def _iqr(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    ordered = sorted(values)
    q1, q3 = statistics.quantiles(ordered, n=4)[0], statistics.quantiles(ordered, n=4)[2]
    return q3 - q1


def _decision_sensitivity(
    per_universe: list[UniverseSurprisal], spec: DecisionSpec
) -> list[DecisionSensitivity]:
    """Mean surprisal per option of each decision, marginalizing the rest.

    This is the specification curve in tabular form: it shows which decisions
    actually moved the result, as opposed to which ones were *predicted* to.
    """
    out: list[DecisionSensitivity] = []
    for did, decision in spec.decisions.items():
        by_option: dict[str, list[float]] = defaultdict(list)
        for u in per_universe:
            oid = u.decisions.get(did)
            if oid is not None:
                by_option[oid].append(u.surprisal)
        if len(by_option) < 2:
            continue
        means = {oid: statistics.mean(vals) for oid, vals in by_option.items()}
        out.append(
            DecisionSensitivity(
                decision_id=did,
                label=decision.label,
                kind=decision.kind,
                option_means=means,
                spread=max(means.values()) - min(means.values()),
            )
        )
    out.sort(key=lambda d: d.spread, reverse=True)
    return out


def _between_agent_spread(per_universe: list[UniverseSurprisal]) -> float | None:
    """Spread of per-agent medians — the implementation-bias estimate.

    Compare against the between-universe spread (`iqr`). Decision variance
    dominating is what licenses reading the multiverse as a statement about
    the analysis rather than about the agent.
    """
    by_agent: dict[str, list[float]] = defaultdict(list)
    for u in per_universe:
        if u.agent:
            by_agent[u.agent].append(u.surprisal)
    if len(by_agent) < 2:
        return None
    medians = [statistics.median(v) for v in by_agent.values()]
    return max(medians) - min(medians)
