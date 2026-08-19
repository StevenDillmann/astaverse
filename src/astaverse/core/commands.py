"""Render reproducible CLI commands from the same config the runner consumes."""

from __future__ import annotations

import shlex
from typing import Any

from .config import RunConfig
from .store import STAGES


def _tokens(config: RunConfig) -> list[str]:
    dumped = config.model_dump()
    tokens: list[str] = []
    for section in ("plans", "decisions", "universes", "execute", "surprisal"):
        for field, value in dumped[section].items():
            flag = f"--{section}.{field.replace('_', '-')}"
            if isinstance(value, bool):
                tokens.append(flag if value else f"--{section}.no-{field.replace('_', '-')}")
            elif isinstance(value, list):
                if value:
                    tokens.append(flag)
                    tokens.extend(str(item) for item in value)
            elif value is not None:
                tokens.extend([flag, str(value)])
    tokens.extend(["--through", config.through])
    return tokens


def _join(tokens: list[str]) -> str:
    return " ".join(shlex.quote(token) for token in tokens)


def preview(
    config: RunConfig | dict[str, Any],
    experiment_id: str = "<experiment-id>",
) -> dict[str, Any]:
    cfg = config if isinstance(config, RunConfig) else RunConfig.model_validate(config)
    run = _join(["astaverse", "run", experiment_id, *_tokens(cfg)])
    stages = {
        stage: _join(["astaverse", "stage", experiment_id, stage])
        for stage in cfg.stages_through()
    }
    # Expose all stages under advanced controls, even those after the target.
    for stage in STAGES:
        stages.setdefault(stage, _join(["astaverse", "stage", experiment_id, stage]))
    return {
        "run": run,
        "stages": stages,
        "planned_stages": cfg.stages_through(),
    }
