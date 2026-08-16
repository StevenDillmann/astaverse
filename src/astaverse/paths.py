"""Where the repo's non-Python assets live.

Resolved once, from this module's own location, so moving a module deeper in
the package cannot silently break a path. The previous code counted
`parents[3]` from inside a stage; restructuring the package changed that depth
and would have failed only at runtime, when emitting a task.
"""

from __future__ import annotations

from pathlib import Path

#: src/astaverse/paths.py -> src/astaverse -> src -> repo root
PACKAGE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_ROOT.parents[1]

TEMPLATES = REPO_ROOT / "templates"
HARBOR_TASK_TEMPLATE = TEMPLATES / "harbor_task"
WEB_DIST = REPO_ROOT / "web" / "dist"
