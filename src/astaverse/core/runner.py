"""Running stages — one implementation, used by the CLI, the API, and run-all.

`run_stage` is the single place that maps a stage name to its function and
supplies the run's saved configuration. Anything that runs a stage goes
through here, so a stage run alone and the same stage run as part of a
sequence behave identically.

`run_sequence` walks stages in order, in a background thread, recording
progress so a caller can poll rather than hold a request open for the many
minutes an agent sweep takes.
"""

from __future__ import annotations

import threading
import traceback
from dataclasses import dataclass, field
from typing import Callable

from . import config as run_config
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
from .store import STAGES, Run, utcnow


def run_stage(run_obj: Run, stage: str) -> None:
    """Run one stage using the run's saved configuration."""
    cfg = run_config.load(run_obj)

    if stage == "study":
        manifest = run_obj.manifest()
        s1_study.run(run_obj, manifest["hypothesis"], manifest["dataset"])

    elif stage == "plans":
        seed_info = run_obj.manifest().get("seed") or {}
        seed = (
            s2_plans.load_seed_plan(
                jsonl=seed_info["source_path"], normalized_id=seed_info["normalized_id"]
            )
            if seed_info.get("source_path")
            else None
        )
        s2_plans.run(
            run_obj,
            # audit_plan is intentionally about one plan. When a seed exists
            # that one plan is the seed; otherwise sample exactly one.
            k=1 if cfg.decisions.mode == "audit_plan" else cfg.plans.k,
            model=cfg.plans.model,
            temperature=cfg.plans.temperature,
            seed_plan=seed,
        )

    elif stage == "decisions":
        d = cfg.decisions
        s3_decisions.run(
            run_obj,
            model=d.models[0] if d.models else None,
            models=d.models or None,
            mode=d.mode,
            critique=d.critique,
            max_decisions=d.max_decisions,
        )

    elif stage == "universes":
        u = cfg.universes
        s4_universes.run(
            run_obj,
            cap=u.cap,
            include=u.include or None,
            exclude=u.exclude or None,
        )

    elif stage == "task":
        s5_task.run(run_obj)

    elif stage == "execute":
        e = cfg.execute
        s6_execute.run(
            run_obj, agent=e.agent, models=e.models or None, dry_run=e.dry_run
        )

    elif stage == "verdicts":
        s7_verdicts.run(run_obj)

    elif stage == "surprisal":
        s8_surprisal.run(
            run_obj, model=cfg.surprisal.model, n_samples=cfg.surprisal.n_samples
        )

    else:
        raise ValueError(f"unknown stage '{stage}'")


# --------------------------------------------------------------------------
# sequential execution
# --------------------------------------------------------------------------


@dataclass
class Progress:
    run_id: str
    target: str
    pending: list[str]
    current: str | None = None
    done: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    failed: str | None = None
    error: str | None = None
    finished: bool = False
    started_at: str = ""

    def as_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "target": self.target,
            "pending": self.pending,
            "current": self.current,
            "done": self.done,
            "skipped": self.skipped,
            "failed": self.failed,
            "error": self.error,
            "finished": self.finished,
            "started_at": self.started_at,
            "running": bool(self.current) and not self.finished,
        }


#: run_id -> Progress. In-process only; a restart clears it, which is fine
#: because the artifacts on disk are the durable record of what completed.
_PROGRESS: dict[str, Progress] = {}
_LOCK = threading.Lock()


def progress_for(run_id: str) -> dict | None:
    with _LOCK:
        p = _PROGRESS.get(run_id)
        return p.as_dict() if p else None


def is_running(run_id: str) -> bool:
    with _LOCK:
        p = _PROGRESS.get(run_id)
        return bool(p and not p.finished)


def run_sequence(
    run_obj: Run,
    through: str | None = None,
    force: bool = False,
    on_stage: Callable[[str], None] | None = None,
) -> Progress:
    """Run stages in order up to `through`, skipping ones already complete.

    Blocks. Use `start_sequence` for the background variant.
    """
    cfg = run_config.load(run_obj)
    target = through or cfg.through
    planned = cfg.stages_through(target)
    status = run_obj.status()

    progress = Progress(
        run_id=run_obj.run_id,
        target=target,
        pending=list(planned),
        started_at=utcnow(),
    )
    with _LOCK:
        _PROGRESS[run_obj.run_id] = progress

    try:
        for stage in planned:
            with _LOCK:
                progress.pending = [s for s in planned if s not in progress.done and s != stage]
            if not force and status.get(stage) == "complete":
                progress.skipped.append(stage)
                progress.done.append(stage)
                continue
            progress.current = stage
            if on_stage:
                on_stage(stage)
            run_obj.log("run-all", f"starting {stage}")
            run_stage(run_obj, stage)
            progress.done.append(stage)
            progress.current = None
            # A stage invalidates everything downstream, so re-read rather
            # than trusting the snapshot taken before the loop.
            status = run_obj.status()
    except Exception as exc:  # noqa: BLE001 - report, do not crash the server
        progress.failed = progress.current
        progress.error = f"{type(exc).__name__}: {exc}"
        run_obj.log("run-all", f"FAILED at {progress.current}: {exc}")
        run_obj.log("run-all", traceback.format_exc(limit=4))
    finally:
        progress.current = None
        progress.pending = []
        progress.finished = True

    return progress


def start_sequence(run_obj: Run, through: str | None = None, force: bool = False) -> dict:
    """Kick off `run_sequence` in a background thread and return immediately."""
    if is_running(run_obj.run_id):
        raise RuntimeError(f"run {run_obj.run_id} is already running")

    cfg = run_config.load(run_obj)
    target = through or cfg.through
    planned = cfg.stages_through(target)
    with _LOCK:
        _PROGRESS[run_obj.run_id] = Progress(
            run_id=run_obj.run_id,
            target=target,
            pending=list(planned),
            current=planned[0] if planned else None,
            started_at=utcnow(),
        )

    thread = threading.Thread(
        target=run_sequence,
        args=(run_obj, target, force),
        name=f"astaverse-run-{run_obj.run_id}",
        daemon=True,
    )
    thread.start()
    return progress_for(run_obj.run_id) or {}
