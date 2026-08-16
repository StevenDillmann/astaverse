"""astaverse — CLI.

Every command calls the same stage function the API does. Stages are
independent: each reads the previous artifact from disk, so any step can be
re-run alone.
"""

from __future__ import annotations

import os
from pathlib import Path

import typer
from dotenv import load_dotenv

from . import astra_io
from . import config as run_cfg
from . import runner
from .schemas import DecisionSpec, PlanSet, RobustSurprisal, StudySpec, UniverseSet
from .stages import (
    s1_study,
    s2_plans,
    s3_decisions,
    s4_universes,
    s5_task,
    s6_execute,
    s7_verdicts,
    s8_surprisal,
)
from .store import STAGES, Run

load_dotenv()

app = typer.Typer(
    add_completion=False,
    help="Multiverse analysis and robust surprisal.",
    no_args_is_help=True,
)


def _runs_dir() -> Path:
    return Path(os.environ.get("ASTAVERSE_RUNS", Path.cwd() / "runs"))


def _run(run_id: str) -> Run:
    return Run.load(_runs_dir(), run_id)


def _echo_stage(name: str, detail: str) -> None:
    typer.secho(f"✓ {name}", fg=typer.colors.GREEN, bold=True, nl=False)
    typer.echo(f"  {detail}")


# --------------------------------------------------------------------------


@app.command()
def new(
    hypothesis: str = typer.Option(..., "--hypothesis", "-h", help="The hypothesis under test"),
    dataset: str = typer.Option(..., "--dataset", "-d", help="CSV file or BLADE dataset folder"),
    description: str | None = typer.Option(None, "--description", help="Dataset description"),
) -> None:
    """Create a run and profile its dataset (stage 1)."""
    run_obj = Run.create(_runs_dir(), hypothesis, dataset)
    spec = s1_study.run(run_obj, hypothesis, dataset, description)
    _echo_stage("study", f"{spec.n_rows} rows, {len(spec.columns)} columns")
    typer.echo(f"\nrun id: {run_obj.run_id}")


@app.command()
def study(
    run_id: str,
    hypothesis: str = typer.Option(None, "--hypothesis", "-h"),
    dataset: str = typer.Option(None, "--dataset", "-d"),
) -> None:
    """Re-profile the dataset (stage 1)."""
    run_obj = _run(run_id)
    manifest = run_obj.manifest()
    spec = s1_study.run(
        run_obj,
        hypothesis or manifest["hypothesis"],
        dataset or manifest["dataset"],
    )
    _echo_stage("study", f"{spec.n_rows} rows, {len(spec.columns)} columns")


@app.command()
def plans(
    run_id: str,
    k: int = typer.Option(5, "-k", help="Number of plans to sample"),
    model: str = typer.Option(None, "--model", help="Overrides ASTAVERSE_PLAN_MODEL"),
    temperature: float = typer.Option(0.9, "--temperature"),
    seed_plan: str = typer.Option(None, "--seed-plan", help="Plan text to include verbatim"),
    seed_jsonl: str = typer.Option(
        None, "--seed-jsonl", help="AutoDiscovery plans jsonl to take a plan from"
    ),
    seed_id: str = typer.Option(
        None, "--seed-id", help="normalized_id within --seed-jsonl (default: first record)"
    ),
) -> None:
    """Sample K independent analysis plans (stage 2).

    With --seed-plan/--seed-jsonl, the supplied plan is kept verbatim and the
    rest are drawn as alternatives to it — use this to build a multiverse
    around an AutoDiscovery plan rather than around invented ones.
    """
    run_obj = _run(run_id)
    seed = s2_plans.load_seed_plan(seed_plan, seed_jsonl, seed_id)
    plan_set = s2_plans.run(
        run_obj, k=k, model=model, temperature=temperature, seed_plan=seed
    )
    _echo_stage("plans", f"{len(plan_set.plans)} sampled from {plan_set.model}")
    for plan in plan_set.plans:
        typer.echo(f"    {plan.id}: {plan.objective}")


