"""s4 — multiverse instantiation: decision space -> the universe set.

Pure Python, no LLM. Enumerates the grid honouring `requires` /
`incompatible_with`, caps it, and writes one ASTRA-shaped UniverseNode YAML
per universe.

Only *execution* decisions enter the executed grid. Post-hoc decisions (the
verdict rule) are applied in s7 to the numbers that come back, which is why a
3-option verdict rule triples the analysed universes at zero execution cost.
"""

from __future__ import annotations

from pathlib import Path

from ...integrations.astra_io import enumerate_universes, read_astra_yaml, write_universe_files
from ..schemas import DecisionSpec, UniverseSet
from ..store import Run


def run(
    run_obj: Run,
    cap: int | None = 24,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
) -> UniverseSet:
    spec: DecisionSpec = read_astra_yaml(run_obj.artifact_path("decisions"))

    universe_set = enumerate_universes(
        spec.execution_decisions(), cap=cap, include=include, exclude=exclude
    )
    if not universe_set.universes:
        raise ValueError(
            "no executable universes: the decision space has no execution decisions "
            "(only post-hoc ones), or --include/--exclude removed everything"
        )

    write_universe_files(universe_set, run_obj.universes_dir)
    run_obj.write_artifact("universes", universe_set)

    n_posthoc = 1
    for decision in spec.post_hoc_decisions().values():
        n_posthoc *= len(decision.options)

    run_obj.record_stage(
        "universes",
        n_universes=len(universe_set.universes),
        n_total_grid=universe_set.n_total_grid,
        n_dropped_constraints=universe_set.n_dropped_constraints,
        n_dropped_cap=universe_set.n_dropped_cap,
        n_analysed=len(universe_set.universes) * n_posthoc,
    )

    msg = (
        f"{len(universe_set.universes)} universes to execute "
        f"(grid {universe_set.n_total_grid}, "
        f"{universe_set.n_dropped_constraints} dropped by constraints)"
    )
    if universe_set.truncated:
        msg += f"; {universe_set.n_dropped_cap} DROPPED BY CAP {universe_set.cap}"
    if n_posthoc > 1:
        msg += f"; x{n_posthoc} post-hoc verdict rules = {len(universe_set.universes) * n_posthoc} analysed"
    run_obj.log("universes", msg)
    return universe_set


def universes_dir(run_obj: Run) -> Path:
    return run_obj.universes_dir
