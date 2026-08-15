"""s2 — plans: StudySpec -> K sampled analysis plans.

K independent samples at temperature, so that where the plans *disagree* is
informative about which analytic choices are genuinely open. Plan shape
mirrors asta-autodiscovery's ExperimentPlan (objective / steps / deliverables)
so plans round-trip with the existing `query` convention.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from ..llm import DEFAULT_PLAN_MODEL, structured_call
from ..schemas import Plan, PlanSet, StudySpec
from ..store import Run
from .s1_study import render_columns_markdown

SYSTEM = (
    "You are an experienced data analyst. You design concrete, executable "
    "analysis plans for testing a scientific hypothesis on tabular data."
)

PROMPT = """\
Design ONE analysis plan to test the hypothesis below on the dataset described.

## Hypothesis
{hypothesis}

## Dataset: {dataset_name} ({n_rows} rows)
{dataset_description}

{columns}

## What to produce
A plan another analyst could execute without asking you questions:

- `objective`: one sentence on what this analysis establishes.
- `steps`: the concrete analytic steps — variable construction, filtering,
  transformations, the statistical model, and how significance is judged.
- `deliverables`: the specific numbers this analysis must report.
- `rationale`: why you made the analytic choices you did.

Commit to specific choices rather than listing alternatives. Where a choice is
genuinely arbitrary, make it and say so in the rationale. Write the plan you
think is best — do not try to be unusual.
"""


class _PlanResponse(BaseModel):
    objective: str = Field(description="One sentence on what this analysis establishes")
    steps: str = Field(description="Concrete analytic steps, in order")
    deliverables: str = Field(description="The specific numbers this analysis must report")
    rationale: str = Field(description="Why these analytic choices")


def run(
    run_obj: Run,
    k: int = 5,
    model: str | None = None,
    temperature: float = 0.9,
) -> PlanSet:
    model = model or DEFAULT_PLAN_MODEL
    study: StudySpec = run_obj.read_artifact("study", StudySpec)

    prompt = PROMPT.format(
        hypothesis=study.hypothesis,
        dataset_name=study.dataset_name,
        n_rows=study.n_rows,
        dataset_description=study.dataset_description or "(no description available)",
        columns=render_columns_markdown(study),
    )

    responses = structured_call(
        prompt,
        _PlanResponse,
        model,
        system=SYSTEM,
        temperature=temperature,
        n=k,
        log_dir=run_obj.root,
        tag="s2_plans",
    )

    plan_set = PlanSet(
        plans=[
            Plan(
                id=f"plan_{i:02d}",
                objective=r.objective,
                steps=r.steps,
                deliverables=r.deliverables,
                rationale=r.rationale,
            )
            for i, r in enumerate(responses)
        ],
        model=model,
        temperature=temperature,
    )

    run_obj.write_artifact("plans", plan_set)
    run_obj.record_stage("plans", k=len(plan_set.plans), model=model, temperature=temperature)
    run_obj.log("plans", f"sampled {len(plan_set.plans)} plans from {model} @ T={temperature}")
    return plan_set
