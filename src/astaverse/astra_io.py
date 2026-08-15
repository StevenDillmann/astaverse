"""ASTRA-shaped YAML emission, loading, and grid enumeration.

The emitted `astra.yaml` mirrors the ASTRA specification's structure
(inputs / outputs / decisions / prior_insights) closely enough that adopting
`astra-tools` later should be a validate-and-fix, not a rewrite. We do not
depend on it yet — see the adoption stance in the README.

Constraint semantics follow ASTRA's `requires` / `incompatible_with`, which
reference options as "<decision_id>.<option_id>".
"""

from __future__ import annotations

import itertools
from pathlib import Path
from typing import Iterable

import yaml

from .schemas import ASTRA_SCHEMA_SHAPE, Decision, DecisionSpec, Universe, UniverseSet


# --------------------------------------------------------------------------
# emit / load
# --------------------------------------------------------------------------


def spec_to_astra_dict(spec: DecisionSpec) -> dict:
    """Render a DecisionSpec as an ASTRA-shaped mapping."""
    decisions: dict[str, dict] = {}
    for did, decision in spec.decisions.items():
        options: dict[str, dict] = {}
        for oid, option in decision.options.items():
            entry: dict = {"label": option.label}
            if option.description:
                entry["description"] = option.description
            if option.requires:
                entry["requires"] = list(option.requires)
            if option.incompatible_with:
                entry["incompatible_with"] = list(option.incompatible_with)
            options[oid] = entry
        block: dict = {"label": decision.label}
        if decision.rationale:
            block["rationale"] = decision.rationale
        block["default"] = decision.default
        block["options"] = options
        # Astaverse extensions live under x_astaverse so the rest of the
        # document stays clean ASTRA.
        block["x_astaverse"] = {
            "kind": decision.kind.value,
            "post_hoc": decision.post_hoc,
            "option_support": {
                oid: list(opt.supported_by) for oid, opt in decision.options.items()
            },
        }
        decisions[did] = block

    return {
        "id": spec.id,
        "name": spec.name,
        "description": spec.description or "",
        "inputs": [
            {
                "id": "dataset",
                "type": "data",
                "source": spec.dataset_path,
                "description": "Primary dataset under analysis",
            }
        ],
        "outputs": [
            {
                "id": "universe_stats",
                "type": "table",
                "description": (
                    "Per-universe statistics (estimate, std_error, p_value, n, direction). "
                    "Carries no verdict by design: verdicts are assigned downstream."
                ),
                "inputs": ["dataset"],
                "decisions": sorted(spec.execution_decisions()),
                "recipe": {"command": "python /app/analysis.py"},
            }
        ],
        "decisions": decisions,
        "prior_insights": {
            "hypothesis": {
                "id": "hypothesis",
                "label": "Hypothesis under test",
                "claim": spec.hypothesis,
            }
        },
        "x_astaverse": {
            "astra_schema_shape": ASTRA_SCHEMA_SHAPE,
            "note": (
                "ASTRA-shaped, emitted by astaverse without astra-tools. "
                "Run `astra validate` to check conformance."
            ),
        },
    }


def write_astra_yaml(spec: DecisionSpec, path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(spec_to_astra_dict(spec), sort_keys=False, width=100))
    return path


def read_astra_yaml(path: Path) -> DecisionSpec:
    """Load an astra.yaml back into a DecisionSpec.

    Tolerates hand-written files that omit the x_astaverse extensions, so a
    spec can be authored by hand and dropped in to skip plan generation and
    decision extraction entirely.
    """
    raw = yaml.safe_load(Path(path).read_text())
    decisions: dict[str, dict] = {}
    for did, block in (raw.get("decisions") or {}).items():
        ext = block.get("x_astaverse") or {}
        support = ext.get("option_support") or {}
        options: dict[str, dict] = {}
        for oid, opt in (block.get("options") or {}).items():
            options[oid] = {
                "label": opt.get("label", oid),
                "description": opt.get("description"),
                "requires": opt.get("requires") or [],
                "incompatible_with": opt.get("incompatible_with") or [],
                "supported_by": support.get(oid) or [],
            }
        decisions[did] = {
            "label": block.get("label", did),
            "rationale": block.get("rationale"),
            "default": block.get("default") or next(iter(options)),
            "options": options,
            "kind": ext.get("kind", "preprocessing"),
            "post_hoc": ext.get("post_hoc", False),
        }

    inputs = raw.get("inputs") or [{}]
    hypothesis = ((raw.get("prior_insights") or {}).get("hypothesis") or {}).get("claim", "")
    return DecisionSpec.model_validate(
        {
            "id": raw.get("id", "analysis"),
            "name": raw.get("name", raw.get("id", "analysis")),
            "description": raw.get("description"),
            "hypothesis": hypothesis,
            "dataset_path": inputs[0].get("source", ""),
            "decisions": decisions,
            "astra_schema_shape": (raw.get("x_astaverse") or {}).get(
                "astra_schema_shape", ASTRA_SCHEMA_SHAPE
            ),
        }
    )


