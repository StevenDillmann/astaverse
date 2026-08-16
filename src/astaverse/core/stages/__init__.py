"""Pipeline stages.

Each stage is a pure function `(run, **config) -> artifact`. The CLI and the
FastAPI server both call these, so there is exactly one implementation of
every step in the pipeline.
"""

from . import (  # noqa: F401
    s1_study,
    s2_plans,
    s3_decisions,
    s4_universes,
    s5_task,
    s6_execute,
    s7_verdicts,
    s8_surprisal,
)
