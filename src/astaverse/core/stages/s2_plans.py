"""s2 — plans: StudySpec -> K sampled analysis plans.

K independent samples at temperature, so that where the plans *disagree* is
informative about which analytic choices are genuinely open. Plan shape
mirrors asta-autodiscovery's ExperimentPlan (objective / steps / deliverables)
so plans round-trip with the existing `query` convention.

A plan can also be **seeded** — supplied rather than sampled. That is the
mode that matters for evaluating AutoDiscovery: the multiverse should cover
the decision space of the plan actually under evaluation, not of plans
invented from scratch. A seeded plan is included verbatim as `plan_00`, and
the sampled plans are drawn as alternatives to it.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

from ...integrations.llm import DEFAULT_PLAN_MODEL, structured_call
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


SEEDED_SUFFIX = """\

## An existing plan for this same hypothesis

{seed}

Write a plan that is a genuine alternative to the one above: same hypothesis,
same data, but make the analytic choices you would defend, whether or not they
match. Do not critique the existing plan; just write yours.
"""


class _PlanResponse(BaseModel):
    objective: str = Field(description="One sentence on what this analysis establishes")
    steps: str = Field(description="Concrete analytic steps, in order")
    deliverables: str = Field(description="The specific numbers this analysis must report")
    rationale: str = Field(description="Why these analytic choices")


def load_seed_plan(
    text: str | None = None,
    jsonl: str | Path | None = None,
    normalized_id: str | None = None,
) -> str | None:
    """Resolve a seed plan from raw text or an AutoDiscovery plans jsonl.

    The jsonl form reads the `query` field of a record in
    `data/plans/01_normalized/<dataset>.jsonl` — that field *is* the
    experiment plan in AutoDiscovery's own format.
    """
    if text:
        return text
    if not jsonl:
        return None
    path = Path(jsonl)
    records = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if normalized_id:
        matches = [r for r in records if r.get("normalized_id") == normalized_id]
        if not matches:
            available = ", ".join(r.get("normalized_id", "?") for r in records[:3])
            raise ValueError(
                f"no record '{normalized_id}' in {path} (first ids: {available}, …)"
            )
        record = matches[0]
    else:
        record = records[0]
    query = record.get("query")
    if not query:
        raise ValueError(f"record {record.get('normalized_id')} has no `query` field")
    return query


def run(
    run_obj: Run,
    k: int = 5,
    model: str | None = None,
    temperature: float = 0.9,
    seed_plan: str | None = None,
) -> PlanSet:
    """Sample K plans. With `seed_plan`, it is kept verbatim and K-1 are drawn."""
    model = model or DEFAULT_PLAN_MODEL
    study: StudySpec = run_obj.read_artifact("study", StudySpec)

    prompt = PROMPT.format(
        hypothesis=study.hypothesis,
        dataset_name=study.dataset_name,
        n_rows=study.n_rows,
        dataset_description=study.dataset_description or "(no description available)",
        columns=render_columns_markdown(study),
    )
    n_sampled = k
    if seed_plan:
        prompt += SEEDED_SUFFIX.format(seed=seed_plan)
        n_sampled = max(k - 1, 1)

    responses = structured_call(
        prompt,
        _PlanResponse,
        model,
        system=SYSTEM,
        temperature=temperature,
        n=n_sampled,
        log_dir=run_obj.root,
        tag="s2_plans",
    )

    plans: list[Plan] = []
    if seed_plan:
        plans.append(
            Plan(
                id="plan_00",
                objective="(seeded plan, supplied verbatim)",
                steps=seed_plan,
                deliverables="As stated in the plan text.",
                rationale="Supplied rather than sampled; this is the plan under evaluation.",
                seeded=True,
            )
        )
    for r in responses:
        plans.append(
            Plan(
                id=f"plan_{len(plans):02d}",
                objective=r.objective,
                steps=r.steps,
                deliverables=r.deliverables,
                rationale=r.rationale,
            )
        )

    plan_set = PlanSet(plans=plans, model=model, temperature=temperature)

    run_obj.write_artifact("plans", plan_set)
    run_obj.record_stage(
        "plans", k=len(plans), model=model, temperature=temperature, seeded=bool(seed_plan)
    )
    run_obj.log(
        "plans",
        f"{'seeded + ' if seed_plan else ''}sampled {len(plans)} plans from {model}",
    )
    return plan_set
