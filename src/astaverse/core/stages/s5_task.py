"""s5 — task emission: decision spec + universes -> a Harbor task directory.

Follows the task shape validated in the sibling repo's
`01_plan_to_harbor/harbor_tasks/hurricane__node_0/`, with the multiverse
differences: the spec and universe files are copied into the image, the
verifier runs a structural check before the rubric, and no reference output
exists to compare against.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined
from pydantic import BaseModel

from ...paths import HARBOR_TASK_TEMPLATE
from ...integrations.astra_io import read_astra_yaml
from ..schemas import DecisionSpec, StudySpec, UniverseSet
from ..store import Run
from .s1_study import render_columns_markdown

TEMPLATES = HARBOR_TASK_TEMPLATE


class TaskArtifact(BaseModel):
    task_dir: str
    task_name: str
    n_universes: int
    files: list[str]


def _render_spec_text(spec: DecisionSpec) -> str:
    """Plain-text decision spec handed to the judge as /tests/spec.txt."""
    lines = [f"Hypothesis: {spec.hypothesis}", "", "Decisions:"]
    for did, decision in spec.decisions.items():
        marker = " (applied downstream, not executed)" if decision.post_hoc else ""
        lines.append(f"\n- {did}: {decision.label}{marker}")
        if decision.rationale:
            lines.append(f"  {decision.rationale}")
        for oid, option in decision.options.items():
            default = " [default]" if oid == decision.default else ""
            lines.append(f"    * {oid}{default}: {option.label} — {option.description or ''}")
    return "\n".join(lines) + "\n"


def run(run_obj: Run, force: bool = False) -> TaskArtifact:
    study: StudySpec = run_obj.read_artifact("study", StudySpec)
    spec: DecisionSpec = read_astra_yaml(run_obj.artifact_path("decisions"))
    universe_set: UniverseSet = run_obj.read_artifact("universes", UniverseSet)

    task_dir = run_obj.task_dir
    if task_dir.exists():
        if not force:
            shutil.rmtree(task_dir)
        else:
            shutil.rmtree(task_dir)
    (task_dir / "environment" / "universes").mkdir(parents=True)
    (task_dir / "tests").mkdir(parents=True)
    (task_dir / "solution").mkdir(parents=True)

    env = Environment(
        loader=FileSystemLoader(TEMPLATES), undefined=StrictUndefined, keep_trailing_newline=True
    )

    execution_decisions = spec.execution_decisions()
    context = {
        "run_id": run_obj.run_id,
        "spec_id": spec.id,
        "dataset_name": study.dataset_name,
        "dataset_description": study.dataset_description or "",
        "n_rows": study.n_rows,
        "hypothesis": spec.hypothesis,
        "columns_markdown": render_columns_markdown(study),
        "decisions": execution_decisions,
        "n_universes": len(universe_set.universes),
        "astra_schema_shape": spec.astra_schema_shape,
    }

    (task_dir / "task.toml").write_text(env.get_template("task.toml.j2").render(**context))
    (task_dir / "instruction.md").write_text(
        env.get_template("instruction.md.j2").render(**context)
    )
    (task_dir / "environment" / "Dockerfile").write_text(
        env.get_template("environment/Dockerfile.j2").render(**context)
    )

    # Dataset and spec into the image.
    shutil.copyfile(study.dataset_path, task_dir / "environment" / "data.csv")
    shutil.copyfile(run_obj.artifact_path("decisions"), task_dir / "environment" / "astra.yaml")
    for universe_file in sorted(run_obj.universes_dir.glob("universe_*.yaml")):
        shutil.copyfile(universe_file, task_dir / "environment" / "universes" / universe_file.name)

    # Verifier: structural check + rubric.
    expected = {u.id: u.decisions for u in universe_set.universes}
    check = env.get_template("tests/check_universes.py.j2").render(
        expected_universes=expected, **context
    )
    (task_dir / "tests" / "check_universes.py").write_text(check)
    (task_dir / "tests" / "test.sh").write_text(env.get_template("tests/test.sh.j2").render(**context))
    (task_dir / "tests" / "test.sh").chmod(0o755)
    (task_dir / "tests" / "rubric.toml").write_text(
        env.get_template("tests/rubric.toml.j2").render(**context)
    )
    (task_dir / "tests" / "spec.txt").write_text(_render_spec_text(spec))

    # Solution slot: `harbor run -a oracle` needs solve.sh. The reference
    # analysis is written by hand per study (see README); scaffold it here so
    # the oracle path fails loudly rather than silently doing nothing.
    (task_dir / "solution" / "solve.sh").write_text(
        "#!/bin/bash\n"
        "# Oracle path: run the hand-written reference sweep.\n"
        "set -euo pipefail\n"
        "cd /app\n"
        "if [ ! -f /app/reference_analysis.py ]; then\n"
        '  echo "no reference_analysis.py: write one to use the oracle agent" >&2\n'
        "  exit 1\n"
        "fi\n"
        "cp /app/reference_analysis.py /app/analysis.py\n"
        "python /app/analysis.py\n"
    )
    (task_dir / "solution" / "solve.sh").chmod(0o755)

    files = sorted(str(p.relative_to(task_dir)) for p in task_dir.rglob("*") if p.is_file())
    artifact = TaskArtifact(
        task_dir=str(task_dir),
        task_name=f"astaverse/multiverse__{spec.id}",
        n_universes=len(universe_set.universes),
        files=files,
    )
    run_obj.write_artifact("task", artifact)
    run_obj.record_stage("task", task_dir=str(task_dir), n_files=len(files))
    run_obj.log("task", f"emitted Harbor task with {len(files)} files at {task_dir}")
    return artifact