@app.command()
def decisions(
    run_id: str,
    mode: str = typer.Option(
        "plan_diff",
        "--mode",
        help="plan_diff | plan_audit | direct | schema_lint | union",
    ),
    model: list[str] = typer.Option(
        None, "--model", "-m", help="Repeatable; >1 unions across models"
    ),
    critique: bool = typer.Option(
        False, "--critique", help="Second pass asking what the extraction missed"
    ),
    union_mode: list[str] = typer.Option(
        None, "--union-mode", help="With --mode union: which modes to combine"
    ),
    max_decisions: int = typer.Option(6, "--max-decisions"),
) -> None:
    """Extract the decision space (stage 3).

    Modes differ in what they can see:

      plan_diff    where K sampled plans disagree. Grounded, but blind to
                   under-specification by silence.
      plan_audit   one plan, audited for what it leaves an implementer to
                   decide. Targets silence directly.
      direct       hypothesis + schema only, no plans. Cheapest.
      schema_lint  what the data itself forces — orientation, scale,
                   missingness. Catches forks no plan mentions.
      union        several of the above, merged. Their blind spots differ.
    """
    run_obj = _run(run_id)
    models = list(model or []) or None
    spec = s3_decisions.run(
        run_obj,
        model=models[0] if models else None,
        models=models,
        mode=mode,
        critique=critique,
        union_modes=list(union_mode or []) or None,
        max_decisions=max_decisions,
    )
    _echo_stage("decisions", f"{len(spec.decisions)} decisions -> {run_obj.artifact_path('decisions').name}")
    for did, decision in spec.decisions.items():
        marker = " (post-hoc)" if decision.post_hoc else ""
        typer.echo(f"    {did}{marker}: {', '.join(decision.options)}")


@app.command()
def universes(
    run_id: str,
    cap: int = typer.Option(24, "--max", help="Maximum universes to execute"),
    include: list[str] = typer.Option(None, "--include", help="Only these decisions"),
    exclude: list[str] = typer.Option(None, "--exclude", help="Drop these decisions"),
) -> None:
    """Enumerate the universe grid (stage 4)."""
    run_obj = _run(run_id)
    universe_set = s4_universes.run(
        run_obj, cap=cap, include=list(include or []) or None, exclude=list(exclude or [])
    )
    detail = f"{len(universe_set.universes)} universes of {universe_set.n_total_grid} grid points"
    if universe_set.n_dropped_constraints:
        detail += f", {universe_set.n_dropped_constraints} invalid"
    _echo_stage("universes", detail)
    if universe_set.truncated:
        typer.secho(
            f"    WARNING: {universe_set.n_dropped_cap} universes dropped by the cap of {cap}",
            fg=typer.colors.YELLOW,
        )


@app.command()
def task(run_id: str) -> None:
    """Emit the Harbor task (stage 5)."""
    run_obj = _run(run_id)
    artifact = s5_task.run(run_obj)
    _echo_stage("task", f"{len(artifact.files)} files -> {artifact.task_dir}")


