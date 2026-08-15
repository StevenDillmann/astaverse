"""s6 — execution: run the Harbor task, collect the multiverse output.

Mirrors `autodiscovery-execution-experiments/scripts/run.sh`, including the
`yes |` auto-confirm for Harbor's env-var prompt.

Multiple `-m` models can be given in one call. That is not a convenience: the
spread between models is the estimate of implementation bias, and s8 reports
it beside the between-universe spread.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from pydantic import BaseModel

from ..store import Run
from .s5_task import TaskArtifact

ARTIFACTS = ["/app/universes.jsonl", "/app/results.md", "/app/analysis.py"]


class JobRecord(BaseModel):
    job_name: str
    agent: str
    model: str | None
    command: list[str]
    returncode: int | None = None
    job_dir: str | None = None


class ExecuteArtifact(BaseModel):
    jobs: list[JobRecord]
    dry_run: bool = False


def _job_name(run_id: str, agent: str, model: str | None) -> str:
    suffix = f"-{model.replace('/', '_')}" if model else ""
    return f"{run_id}__{agent}{suffix}"


def build_command(run_obj: Run, task_dir: Path, agent: str, model: str | None) -> list[str]:
    cmd = [
        "harbor",
        "run",
        "-p",
        str(task_dir),
        "-a",
        agent,
        "-o",
        str(run_obj.jobs_dir),
        "--job-name",
        _job_name(run_obj.run_id, agent, model),
    ]
    if model:
        cmd += ["-m", model]
    for artifact in ARTIFACTS:
        cmd += ["--artifact", artifact]
    return cmd


def run(
    run_obj: Run,
    agent: str = "terminus-2",
    models: list[str] | None = None,
    dry_run: bool = False,
) -> ExecuteArtifact:
    task: TaskArtifact = run_obj.read_artifact("task", TaskArtifact)
    task_dir = Path(task.task_dir)
    if not task_dir.is_dir():
        raise FileNotFoundError(f"task dir missing, re-run `astaverse task`: {task_dir}")

    run_obj.jobs_dir.mkdir(parents=True, exist_ok=True)
    models = models or [None]  # type: ignore[list-item]

    jobs: list[JobRecord] = []
    for model in models:
        cmd = build_command(run_obj, task_dir, agent, model)
        job_name = _job_name(run_obj.run_id, agent, model)
        record = JobRecord(job_name=job_name, agent=agent, model=model, command=cmd)

        if dry_run:
            run_obj.log("execute", "DRY RUN: " + " ".join(cmd))
            jobs.append(record)
            continue

        run_obj.log("execute", "running: " + " ".join(cmd))
        # `yes |` auto-confirms Harbor's env-var prompt, as scripts/run.sh does.
        proc = subprocess.run(
            f"yes | {' '.join(subprocess.list2cmdline([c]) for c in cmd)}",
            shell=True,
            cwd=run_obj.root,
            env={**os.environ},
        )
        record.returncode = proc.returncode
        job_dir = run_obj.jobs_dir / job_name
        record.job_dir = str(job_dir) if job_dir.exists() else None
        if proc.returncode != 0:
            run_obj.log("execute", f"{job_name} exited {proc.returncode}")
        jobs.append(record)

    artifact = ExecuteArtifact(jobs=jobs, dry_run=dry_run)
    # Write the artifact first either way, so the exact commands stay
    # inspectable after a failure.
    run_obj.write_artifact("execute", artifact)

    if dry_run:
        return artifact

    failures = [j for j in jobs if j.returncode not in (0, None)]
    if failures:
        # A harbor run that crashed is not a completed stage. Recording it as
        # one would let verdicts read a nonexistent sweep and report an empty
        # multiverse as though it were a result.
        raise RuntimeError(
            "harbor run failed for "
            + ", ".join(f"{j.job_name} (exit {j.returncode})" for j in failures)
            + f"\nCommands are recorded in {run_obj.artifact_path('execute').name}; "
            "re-run one by hand to see harbor's own output."
        )

    run_obj.record_stage(
        "execute", agent=agent, models=[m for m in models], n_jobs=len(jobs)
    )
    return artifact
