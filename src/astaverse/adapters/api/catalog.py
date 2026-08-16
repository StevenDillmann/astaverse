"""What you can start an analysis from, and how the tool can be configured.

Everything here is static or derived from the environment — no analysis
required. The config schema in particular is what lets the UI render its form
from the same definition the CLI generates its flags from.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from ...core import config as run_cfg
from ...core.store import STAGES
from ...integrations import datasets, plans_index

router = APIRouter(prefix="/api", tags=["catalog"])


@router.get("/stages")
def list_stages() -> list[str]:
    return STAGES


@router.get("/config-schema")
def config_schema() -> dict[str, Any]:
    """The configuration schema, for rendering the UI form.

    The same pydantic model generates the CLI flags, so a knob added here
    appears in both surfaces without either being edited.
    """
    return run_cfg.json_schema()


@router.get("/datasets")
def list_datasets() -> list[dict[str, Any]]:
    out = []
    for d in datasets.discover():
        entry = d.to_dict()
        entry["n_autodiscovery_hypotheses"] = plans_index.count_for_dataset(d.name)
        out.append(entry)
    return out


@router.get("/datasets/{name}/hypotheses")
def list_hypotheses(name: str, q: str = "", limit: int = 300) -> dict[str, Any]:
    """AutoDiscovery's own hypotheses for a dataset.

    A BLADE dataset carries one published research question; AutoDiscovery has
    generated hundreds against the same data, each with the plan it produced.
    """
    records = plans_index.for_dataset(name)
    if q:
        needle = q.lower()
        records = [r for r in records if needle in r.hypothesis.lower()]
    return {
        "dataset": name,
        "total": plans_index.count_for_dataset(name),
        "matched": len(records),
        "hypotheses": [r.to_dict() for r in records[:limit]],
    }


@router.get("/extraction-modes")
def list_extraction_modes() -> list[dict[str, Any]]:
    """Stage-3 strategies, each with what it is blind to.

    Surfaced separately from the schema because choosing one is a
    methodological decision, not a preference, and the tradeoff should be
    visible at the point of choosing.
    """
    blurbs = {
        "plan_diff": (
            "Where K sampled plans disagree. Grounded in what analysts do; "
            "blind to steps no plan mentions at all."
        ),
        "plan_audit": (
            "One plan, audited for what it leaves an implementer to decide. "
            "Targets under-specification by silence; no disagreement signal."
        ),
        "direct": (
            "Hypothesis and schema only, no plans. Cheapest; tends toward "
            "textbook axes rather than ones this study would hit."
        ),
        "schema_lint": (
            "What the data itself forces — orientation, scale, missingness. "
            "Catches forks that appear in code but never in plan text."
        ),
        "union": (
            "Several modes merged. The blind spots differ, so the union covers "
            "more than any single mode; costs one call per mode."
        ),
    }
    schema = run_cfg.json_schema()
    modes = schema["$defs"]["DecisionsConfig"]["properties"]["mode"]["enum"]
    return [
        {
            "id": m,
            "description": blurbs.get(m, ""),
            "needs_plans": m in {"plan_diff", "plan_audit"},
        }
        for m in modes
    ]
