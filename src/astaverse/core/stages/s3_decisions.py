"""s3 — decision extraction: find the analytic forks.

Three strategies, because they look at different artifacts:

* `sample_plans` sample K plans, extract where they disagree.
* `audit_plan`   one plan, extract every choice an implementer still has to make.
* `direct`      hypothesis + dataset only, no plans.

`critique` composes with any of them: a second pass asking what is missing.
A `verdict_rule` decision is always injected afterwards — it is an
under-specification that never gets resolved in the plan, and it costs
nothing to execute since it is post-hoc.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from pydantic import BaseModel, Field

from ...integrations.astra_io import write_astra_yaml
from ...integrations.llm import DEFAULT_DECISION_MODEL, structured_call
from ..config import normalize_extraction_mode
from ..schemas import (
    Decision,
    DecisionKind,
    DecisionSpec,
    Option,
    PlanSet,
    StudySpec,
)
from ..store import Run
from .s1_study import render_columns_markdown


class ExtractionMode(str, Enum):
    sample_plans = "sample_plans"
    audit_plan = "audit_plan"
    direct = "direct"


#: Modes that need stage 2 to have run.
NEEDS_PLANS = {ExtractionMode.sample_plans, ExtractionMode.audit_plan}


# --------------------------------------------------------------------------
# response schema, shared by every mode
# --------------------------------------------------------------------------


class _OptionResponse(BaseModel):
    id: str
    label: str
    description: str
    supported_by: list[str] = Field(default_factory=list)
    requires: list[str] = Field(default_factory=list)
    incompatible_with: list[str] = Field(default_factory=list)


class _DecisionResponse(BaseModel):
    id: str
    label: str
    question: str
    kind: str
    options: list[_OptionResponse]
    default_option_id: str
    consequential: bool = True


class _DecisionSpaceResponse(BaseModel):
    decisions: list[_DecisionResponse]


@dataclass
class Context:
    """Everything the prompts can draw on."""

    study: StudySpec
    plans: PlanSet | None
    max_decisions: int

    @property
    def columns(self) -> str:
        return render_columns_markdown(self.study)

    @property
    def rendered_plans(self) -> str:
        if not self.plans:
            return "(no plans were sampled)"
        return "\n\n".join(
            f"### {p.id}{' — THE PLAN UNDER EVALUATION' if p.seeded else ''}\n"
            f"**Objective:** {p.objective}\n\n**Steps:**\n{p.steps}\n\n"
            f"**Deliverables:**\n{p.deliverables}\n\n**Rationale:** {p.rationale or ''}"
            for p in self.plans.plans
        )

    @property
    def primary_plan(self):
        if not self.plans or not self.plans.plans:
            return None
        return next((p for p in self.plans.plans if p.seeded), self.plans.plans[0])


SYSTEM = (
    "You are a methodologist who audits analyses for hidden degrees of "
    "freedom. You find the points where reasonable analysts would diverge."
)

COMMON_RULES = """\
Rules:

- Only include decisions that could plausibly change the reported numbers.
  Cosmetic choices (plot colours, naming, report ordering) are not decisions.
- Options must be mutually exclusive, and each needs a `description` precise
  enough to implement directly without further interpretation.
- Prefer 2-4 options per decision, and at most {max_decisions} decisions.
- `default_option_id` is the choice an analyst would most likely make without
  thinking about it — the one a single-universe pipeline would land on.
- Use `requires` / `incompatible_with` (referencing "decision_id.option_id")
  only where a combination is genuinely impossible, not merely unusual.
- Do NOT propose a decision about the significance threshold or how to word
  the verdict. That is handled separately.
