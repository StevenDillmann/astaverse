"""Reading what an analysis produced: artifacts, agent output, history, logs."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from .deps import get_analysis

router = APIRouter(prefix="/api/analyses", tags=["files"])

# Everything else in an analysis directory is container plumbing.
BROWSABLE_SUFFIXES = {
    ".json",
    ".yaml",
    ".yml",
    ".md",
    ".py",
    ".txt",
    ".jsonl",
    ".toml",
    ".log",
    ".sh",
}
MAX_FILE_BYTES = 2_000_000


def _category(parts: tuple[str, ...]) -> str:
    head = parts[0]
    if head == "history":
        return "history"
    if head == "jobs":
        return "agent output" if "artifacts" in parts else "job"
    if head == "harbor_task":
        return "task"
    if head == "universes":
        return "universes"
    return "artifact"


@router.get("/{analysis_id}/files")
def list_files(analysis_id: str) -> list[dict[str, Any]]:
    """Every readable file, including agent output and superseded artifacts."""
    analysis = get_analysis(analysis_id)
    out: list[dict[str, Any]] = []
    for path in sorted(analysis.root.rglob("*")):
        if not path.is_file() or path.suffix not in BROWSABLE_SUFFIXES:
            continue
        rel = path.relative_to(analysis.root)
        stat = path.stat()
        out.append(
            {
                "path": str(rel),
                "name": path.name,
                "category": _category(rel.parts),
                "bytes": stat.st_size,
                "modified": stat.st_mtime,
            }
        )
    return out


@router.get("/{analysis_id}/file")
def read_file(analysis_id: str, path: str) -> dict[str, Any]:
    analysis = get_analysis(analysis_id)
    target = (analysis.root / path).resolve()
    # `path` is client-supplied: refuse anything outside the analysis.
    if not str(target).startswith(str(analysis.root)) or not target.is_file():
        raise HTTPException(404, f"no such file: {path}")
    if target.suffix not in BROWSABLE_SUFFIXES:
        raise HTTPException(415, f"not a readable text file: {path}")
    size = target.stat().st_size
    if size > MAX_FILE_BYTES:
        raise HTTPException(413, f"file is {size} bytes, too large to display")
    return {"path": path, "bytes": size, "content": target.read_text(errors="replace")}


@router.get("/{analysis_id}/history")
def get_history(analysis_id: str) -> list[dict[str, Any]]:
    """Artifact sets superseded by re-running an earlier stage, newest first."""
    return get_analysis(analysis_id).history()


@router.get("/{analysis_id}/log")
def get_log(analysis_id: str) -> dict[str, str]:
    analysis = get_analysis(analysis_id)
    path = analysis.root / "run.log"
    return {"log": path.read_text() if path.exists() else ""}
