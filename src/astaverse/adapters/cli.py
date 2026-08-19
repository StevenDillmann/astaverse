"""astaverse — command line interface.

Generated from the config object rather than written by hand. Every field in
`RunConfig` becomes a flag, with its `description` as help text, so the CLI
and the UI cannot drift: they read the same schema.

    astaverse new --hypothesis "..." --dataset hurricane
    astaverse ls
    astaverse run <id> --decisions.mode direct --universes.cap 12
    astaverse stage <id> decisions --decisions.mode audit_plan
    astaverse serve

The verbs are hand-chosen because they are a small, stable vocabulary; the
options are generated because they are neither.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Annotated, Any

import tyro
from dotenv import load_dotenv

from ..core import claims as claims_core
from ..core import config as run_cfg
from ..core import runner
from ..core import settings as app_settings
from ..core.config import RunConfig
from ..core.stages import s1_study, s2_plans
from ..core.store import STAGES, Run

load_dotenv()

# Flatten the nested config onto the top level, so flags read
# `--decisions.mode` rather than `--config.decisions.mode`.
Config = Annotated[RunConfig, tyro.conf.arg(name="")]

GREEN, YELLOW, RED, DIM, BOLD, OFF = (
    "\033[32m",
    "\033[33m",
    "\033[31m",
    "\033[2m",
    "\033[1m",
    "\033[0m",
)


def _runs_dir() -> Path:
    return Path(os.environ.get("ASTAVERSE_RUNS", Path.cwd() / "runs"))


def _load(analysis_id: str) -> Run:
    try:
        return Run.load(_runs_dir(), analysis_id)
    except FileNotFoundError as exc:
        sys.exit(f"{RED}{exc}{OFF}")


def _explicit_patch(config: RunConfig, argv: list[str] | None = None) -> dict[str, Any]:
    """Which config fields the user actually typed, with their parsed values.

    tyro hands back a fully-populated object, so an unset field is
    indistinguishable from one passed at its default. Saving that object
    wholesale would silently reset every knob the user configured earlier —
    `astaverse run <id>` with no flags would wipe the saved configuration.

    So argv says *which* fields were given, and the parsed object supplies
    their *values*, already typed and validated.
    """
    argv = sys.argv[1:] if argv is None else argv
    dumped = config.model_dump()
    patch: dict[str, Any] = {}

    for token in argv:
        if not token.startswith("--"):
            continue
        name = token[2:].split("=", 1)[0]
        if "." not in name:
            if name.replace("-", "_") in dumped:
                key = name.replace("-", "_")
                patch[key] = dumped[key]
            continue
        section, _, field = name.partition(".")
        section = section.replace("-", "_")
        field = field.replace("-", "_")
        # Boolean flags arrive as --x / --no-x.
        if field.startswith("no_") and field not in dumped.get(section, {}):
            field = field[3:]
        if section in dumped and isinstance(dumped[section], dict) and field in dumped[section]:
            patch.setdefault(section, {})[field] = dumped[section][field]

    return patch


def _apply_cli_config(analysis: Run, config: RunConfig) -> RunConfig:
    """Merge only what was typed, then return the effective configuration."""
    patch = _explicit_patch(config)
    if patch:
        run_cfg.update(analysis, patch)
    return run_cfg.load(analysis)


def _echo_config(config: RunConfig) -> None:
    print(f"{DIM}  plans      k={config.plans.k} model={config.plans.model or 'default'}{OFF}")
    print(
        f"{DIM}  decisions  mode={config.decisions.mode}"
        f" models={','.join(config.decisions.models) or 'default'}"
        f"{' +critique' if config.decisions.critique else ''}{OFF}"
    )
    print(f"{DIM}  universes  cap={config.universes.cap}{OFF}")
    if config.spends_money():
        print(
            f"{YELLOW}  execute    agent={config.execute.agent}"
            f" models={','.join(config.execute.models) or 'default'}"
            f"   <- this spends money{OFF}"
        )


# --------------------------------------------------------------------------
# commands
# --------------------------------------------------------------------------


def new(
    hypothesis: str,
    dataset: str,
    /,
    description: str | None = None,
    config: Config = RunConfig(),
) -> None:
    """Create an analysis and profile its dataset.

    Args:
        hypothesis: The claim under test.
        dataset: A CSV file, or a BLADE folder holding data.csv and info.json.
        description: Overrides the dataset's own description, if it has one.
    """
    analysis = Run.create(_runs_dir(), hypothesis, dataset)
    app_settings.apply_to_manifest(analysis, app_settings.load(_runs_dir()))
    _apply_cli_config(analysis, config)
    spec = s1_study.run(analysis, hypothesis, dataset, description)
    print(f"{GREEN}created{OFF} {analysis.run_id}")
    print(f"{DIM}  {spec.n_rows} rows, {len(spec.columns)} columns{OFF}")


def ls() -> None:
    """List analyses, newest first."""
    analyses = Run.list_all(_runs_dir())
    if not analyses:
        print(f"{DIM}no analyses in {_runs_dir()}{OFF}")
        return
    for analysis in analyses:
        status = analysis.status()
        done = sum(1 for v in status.values() if v == "complete")
        pips = "".join(
            "*" if status[s] == "complete" else "-" if status[s] == "skipped" else "."
            for s in STAGES
        )
        manifest = analysis.manifest()
        print(f"{pips} {done}/{len(STAGES)}  {analysis.run_id}")
        print(f"{DIM}          {manifest['hypothesis'][:88]}{OFF}")


def hypotheses() -> None:
    """List hypotheses — each coupled to a dataset — and their experiments.

    A hypothesis groups every experiment using the same hypothesis text and
    dataset, so different methods can be compared.
    """
    found = claims_core.all_claims(_runs_dir())
    if not found:
        print(f"{DIM}no claims in {_runs_dir()}{OFF}")
        return
    for claim in found:
        print(f"{BOLD}{claim.id}{OFF}  {claim.hypothesis[:76]}")
        print(f"{DIM}             {claim.dataset_name} · {len(claim.attempts)} experiment(s){OFF}")
        for a in claim.attempts:
            bits = [f"mode={a.mode or 'default'}"]
            if a.critique:
                bits.append("+critique")
            if a.n_universes is not None:
                bits.append(f"{a.n_universes} universes")
            if a.fragility is not None:
                bits.append(f"fragility={a.fragility:.3f}")
            print(f"    {claims_core.stages_done(a)}  {a.id[:13]}  {DIM}{' · '.join(bits)}{OFF}")

        summary = claims_core.comparison(claim.attempts)
        if summary["unique_decisions"]:
            print(f"{DIM}    found by only some attempts:{OFF}")
            for decision, finders in summary["unique_decisions"].items():
                print(f"{DIM}      {decision:34s} {', '.join(f[:13] for f in finders)}{OFF}")
        if summary["agreement"] == "disagree":
            print(
                f"{YELLOW}    attempts disagree about whether this claim is fragile{OFF}"
            )
        print()


def experiment(analysis_id: str, /, config: Config = RunConfig()) -> None:
    """Create another experiment for the same hypothesis and dataset.

    Inherits the previous configuration, so experiments differ only in what
    you deliberately change:

        astaverse experiment <id> --decisions.mode direct

    Args:
        analysis_id: The run to repeat.
    """
    previous = _load(analysis_id)
    manifest = previous.manifest()
    analysis = Run.create(_runs_dir(), manifest["hypothesis"], manifest["dataset"])
    run_cfg.save(analysis, run_cfg.load(previous))
    patch = _explicit_patch(config)
    if patch:
        run_cfg.update(analysis, patch)
    if manifest.get("seed"):
        fresh = analysis.manifest()
        fresh["seed"] = manifest["seed"]
        analysis.write_manifest(fresh)
    s1_study.run(analysis, manifest["hypothesis"], manifest["dataset"])
    print(f"{GREEN}created experiment{OFF} {analysis.run_id}")
    print(f"{DIM}  hypothesis {claims_core.claim_id(manifest['hypothesis'], manifest['dataset'])}{OFF}")
    _echo_config(run_cfg.load(analysis))


def show(analysis_id: str, /) -> None:
    """Show an analysis: its status, and the configuration it will use."""
    analysis = _load(analysis_id)
    manifest = analysis.manifest()
    print(f"{BOLD}{analysis.run_id}{OFF}")
    print(f"  hypothesis  {manifest['hypothesis']}")
    print(f"  dataset     {manifest['dataset']}\n")
    marks = {
        "complete": f"{GREEN}*{OFF}",
        "ready": ">",
        "pending": " ",
        "skipped": f"{DIM}-{OFF}",
    }
    for stage, state in analysis.status().items():
        print(f"  {marks[state]} {stage}")
    print()
    _echo_config(run_cfg.load(analysis))


def configure(analysis_id: str, /, config: Config = RunConfig()) -> None:
    """Save configuration for an analysis. Only flags you pass are changed."""
    analysis = _load(analysis_id)
    if _explicit_patch(config):
        _apply_cli_config(analysis, config)
        print(f"{GREEN}saved{OFF}")
    else:
        print(f"{DIM}nothing to change; showing current configuration{OFF}")
    _echo_config(run_cfg.load(analysis))


def defaults(config: Config = RunConfig(), review_before_execute: bool | None = None) -> None:
    """Set defaults copied into every new experiment."""
    current = app_settings.load(_runs_dir())
    patch = _explicit_patch(config)
    payload: dict[str, Any] = {}
    if patch:
        payload["default_experiment"] = patch
    if review_before_execute is not None:
        payload["review_before_execute"] = review_before_execute
    if payload:
        current = app_settings.update(_runs_dir(), payload)
        print(f"{GREEN}saved defaults{OFF}")
    _echo_config(current.default_experiment)
    print(
        f"{DIM}  review     {'before execution' if current.review_before_execute else 'fully automatic'}{OFF}"
    )


def stage(analysis_id: str, name: str, /, config: Config = RunConfig()) -> None:
    """Run one stage.

    Args:
        analysis_id: Which analysis.
        name: Stage to run — one of study, plans, decisions, universes, task,
            execute, verdicts, surprisal.
    """
    if name not in STAGES:
        sys.exit(f"{RED}unknown stage '{name}' (have: {', '.join(STAGES)}){OFF}")
    analysis = _load(analysis_id)
    _apply_cli_config(analysis, config)
    print(f"{BOLD}-> {name}{OFF}")
    try:
        runner.run_stage(analysis, name)
    except Exception as exc:  # noqa: BLE001
        sys.exit(f"{RED}{name} failed: {exc}{OFF}")
    print(f"{GREEN}done{OFF} {name}")


def run(
    analysis_id: str,
    /,
    config: Config = RunConfig(),
    force: bool = False,
    yes: bool = False,
) -> None:
    """Run every stage up to the configured target, in order.

    Stages already complete are skipped unless --force.

    Args:
        analysis_id: Which analysis.
        force: Re-run stages that have already completed.
        yes: Skip the confirmation when the target includes execute.
    """
    analysis = _load(analysis_id)
    saved = _apply_cli_config(analysis, config)

    print(f"{BOLD}running {analysis.run_id} through '{saved.through}'{OFF}")
    _echo_config(saved)
    if saved.spends_money() and not yes:
        answer = input(
            f"{YELLOW}This launches a coding agent in a container. Continue? [y/N] {OFF}"
        )
        if answer.strip().lower() not in {"y", "yes"}:
            sys.exit("cancelled")
    print()

    progress = runner.run_sequence(
        analysis,
        through=saved.through,
        force=force,
        on_stage=lambda s: print(f"{BOLD}-> {s}{OFF}"),
    )
    for skipped in progress.skipped:
        print(f"{DIM}.  {skipped} (already complete){OFF}")
    if progress.failed:
        sys.exit(f"\n{RED}failed at '{progress.failed}'{OFF}\n  {progress.error}")
    print(f"\n{GREEN}complete through '{saved.through}'{OFF}")


def seed(analysis_id: str, jsonl: str, /, normalized_id: str | None = None) -> None:
    """Attach an AutoDiscovery plan, so the multiverse describes that plan.

    Args:
        analysis_id: Which analysis.
        jsonl: A plans jsonl, e.g. data/plans/01_normalized/hurricane.jsonl.
        normalized_id: Which record. Defaults to the first.
    """
    analysis = _load(analysis_id)
    text = s2_plans.load_seed_plan(jsonl=jsonl, normalized_id=normalized_id)
    if not text:
        sys.exit(f"{RED}no plan found in {jsonl}{OFF}")
    manifest = analysis.manifest()
    manifest["seed"] = {"source_path": str(jsonl), "normalized_id": normalized_id or ""}
    analysis.write_manifest(manifest)
    print(f"{GREEN}seeded{OFF} {normalized_id or '(first record)'} from {jsonl}")


def schema() -> None:
    """Print the configuration JSON Schema — what the UI renders its form from."""
    import json

    print(json.dumps(run_cfg.json_schema(), indent=2))


def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Serve the web interface."""
    import uvicorn

    uvicorn.run("astaverse.adapters.api:app", host=host, port=port, reload=False)


def main() -> None:
    tyro.extras.subcommand_cli_from_dict(
        {
            "new": new,
            "ls": ls,
            "hypotheses": hypotheses,
            "experiment": experiment,
            # Compatibility aliases for scripts written before the interface
            # vocabulary was introduced.
            "claims": hypotheses,
            "again": experiment,
            "show": show,
            "config": configure,
            "defaults": defaults,
            "stage": stage,
            "run": run,
            "seed": seed,
            "schema": schema,
            "serve": serve,
        },
        prog="astaverse",
        description="Multiverse analysis and robust surprisal.",
    )


if __name__ == "__main__":
    main()
