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
from collections.abc import Iterable
from pathlib import Path

import yaml

from ..core.schemas import ASTRA_SCHEMA_SHAPE, Decision, DecisionSpec, Universe, UniverseSet

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
                    "Per-universe statistics (estimate, estimate_standardized, "
                    "std_error, std_error_standardized, 95% standardized confidence "
                    "interval, p_value, n, direction). Carries no verdict by design: "
                    "verdicts are assigned downstream."
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


def satisfies_constraints(selections: dict[str, str], decisions: dict[str, Decision]) -> bool:
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


def matched_pair_counts(selections: Iterable[dict[str, str]]) -> dict[str, int]:
    """Count pairs that differ on exactly one decision."""
    rows = list(selections)
    counts: dict[str, int] = {}
    for index, left in enumerate(rows):
        for right in rows[index + 1 :]:
            changed = [key for key in left if left.get(key) != right.get(key)]
            if len(changed) == 1:
                decision_id = changed[0]
                counts[decision_id] = counts.get(decision_id, 0) + 1
    return counts


def _pair_balanced_sample(
    valid: list[dict[str, str]],
    active: dict[str, Decision],
    defaults: dict[str, str],
    cap: int,
) -> list[dict[str, str]]:
    """Select a compact design with option coverage and matched comparisons.

    A simple stride covers the grid but usually produces no two universes that
    differ on only one decision. This design starts from the default, adds the
    nearest valid universe needed to represent every option, then greedily
    fills the remaining budget with points that add matched-pair edges for the
    least-covered decisions and option contrasts.
    """
    if cap <= 0:
        return []

    ids = sorted(active)

    def key(row: dict[str, str]) -> tuple[str, ...]:
        return tuple(row[decision_id] for decision_id in ids)

    valid_by_key = {key(row): row for row in valid}
    valid_order = {candidate: index for index, candidate in enumerate(valid_by_key)}
    default_key = key(defaults)
    first = default_key if default_key in valid_by_key else next(iter(valid_by_key))

    selected: list[tuple[str, ...]] = []
    selected_set: set[tuple[str, ...]] = set()
    option_counts: dict[tuple[str, str], int] = {}
    pair_counts: dict[str, int] = {}
    contrast_counts: dict[tuple[str, str, str], int] = {}

    def add(candidate: tuple[str, ...]) -> None:
        for decision_index, decision_id in enumerate(ids):
            option = candidate[decision_index]
            option_counts[(decision_id, option)] = option_counts.get((decision_id, option), 0) + 1
            for other_option in active[decision_id].options:
                if other_option == option:
                    continue
                neighbor = list(candidate)
                neighbor[decision_index] = other_option
                if tuple(neighbor) not in selected_set:
                    continue
                pair_counts[decision_id] = pair_counts.get(decision_id, 0) + 1
                low, high = sorted((option, other_option))
                contrast = (decision_id, low, high)
                contrast_counts[contrast] = contrast_counts.get(contrast, 0) + 1
        selected.append(candidate)
        selected_set.add(candidate)

    add(first)

    # Round-robin by option rank so a tight cap does not spend all its coverage
    # budget on the alphabetically first decision.
    alternatives = {
        decision_id: [
            option for option in sorted(decision.options) if option != defaults[decision_id]
        ]
        for decision_id, decision in active.items()
    }
    max_alternatives = max((len(options) for options in alternatives.values()), default=0)
    for option_index in range(max_alternatives):
        for decision_id in ids:
            options = alternatives[decision_id]
            if option_index >= len(options) or len(selected) >= cap:
                continue
            option = options[option_index]
            if option_counts.get((decision_id, option), 0):
                continue
            decision_index = ids.index(decision_id)
            candidates = [
                candidate
                for candidate in valid_by_key
                if candidate not in selected_set and candidate[decision_index] == option
            ]
            if not candidates:
                continue
            nearest = min(
                candidates,
                key=lambda candidate: (
                    min(sum(a != b for a, b in zip(candidate, existing)) for existing in selected),
                    valid_order[candidate],
                ),
            )
            add(nearest)

    while len(selected) < min(cap, len(valid_by_key)):
        frontier: set[tuple[str, ...]] = set()
        for existing in selected:
            for decision_index, decision_id in enumerate(ids):
                for option in active[decision_id].options:
                    if option == existing[decision_index]:
                        continue
                    candidate = list(existing)
                    candidate[decision_index] = option
                    candidate_key = tuple(candidate)
                    if candidate_key in valid_by_key and candidate_key not in selected_set:
                        frontier.add(candidate_key)

        if not frontier:
            add(next(candidate for candidate in valid_by_key if candidate not in selected_set))
            continue

        def score(candidate: tuple[str, ...]) -> tuple[float, float, int, float, int]:
            edges: list[tuple[str, str, str]] = []
            for decision_index, decision_id in enumerate(ids):
                option = candidate[decision_index]
                for other_option in active[decision_id].options:
                    if other_option == option:
                        continue
                    neighbor = list(candidate)
                    neighbor[decision_index] = other_option
                    if tuple(neighbor) in selected_set:
                        low, high = sorted((option, other_option))
                        edges.append((decision_id, low, high))
            unseen_contrasts = sum(1 for contrast in edges if contrast_counts.get(contrast, 0) == 0)
            balanced_pair_gain = sum(
                1 / (1 + pair_counts.get(decision_id, 0)) for decision_id, _, _ in edges
            )
            option_balance = sum(
                1 / (1 + option_counts.get((decision_id, candidate[index]), 0))
                for index, decision_id in enumerate(ids)
            )
            return (
                unseen_contrasts,
                balanced_pair_gain,
                len(edges),
                option_balance,
                -valid_order[candidate],
            )

        add(max(frontier, key=score))

    return [valid_by_key[candidate] for candidate in selected]


def enumerate_universes(
    decisions: dict[str, Decision],
    cap: int | None = None,
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

    # Generated constraints can make individually reasonable defaults invalid
    # in combination. Use the nearest valid specification as the reproducible
    # baseline instead of silently producing no default universe.
    if valid and defaults not in valid:
        defaults = min(
            valid,
            key=lambda row: (
                sum(row[decision_id] != defaults[decision_id] for decision_id in ids),
                tuple(row[decision_id] for decision_id in ids),
            ),
        )

    # Default first, so universe_000 is always the single-universe baseline.
    valid.sort(key=lambda s: (s != defaults,))

    n_dropped_cap = 0
    selection_strategy = "full_grid"
    if cap is not None and len(valid) > cap:
        n_dropped_cap = len(valid) - cap
        selection_strategy = "pair_balanced"
        valid = _pair_balanced_sample(valid, active, defaults, cap)

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
        selection_strategy=selection_strategy,
        matched_pairs_by_decision=matched_pair_counts(valid),
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
