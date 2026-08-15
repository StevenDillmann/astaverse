"""s3 — decision extraction: K plans -> an ASTRA-shaped decision space.

The novel stage. K plans written independently will silently disagree about
choices none of them flags as a choice; those disagreements are the decision
axes. The model is asked to find them, and the result is emitted as
`03_astra.yaml`.

Two deliberate design points:

* By default this runs on a *different* model than plan generation. One model
  doing both can systematically miss forks it never entertains.
* A `verdict_rule` decision is always injected. The experiments repo found the
  verdict decision rule to be an under-specification that never gets resolved,
  distinct from under-specified computation. It is marked `post_hoc`, so it
  costs nothing to execute: it is applied downstream to the reported numbers.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from ..astra_io import write_astra_yaml
from ..llm import DEFAULT_DECISION_MODEL, structured_call
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

SYSTEM = (
    "You are a methodologist who audits analysis plans for hidden degrees of "
    "freedom. You find the points where reasonable analysts would diverge."
)

PROMPT = """\
Below are {k} independent analysis plans, each written to test the same
hypothesis on the same dataset. Your job is to find the **analytic decisions**:
the points where the plans disagree, or where a plan silently commits to one
choice without acknowledging the alternatives.

## Hypothesis
{hypothesis}

## Dataset: {dataset_name} ({n_rows} rows)
{columns}

## The plans
{plans}

## What to produce
A list of decisions. For each one:

- `id`: snake_case identifier, e.g. `min_pressure_direction`.
- `label`: short human-readable name.
- `question`: the choice, phrased as a question an analyst would have to answer.
- `kind`: one of `preprocessing`, `variable_choice`, `model`, `inference`.
- `options`: two or more concrete, executable alternatives. Each needs an
  `id`, a `label`, and a `description` precise enough to implement directly.
- `default_option_id`: the option the plans most commonly assume — the choice
  a single analyst would probably have made without thinking about it.
- `supported_by`: the plan ids (e.g. `plan_00`) whose text supports each option.
- `consequential`: your honest guess at whether this choice could change the
  conclusion.

Rules:

- Only include decisions that could plausibly change the reported numbers.
  Cosmetic choices (plot colours, variable naming, report ordering) are not
  decisions.
- A decision found in only ONE plan is still a real decision. Record the
  narrow support in `supported_by`; do not drop it for lack of consensus.
- **A majority is not a resolution.** If any plan handles a step differently
  from the others — even if the others agree, and even if their way is
  clearly the methodologically correct one — that is a decision. You are not
  adjudicating which plan is right; you are cataloguing what varies so its
  effect can be measured. Recording a choice costs little; omitting one hides
  a result's dependence on it.
- Pay specific attention to steps where plans differ in the **orientation or
  sign** of a variable (reversing, inverting, negating, or flipping a measure
  before combining it with others), in whether a step happens **at all**
  (a filter, transformation, or control one plan applies and another omits),
  and in **how a composite or index is constructed** from components. These
  are the choices most often left unstated, and they are frequently the ones
  that move the conclusion.
- **Silence is under-specification, and it counts.** The most consequential
  decisions usually are not stated disagreements — they are steps a plan
  describes at a level of detail that leaves an implementer a real choice.
  If a plan says "combine these variables into an index" without saying how
  they are oriented, or "adjust for severity" without saying with what, or
  "remove outliers" without saying which, then two competent implementers
  would write different code, and that gap is a decision. Enumerate the
  options an implementer would actually pick between, and set
  `supported_by: []` when no plan states a preference.{seed_note}
- Options must be mutually exclusive and jointly cover what the plans do.
- Prefer 2-4 options per decision, and at most {max_decisions} decisions.
- Use `requires` / `incompatible_with` (referencing "decision_id.option_id")
  only where a combination is genuinely impossible, not merely unusual.
- Do NOT include a decision about the significance threshold or how to word
  the final verdict. That is handled separately.
