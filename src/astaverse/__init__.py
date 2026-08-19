"""Astaverse — multiverse analysis and robust surprisal.

Usable three ways, all over the same core:

    # as a library
    from astaverse import Analysis, RunConfig, run_sequence
    analysis = Analysis.create("runs", "X causes Y", "data/hurricane")
    run_sequence(analysis, through="universes")

    # as a CLI
    $ astaverse new --hypothesis "X causes Y" --dataset data/hurricane
    $ astaverse run <id> --decisions.mode direct

    # as a web app
    $ astaverse serve

`RunConfig` is the single definition of every knob: tyro generates the CLI
flags from it, and the web form renders from its JSON Schema. Adding a field
adds it everywhere.
"""

from __future__ import annotations

__version__ = "0.1.0"

from .core.config import RunConfig, json_schema
from .core.config import load as load_config
from .core.config import save as save_config
from .core.config import update as update_config
from .core.runner import Progress, run_sequence, run_stage, start_sequence
from .core.schemas import (
    Decision,
    DecisionSpec,
    Option,
    Plan,
    RobustSurprisal,
    StudySpec,
    Universe,
    UniverseResult,
    UniverseSet,
    UniverseStats,
    Verdict,
)
from .core.store import STAGES, Run

#: The unit of work: one hypothesis, one dataset, one decision space, and the
#: universes that come out of it. `Run` is the historical name of the class.
Analysis = Run

__all__ = [
    "__version__",
    "Analysis",
    "Run",
    "STAGES",
    # configuration
    "RunConfig",
    "json_schema",
    "load_config",
    "save_config",
    "update_config",
    # running
    "run_stage",
    "run_sequence",
    "start_sequence",
    "Progress",
    # domain objects
    "StudySpec",
    "Plan",
    "DecisionSpec",
    "Decision",
    "Option",
    "Universe",
    "UniverseSet",
    "UniverseStats",
    "UniverseResult",
    "Verdict",
    "RobustSurprisal",
]
