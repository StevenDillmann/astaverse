"""Execution command behavior that does not launch Harbor."""

from types import SimpleNamespace

from astaverse.core.stages.s6_execute import _available_job_name, build_command


def test_rerun_uses_a_fresh_harbor_job_name(tmp_path):
    base = "run__terminus-2-openai_gpt-5.6-luna"
    (tmp_path / base).mkdir()
    (tmp_path / f"{base}-2").mkdir()

    assert _available_job_name(tmp_path, "run", "terminus-2", "openai/gpt-5.6-luna") == f"{base}-3"


def test_harbor_command_confirms_prompts_noninteractively(tmp_path):
    run_obj = SimpleNamespace(run_id="run", jobs_dir=tmp_path / "jobs")

    command = build_command(run_obj, tmp_path / "task", "terminus-2", "openai/gpt-5.6-luna")

    assert command[:3] == ["harbor", "run", "--yes"]