"""

OUTPUT_SPEC = """\
For each decision give: `id` (snake_case), `label`, `question` (the choice as
a question), `kind` (one of `preprocessing`, `variable_choice`, `model`,
`inference`), `options` (each with `id`, `label`, `description`,
`supported_by` = the plan ids supporting it, empty if none state a
preference), `default_option_id`, and `consequential` (your honest guess at
whether it could change the conclusion).
"""


# --------------------------------------------------------------------------
# modes
# --------------------------------------------------------------------------


PLAN_DIFF_PROMPT = """\
Below are {k} independent analysis plans, each written to test the same
hypothesis on the same dataset. Find the **analytic decisions**: points where
the plans disagree, or where a plan silently commits to one choice without
acknowledging the alternatives.

## Hypothesis
{hypothesis}

## Dataset: {dataset_name} ({n_rows} rows)
{columns}

## The plans
{plans}

{output_spec}
{rules}
- **A majority is not a resolution.** If any plan handles a step differently
  from the others — even if the others agree, and even if their way is
  clearly correct — that is a decision. You are cataloguing what varies so
  its effect can be measured, not adjudicating who is right.
- A decision found in only ONE plan is still a decision. Record the narrow
  support; do not drop it for lack of consensus.
"""

PLAN_AUDIT_PROMPT = """\
Below is one analysis plan. Audit it for **under-specification**: walk its
steps and ask, at each one, what an implementer would still have to decide in
order to turn that sentence into code.

## Hypothesis
{hypothesis}

## Dataset: {dataset_name} ({n_rows} rows)
{columns}

## The plan
{plan}

{output_spec}
{rules}
- **Silence is the target here.** You are not looking for what the plan says;
  you are looking for what it does not say. "Combine these variables into an
  index" does not state how they are oriented. "Adjust for severity" does not
  state with what. "Remove outliers" does not state which. Two competent
  implementers would write different code, and each such gap is a decision.
- Set `supported_by` to an empty list when the plan states no preference —
  that is the normal case for this mode, not a failure.
"""

DIRECT_PROMPT = """\
Given only a hypothesis and a dataset, enumerate the **analytic decisions**
that testing this hypothesis would require. No analysis plan exists yet; you
are predicting where analysts would diverge.

## Hypothesis
{hypothesis}

## Dataset: {dataset_name} ({n_rows} rows)
{description}

{columns}

{output_spec}
{rules}
- Ground each decision in this specific dataset and hypothesis. Name the
  actual columns involved. Generic methodology ("choose a model") is useless
  unless you say which models and which variables.
"""

CRITIQUE_PROMPT = """\
Here is a decision space that was extracted for the study below. Your job is
to find what is MISSING.

## Hypothesis
{hypothesis}

## Dataset: {dataset_name} ({n_rows} rows)
{columns}

## Decisions found so far
{existing}

Return ONLY decisions that are genuinely absent from the list above — do not
restate or rephrase what is already there. Look especially for:

- a variable that must be oriented, reversed, or aligned before being combined
- a step the analysis needs that nobody has mentioned at all
- a choice buried inside a step that is described as though it were atomic

If nothing important is missing, return an empty list. An empty list is a
perfectly good answer and better than padding.