@app.command()
def execute(
    run_id: str,
    agent: str = typer.Option("terminus-2", "--agent", "-a"),
    model: list[str] = typer.Option(None, "--model", "-m", help="Repeatable; >1 estimates agent bias"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print the harbor command, run nothing"),
) -> None:
    """Run the Harbor task (stage 6)."""
    run_obj = _run(run_id)
    artifact = s6_execute.run(run_obj, agent=agent, models=list(model or []) or None, dry_run=dry_run)
    if dry_run:
        for job in artifact.jobs:
            typer.echo(" ".join(job.command))
        return
    _echo_stage("execute", f"{len(artifact.jobs)} job(s)")
    for job in artifact.jobs:
        status = "ok" if job.returncode == 0 else f"exit {job.returncode}"
        typer.echo(f"    {job.job_name}: {status}")


@app.command()
def verdicts(
    run_id: str,
    universes_jsonl: str = typer.Option(None, "--universes-jsonl", help="Score a local file instead"),
) -> None:
    """Assign verdicts to the reported statistics (stage 7)."""
    run_obj = _run(run_id)
    artifact = s7_verdicts.run(run_obj, universes_jsonl=universes_jsonl)
    _echo_stage("verdicts", f"{len(artifact.results)} results, rules: {', '.join(artifact.verdict_rules)}")
    if not artifact.complete:
        typer.secho(
            f"    INCOMPLETE: {len(artifact.missing_universe_ids)} universes missing",
            fg=typer.colors.RED,
        )
    counts: dict[str, int] = {}
    for result in artifact.results:
        counts[result.verdict.value] = counts.get(result.verdict.value, 0) + 1
    for verdict, count in sorted(counts.items()):
        typer.echo(f"    {verdict}: {count}")


@app.command()
def surprisal(
    run_id: str,
    model: str = typer.Option(None, "--model", help="Overrides ASTAVERSE_BELIEF_MODEL"),
    n_samples: int = typer.Option(5, "--n-samples", help="Belief draws per elicitation"),
) -> None:
    """Compute robust surprisal over the multiverse (stage 8)."""
    run_obj = _run(run_id)
    robust = s8_surprisal.run(run_obj, model=model, n_samples=n_samples)
    _echo_stage("surprisal", f"{robust.n_universes} universes")
    typer.echo(f"    prior mean          {robust.prior_mean:.3f}")
    if robust.joint_surprisal is not None:
        typer.secho(
            f"    JOINT surprisal     {robust.joint_surprisal:+.3f}"
            "   ← the belief update",
            bold=True,
        )
    typer.echo("\n    diagnostics (sensitivity, not independent evidence):")
    typer.echo(f"    median surprisal    {robust.median:+.3f}")
    typer.echo(f"    IQR                 {robust.iqr:.3f}")
    typer.echo(f"    sign consistency    {robust.sign_consistency:.0%}")
    typer.echo(f"    surprising          {robust.frac_surprising:.0%} of universes")
    if robust.single_universe_surprisal is not None:
        typer.echo(f"    single-universe     {robust.single_universe_surprisal:+.3f}")
        typer.secho(
            f"    fragility index     {robust.fragility_index:.3f}",
            fg=typer.colors.YELLOW if (robust.fragility_index or 0) > 0.1 else None,
            bold=True,
        )
    if robust.between_agent_spread is not None:
        typer.echo(f"    between-agent       {robust.between_agent_spread:.3f}")
    if robust.decision_sensitivity:
        typer.echo("\n    decision sensitivity (spread of mean surprisal):")
        for sens in robust.decision_sensitivity:
            typer.echo(f"      {sens.spread:.3f}  {sens.decision_id} ({sens.kind.value})")


@app.command()
def config(
    run_id: str,
    show: bool = typer.Option(False, "--show", help="Print the saved config and exit"),
    through: str = typer.Option(None, "--through", help=f"Run-all target: {', '.join(STAGES)}"),
    k: int = typer.Option(None, "-k", help="Plans to sample"),
    mode: str = typer.Option(None, "--mode", help="Decision extraction mode"),
    critique: bool = typer.Option(None, "--critique/--no-critique"),
    max_decisions: int = typer.Option(None, "--max-decisions"),
    cap: int = typer.Option(None, "--max", help="Universe cap"),
    exclude: list[str] = typer.Option(None, "--exclude", help="Drop these decisions"),
    agent: str = typer.Option(None, "--agent", "-a"),
    execute_model: list[str] = typer.Option(None, "--execute-model"),
    decision_model: list[str] = typer.Option(None, "--decision-model"),
    plan_model: str = typer.Option(None, "--plan-model"),
    belief_model: str = typer.Option(None, "--belief-model"),
    n_samples: int = typer.Option(None, "--n-samples"),
) -> None:
    """Set the knobs for a run, once, then `run-all` uses them.

    Stages run individually use the same saved config, so a stage cannot
    behave differently depending on how it was launched.
    """
    run_obj = _run(run_id)
    if show:
        typer.echo(run_cfg.load(run_obj).model_dump_json(indent=2))
        return

    patch: dict = {}

    def section(name: str, **values):
        kept = {k2: v for k2, v in values.items() if v not in (None, (), [])}
        if kept:
            patch[name] = kept

    section("plans", k=k, model=plan_model)
    section(
        "decisions",
        mode=mode,
        critique=critique,
        max_decisions=max_decisions,
        models=list(decision_model or []),
    )
    section("universes", cap=cap, exclude=list(exclude or []))
    section("execute", agent=agent, models=list(execute_model or []))
    section("surprisal", model=belief_model, n_samples=n_samples)
    if through:
        patch["through"] = through

    if not patch:
        typer.echo("Nothing to change. Use --show to inspect, or pass some options.")
        raise typer.Exit(1)

    updated = run_cfg.update(run_obj, patch)
    typer.secho("✓ config saved", fg=typer.colors.GREEN, bold=True)
    typer.echo(updated.model_dump_json(indent=2))


@app.command("run-all")
def run_all(
    run_id: str,
    through: str = typer.Option(None, "--through", help="Overrides the configured target"),
    force: bool = typer.Option(False, "--force", help="Re-run stages already complete"),
) -> None:
    """Run every stage up to the configured target, in order.

    Stages already complete are skipped unless --force. Runs in the
    foreground here, so you see each stage as it happens.
    """
    run_obj = _run(run_id)
    cfg = run_cfg.load(run_obj)
    target = through or cfg.through
    typer.secho(f"Running {run_obj.run_id} through '{target}'", bold=True)
    typer.echo(f"  plans      k={cfg.plans.k} model={cfg.plans.model or 'default'}")
    typer.echo(
        f"  decisions  mode={cfg.decisions.mode}"
        f" models={','.join(cfg.decisions.models) or 'default'}"
        f"{' +critique' if cfg.decisions.critique else ''}"
    )
    typer.echo(f"  universes  cap={cfg.universes.cap}")
    if STAGES.index(target) >= STAGES.index("execute"):
        typer.secho(
            f"  execute    agent={cfg.execute.agent} "
            f"models={','.join(cfg.execute.models) or 'default'}"
            "   ← this spends money",
            fg=typer.colors.YELLOW,
        )
    typer.echo("")

    def announce(stage: str) -> None:
        typer.secho(f"→ {stage}", bold=True)

    progress = runner.run_sequence(run_obj, through=target, on_stage=announce)

    for stage in progress.skipped:
        typer.echo(f"· {stage} (already complete)")
    if progress.failed:
        typer.secho(f"\n✗ failed at '{progress.failed}'", fg=typer.colors.RED, bold=True)
        typer.echo(f"  {progress.error}")
        raise typer.Exit(1)
    typer.secho(f"\n✓ complete through '{target}'", fg=typer.colors.GREEN, bold=True)


@app.command("list")
def list_runs() -> None:
    """List runs."""
    runs = Run.list_all(_runs_dir())
    if not runs:
        typer.echo(f"no runs in {_runs_dir()}")
        return
    for run_obj in runs:
        status = run_obj.status()
        done = sum(1 for v in status.values() if v == "complete")
        manifest = run_obj.manifest()
        typer.echo(f"{run_obj.run_id}  [{done}/{len(STAGES)}]  {manifest['hypothesis'][:60]}")


@app.command()
def show(run_id: str) -> None:
    """Show a run's stage status and key artifacts."""
    run_obj = _run(run_id)
    manifest = run_obj.manifest()
    typer.secho(run_obj.run_id, bold=True)
    typer.echo(f"hypothesis: {manifest['hypothesis']}")
    typer.echo(f"dataset:    {manifest['dataset']}\n")
    marks = {"complete": "✓", "ready": "→", "pending": " "}
    for stage, state in run_obj.status().items():
        typer.echo(f"  {marks[state]} {stage}")


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8000, "--port"),
) -> None:
    """Serve the pipeline viewer."""
    import uvicorn

    uvicorn.run("astaverse.server:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    app()