"""


SEED_NOTE = """
- **{seed_id} is the plan under evaluation** — it was supplied, not sampled.
  Audit it specifically: walk its steps and ask, at each one, what an
  implementer would still have to decide to turn that sentence into code. Where
  the other plans spell out something it leaves implicit, that gap is a
  decision, and the fact that the others agree does not close it."""


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


def _verdict_rule_decision() -> Decision:
    """The always-injected verdict rule.

    Marked post_hoc: no analysis code branches on it, so it multiplies the
    universe count at zero execution cost. Applied in s7 to the same numbers.
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
                    "Significant at 5% AND the estimate points the way the "
                    "hypothesis predicts; a significant effect in the opposite "
                    "direction counts as not supported."
                ),
            ),
        },
    )


def run(
    run_obj: Run,
    model: str | None = None,
    max_decisions: int = 6,
) -> DecisionSpec:
    model = model or DEFAULT_DECISION_MODEL
    study: StudySpec = run_obj.read_artifact("study", StudySpec)
    plan_set: PlanSet = run_obj.read_artifact("plans", PlanSet)

    rendered_plans = "\n\n".join(
        f"### {p.id}{' — THE PLAN UNDER EVALUATION' if p.seeded else ''}\n"
        f"**Objective:** {p.objective}\n\n**Steps:**\n{p.steps}\n\n"
        f"**Deliverables:**\n{p.deliverables}\n\n**Rationale:** {p.rationale or ''}"
        for p in plan_set.plans
    )

    seeded = next((p for p in plan_set.plans if p.seeded), None)
    prompt = PROMPT.format(
        k=len(plan_set.plans),
        hypothesis=study.hypothesis,
        dataset_name=study.dataset_name,
        n_rows=study.n_rows,
        columns=render_columns_markdown(study),
        plans=rendered_plans,
        max_decisions=max_decisions,
        seed_note=SEED_NOTE.format(seed_id=seeded.id) if seeded else "",
    )

    response = structured_call(
        prompt,
        _DecisionSpaceResponse,
        model,
        system=SYSTEM,
        log_dir=run_obj.root,
        tag="s3_decisions",
    )[0]

    decisions: dict[str, Decision] = {}
    for item in response.decisions[:max_decisions]:
        if len(item.options) < 2:
            run_obj.log("decisions", f"dropped '{item.id}': fewer than 2 options")
            continue
        options = {
            opt.id: Option(
                label=opt.label,
                description=opt.description,
                requires=opt.requires,
                incompatible_with=opt.incompatible_with,
                supported_by=opt.supported_by,
            )
            for opt in item.options
        }
        default = item.default_option_id if item.default_option_id in options else next(iter(options))
        if default != item.default_option_id:
            run_obj.log(
                "decisions",
                f"'{item.id}': default '{item.default_option_id}' is not an option; using '{default}'",
            )
        try:
            kind = DecisionKind(item.kind)
        except ValueError:
            kind = DecisionKind.preprocessing
        if kind is DecisionKind.verdict_rule:
            # Verdict rules are injected below, not taken from the model.
            run_obj.log("decisions", f"dropped '{item.id}': verdict rules are injected")
            continue
        decisions[item.id] = Decision(
            label=item.label,
            rationale=item.question,
            default=default,
            options=options,
            kind=kind,
        )

    decisions["verdict_rule"] = _verdict_rule_decision()

    spec = DecisionSpec(
        id=f"{study.dataset_name}_multiverse",
        name=f"{study.dataset_name}: multiverse analysis",
        description=f"Decision space extracted from {len(plan_set.plans)} sampled plans.",
        hypothesis=study.hypothesis,
        dataset_path=study.dataset_path,
        decisions=decisions,
    )

    write_astra_yaml(spec, run_obj.artifact_path("decisions"))
    n_exec = len(spec.execution_decisions())
    run_obj.record_stage(
        "decisions",
        model=model,
        n_decisions=len(decisions),
        n_execution_decisions=n_exec,
    )
    run_obj.log(
        "decisions",
        f"extracted {n_exec} execution decisions (+1 verdict rule) from "
        f"{len(plan_set.plans)} plans using {model}",
    )
    return spec