# --------------------------------------------------------------------------
# constraints + grid enumeration
# --------------------------------------------------------------------------


def _parse_ref(ref: str) -> tuple[str, str] | None:
    """Parse an ASTRA option reference "<decision_id>.<option_id>"."""
    if "." not in ref:
        return None
    did, _, oid = ref.partition(".")
    return did.strip(), oid.strip()


def satisfies_constraints(
    selections: dict[str, str], decisions: dict[str, Decision]
) -> bool:
    """Check one grid point against every selected option's requires/incompatible_with.

    Constraints referencing a decision that is not part of this grid are
    ignored rather than treated as violations — a spec may legitimately
    constrain against a decision the user excluded.
    """
    for did, oid in selections.items():
        decision = decisions.get(did)
        if decision is None:
            continue
        option = decision.options.get(oid)
        if option is None:
            return False
        for ref in option.requires:
            parsed = _parse_ref(ref)
            if parsed is None:
                continue
            req_did, req_oid = parsed
            if req_did in selections and selections[req_did] != req_oid:
                return False
        for ref in option.incompatible_with:
            parsed = _parse_ref(ref)
            if parsed is None:
                continue
            bad_did, bad_oid = parsed
            if selections.get(bad_did) == bad_oid:
                return False
    return True


def default_selections(decisions: dict[str, Decision]) -> dict[str, str]:
    return {did: d.default for did, d in decisions.items()}


def enumerate_universes(
    decisions: dict[str, Decision],
    cap: int | None = 24,
    include: Iterable[str] | None = None,
    exclude: Iterable[str] | None = None,
) -> UniverseSet:
    """Enumerate the decision grid, honouring constraints and a cap.

    The default-option universe is always kept and always first: it is the
    single-universe result the whole exercise is measured against. Anything
    dropped by the cap is counted and reported, never silently discarded.
    """
    include_set = set(include) if include else None
    exclude_set = set(exclude) if exclude else set()
    active = {
        did: d
        for did, d in decisions.items()
        if (include_set is None or did in include_set) and did not in exclude_set
    }
    if not active:
        return UniverseSet(universes=[], n_total_grid=0, cap=cap)

    ids = sorted(active)
    option_lists = [sorted(active[did].options) for did in ids]

    n_total = 1
    for opts in option_lists:
        n_total *= len(opts)

    defaults = default_selections(active)
    valid: list[dict[str, str]] = []
    n_dropped_constraints = 0
    for combo in itertools.product(*option_lists):
        selections = dict(zip(ids, combo))
        if satisfies_constraints(selections, active):
            valid.append(selections)
        else:
            n_dropped_constraints += 1

    # Default first, so universe_000 is always the single-universe baseline.
    valid.sort(key=lambda s: (s != defaults,))

    n_dropped_cap = 0
    if cap is not None and len(valid) > cap:
        n_dropped_cap = len(valid) - cap
        valid = valid[:cap]

    universes = [
        Universe(id=f"universe_{i:03d}", decisions=sel, is_default=(sel == defaults))
        for i, sel in enumerate(valid)
    ]
    return UniverseSet(
        universes=universes,
        n_total_grid=n_total,
        n_dropped_constraints=n_dropped_constraints,
        n_dropped_cap=n_dropped_cap,
        cap=cap,
    )


def write_universe_files(universe_set: UniverseSet, directory: Path) -> list[Path]:
    """Write one ASTRA-shaped UniverseNode YAML per universe."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    for stale in directory.glob("universe_*.yaml"):
        stale.unlink()
    paths: list[Path] = []
    for universe in universe_set.universes:
        doc = {
            "id": universe.id,
            "decisions": [
                {"decision_id": did, "option_id": oid}
                for did, oid in sorted(universe.decisions.items())
            ],
        }
        path = directory / f"{universe.id}.yaml"
        path.write_text(yaml.safe_dump(doc, sort_keys=False))
        paths.append(path)
    return paths