{output_spec}
{rules}
"""


def _call(prompt: str, model: str, run_obj: Run, tag: str) -> list[_DecisionResponse]:
    response = structured_call(
        prompt,
        _DecisionSpaceResponse,
        model,
        system=SYSTEM,
        log_dir=run_obj.root,
        tag=tag,
    )[0]
    return list(response.decisions)


def _run_mode(
    mode: ExtractionMode, ctx: Context, model: str, run_obj: Run
) -> list[_DecisionResponse]:
    common = {
        "hypothesis": ctx.study.hypothesis,
        "dataset_name": ctx.study.dataset_name,
        "n_rows": ctx.study.n_rows,
        "columns": ctx.columns,
        "description": ctx.study.dataset_description or "",
        "output_spec": OUTPUT_SPEC,
        "rules": COMMON_RULES.format(max_decisions=ctx.max_decisions),
    }

    if mode is ExtractionMode.sample_plans:
        if not ctx.plans:
            raise ValueError("method 'sample_plans' needs the plans stage to have run")
        prompt = PLAN_DIFF_PROMPT.format(
            k=len(ctx.plans.plans), plans=ctx.rendered_plans, **common
        )
    elif mode is ExtractionMode.audit_plan:
        plan = ctx.primary_plan
        if plan is None:
            raise ValueError("method 'audit_plan' needs the plans stage to have run")
        rendered = (
            f"**Objective:** {plan.objective}\n\n**Steps:**\n{plan.steps}\n\n"
            f"**Deliverables:**\n{plan.deliverables}"
        )
        prompt = PLAN_AUDIT_PROMPT.format(plan=rendered, **common)
    elif mode is ExtractionMode.direct:
        prompt = DIRECT_PROMPT.format(**common)
    else:
        raise ValueError(f"unknown extraction mode '{mode}'")

    return _call(prompt, model, run_obj, f"s3_{mode.value}")


def _critique(
    ctx: Context, found: list[_DecisionResponse], model: str, run_obj: Run
) -> list[_DecisionResponse]:
    existing = "\n".join(
        f"- {d.id} ({d.kind}): {d.question} — options: "
        + ", ".join(o.id for o in d.options)
        for d in found
    ) or "(none)"
    prompt = CRITIQUE_PROMPT.format(
        hypothesis=ctx.study.hypothesis,
        dataset_name=ctx.study.dataset_name,
        n_rows=ctx.study.n_rows,
        columns=ctx.columns,
        existing=existing,
        output_spec=OUTPUT_SPEC,
        rules=COMMON_RULES.format(max_decisions=ctx.max_decisions),
    )
    return _call(prompt, model, run_obj, "s3_critique")


# --------------------------------------------------------------------------
# merging
# --------------------------------------------------------------------------


def _merge(
    batches: list[tuple[str, list[_DecisionResponse]]],
) -> tuple[list[_DecisionResponse], dict[str, list[str]]]:
    """Merge decisions from several passes, keyed by id.

    Union the options rather than taking the first batch's, so a second
    model or a critique pass that finds an extra option still contributes.
    Records which passes proposed each decision.
    """
    merged: dict[str, _DecisionResponse] = {}
    provenance: dict[str, list[str]] = {}

    for source, decisions in batches:
        for d in decisions:
            key = d.id.strip().lower()
            if key not in merged:
                merged[key] = d
                provenance[key] = [source]
                continue
            provenance[key].append(source)
            existing = merged[key]
            have = {o.id for o in existing.options}
            existing.options.extend(o for o in d.options if o.id not in have)

    return list(merged.values()), provenance


def _verdict_rule_decision() -> Decision:
    """Always injected: how statistics become a verdict.

    Marked post_hoc, so no analysis code branches on it and it multiplies the
    analysed universes at zero execution cost.
    """
    return Decision(
        label="Verdict decision rule",
        rationale=(
            "How the reported statistics become a supported / not-supported verdict. "
            "Left implicit by every plan, and consequential on its own."
        ),
        default="alpha_05_two_sided",
        kind=DecisionKind.verdict_rule,
        post_hoc=True,
        options={
            "alpha_05_two_sided": Option(
                label="p < 0.05, two-sided",
                description="Conventional two-sided test at the 5% level.",
            ),
            "alpha_01_two_sided": Option(
                label="p < 0.01, two-sided",
                description="Stricter two-sided threshold at the 1% level.",
            ),
            "alpha_05_directional": Option(
                label="p < 0.05 and direction matches",
                description=(
                    "Significant at 5% AND the estimate points the way the hypothesis "
                    "predicts; a significant effect the other way counts as not supported."
                ),
            ),
        },
    )


# --------------------------------------------------------------------------
# the stage
# --------------------------------------------------------------------------


def run(
    run_obj: Run,
    model: str | None = None,
    max_decisions: int = 6,
    mode: str | ExtractionMode = ExtractionMode.sample_plans,
    models: list[str] | None = None,
    critique: bool = False,
) -> DecisionSpec:
    """Extract the decision space.

    `models` with more than one entry runs the mode once per model and merges
    the results, covering one model's blind spots.
    """
    mode = ExtractionMode(normalize_extraction_mode(mode))
    model_list = models or [model or DEFAULT_DECISION_MODEL]

    study: StudySpec = run_obj.read_artifact("study", StudySpec)
    plans: PlanSet | None = None
    if run_obj.artifact_path("plans").exists():
        plans = run_obj.read_artifact("plans", PlanSet)

    if mode in NEEDS_PLANS and plans is None:
        raise ValueError(
            f"mode '{mode.value}' needs stage 2 (plans); run it, or use "
            "'direct', which does not"
        )

    ctx = Context(study=study, plans=plans, max_decisions=max_decisions)

    batches: list[tuple[str, list[_DecisionResponse]]] = []
    for mdl in model_list:
        source = mode.value if len(model_list) == 1 else f"{mode.value}@{mdl}"
        batches.append((source, _run_mode(mode, ctx, mdl, run_obj)))

    found, provenance = _merge(batches)

    if critique:
        extra = _critique(ctx, found, model_list[0], run_obj)
        if extra:
            found, provenance = _merge(
                [("merged", found), ("critique", extra)]
            )
            run_obj.log("decisions", f"critique added {len(extra)} candidate decisions")

    # Build the spec.
    decisions: dict[str, Decision] = {}
    for item in found:
        if len(decisions) >= max_decisions:
            run_obj.log("decisions", f"dropped '{item.id}': at max_decisions={max_decisions}")
            continue
        if len(item.options) < 2:
            run_obj.log("decisions", f"dropped '{item.id}': fewer than 2 options")
            continue
        try:
            kind = DecisionKind(item.kind)
        except ValueError:
            kind = DecisionKind.preprocessing
        if kind is DecisionKind.verdict_rule:
            run_obj.log("decisions", f"dropped '{item.id}': verdict rules are injected")
            continue

        options = {
            o.id: Option(
                label=o.label,
                description=o.description,
                requires=o.requires,
                incompatible_with=o.incompatible_with,
                supported_by=o.supported_by,
            )
            for o in item.options
        }
        default = (
            item.default_option_id
            if item.default_option_id in options
            else next(iter(options))
        )
        if default != item.default_option_id:
            run_obj.log(
                "decisions",
                f"'{item.id}': default '{item.default_option_id}' is not an option; "
                f"using '{default}'",
            )
        key = item.id.strip().lower()
        rationale = item.question
        sources = provenance.get(key, [])
        if sources:
            rationale += f"  [found by: {', '.join(sorted(set(sources)))}]"
        decisions[item.id] = Decision(
            label=item.label,
            rationale=rationale,
            default=default,
            options=options,
            kind=kind,
        )

    decisions["verdict_rule"] = _verdict_rule_decision()

    spec = DecisionSpec(
        id=f"{study.dataset_name}_multiverse",
        name=f"{study.dataset_name}: multiverse analysis",
        description=(
            f"Decision space extracted by mode '{mode.value}'"
            + (f" across {len(model_list)} models" if len(model_list) > 1 else "")
            + (" with a critique pass" if critique else "")
            + "."
        ),
        hypothesis=study.hypothesis,
        dataset_path=study.dataset_path,
        decisions=decisions,
    )

    write_astra_yaml(spec, run_obj.artifact_path("decisions"))
    n_exec = len(spec.execution_decisions())
    run_obj.record_stage(
        "decisions",
        mode=mode.value,
        models=model_list,
        critique=critique,
        n_decisions=len(decisions),
        n_execution_decisions=n_exec,
    )
    run_obj.log(
        "decisions",
        f"mode={mode.value} models={','.join(model_list)}"
        f"{' +critique' if critique else ''} -> {n_exec} execution decisions",
    )
    return spec
