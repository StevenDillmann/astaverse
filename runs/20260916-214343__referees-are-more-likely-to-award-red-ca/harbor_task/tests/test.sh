#!/bin/bash
# Harbor copies tests/ to /tests and runs this after the agent.
#
# Two gates: a hard structural check on the multiverse output (coverage +
# parametric structure), then the rewardkit LLM rubric on the written report.
# The structural check runs first because a rubric score over a malformed or
# special-cased sweep is meaningless.
set -euo pipefail

echo "=== structural check ==="
python3 /tests/check_universes.py

echo "=== rubric ==="
uvx --from harbor-rewardkit==0.1 rewardkit /tests
