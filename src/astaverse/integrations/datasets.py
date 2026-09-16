"""Dataset discovery for the run-creation UI.

Scans one or more roots for usable datasets so a study can be started by
picking one, rather than by typing a path. Canonical AstaVerse dataset folders
contain `data.csv` plus `info.json` with dataset and per-column descriptions.
Bare CSV discovery remains supported for backwards compatibility.
"""

from __future__ import annotations

import csv
import json
import os
import re
import shutil
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

from ..core.schemas import StudySpec
from ..core.stages import s1_study
from ..paths import REPO_ROOT

# Roots to scan, in order. Override with ASTAVERSE_DATASETS (os.pathsep-separated list).
# Bundled reference data lives in data/datasets/ (e.g. hurricane/); user uploads
# land in the same directory but stay gitignored except committed bundles.
DEFAULT_ROOTS = [
    REPO_ROOT / "data" / "datasets",
]

MAX_UPLOAD_BYTES = 50 * 1024 * 1024
MAX_PREVIEW_ROWS = 200


@dataclass
class DatasetInfo:
    name: str
    path: str
    csv_path: str
    kind: str  # "astaverse" | "csv"
    n_columns: int
    n_rows: int | None = None
    description: str | None = None
    columns: list[str] = field(default_factory=list)
    fields: list[dict] = field(default_factory=list)

    def to_dict(self, *, include_fields: bool = False) -> dict:
        data = asdict(self)
        if not include_fields:
            data.pop("fields", None)
        return data


def _normalize_field(field: dict) -> dict:
    props = field.get("properties") or {}
    return {
        "name": field["column"],
        "dtype": props.get("dtype", "string"),
        "description": props.get("description") or None,
        "n_missing": props.get("n_missing"),
        "min": props.get("min"),
        "max": props.get("max"),
        "samples": list(props.get("samples") or []),
        "std": props.get("std"),
        "num_unique_values": props.get("num_unique_values"),
    }


def _fields_from_info(info: dict) -> list[dict]:
    return [
        _normalize_field(field)
        for field in (info.get("data_desc") or {}).get("fields") or []
        if field.get("column")
    ]


def roots() -> list[Path]:
    env = os.environ.get("ASTAVERSE_DATASETS")
    if env:
        return [Path(p).expanduser() for p in env.split(os.pathsep) if p]
    return DEFAULT_ROOTS


def _count_rows(csv_path: Path, limit: int = 200_000) -> int | None:
    """Row count without loading pandas — this runs on every listing."""
    try:
        with csv_path.open(newline="") as fh:
            return max(sum(1 for _ in csv.reader(fh)) - 1, 0)
    except (OSError, csv.Error):
        return None


def _header(csv_path: Path) -> list[str]:
    try:
        with csv_path.open(newline="") as fh:
            return next(csv.reader(fh), [])
    except (OSError, csv.Error, StopIteration):
        return []


def _from_astaverse(folder: Path) -> DatasetInfo | None:
    info_path = folder / "info.json"
    csv_path = folder / "data.csv"
    if not (info_path.exists() and csv_path.exists()):
        return None
    try:
        info = json.loads(info_path.read_text())
    except json.JSONDecodeError:
        return None
    desc = (info.get("data_desc") or {}).get("dataset_description")
    fields = _fields_from_info(info)
    columns = [field["name"] for field in fields] or _header(csv_path)
    return DatasetInfo(
        name=folder.name,
        path=str(folder),
        csv_path=str(csv_path),
        kind="astaverse",
        n_columns=len(columns),
        n_rows=(info.get("data_desc") or {}).get("num_rows") or _count_rows(csv_path),
        description=desc,
        columns=columns,
        fields=fields,
    )


def _from_csv(csv_path: Path) -> DatasetInfo:
    header = _header(csv_path)
    return DatasetInfo(
        name=csv_path.stem,
        path=str(csv_path),
        csv_path=str(csv_path),
        kind="csv",
        n_columns=len(header),
        n_rows=_count_rows(csv_path),
        columns=header,
    )


def discover() -> list[DatasetInfo]:
    """All datasets found across the configured roots, de-duplicated by path."""
    found: dict[str, DatasetInfo] = {}
    for root in roots():
        if not root.is_dir():
            continue
        for entry in sorted(root.iterdir()):
            if entry.is_dir():
                dataset = _from_astaverse(entry)
                if dataset and dataset.path not in found:
                    found[dataset.path] = dataset
            elif entry.suffix == ".csv" and entry.name != "data.csv":
                info = _from_csv(entry)
                if info.path not in found:
                    found[info.path] = info
    return sorted(found.values(), key=lambda d: d.name)


def get(name: str) -> DatasetInfo | None:
    for dataset in discover():
        if dataset.name == name:
            return dataset
    return None


def head(name: str, limit: int = 20) -> dict | None:
    """The first rows of a dataset, for the detail page's preview.

    Streams the CSV and stops after `limit` rows, so a wide or long file costs
    the same as a small one. Values stay as the strings the file holds; the
    schema table already carries the typed view.
    """
    dataset = get(name)
    if dataset is None:
        return None
    limit = max(1, min(limit, MAX_PREVIEW_ROWS))
    header: list[str] = []
    rows: list[list[str]] = []
    try:
        with Path(dataset.csv_path).open(newline="", encoding="utf-8", errors="replace") as fh:
            reader = csv.reader(fh)
            header = next(reader, [])
            for row in reader:
                if len(rows) >= limit:
                    break
                rows.append(row)
    except (OSError, csv.Error):
        header, rows = list(dataset.columns), []
    return {
        "name": dataset.name,
        "columns": header,
        "rows": rows,
        "n_rows": dataset.n_rows,
        "limit": limit,
    }


def delete(name: str) -> bool:
    """Delete one discovered dataset without escaping a configured root."""
    dataset = get(name)
    if dataset is None:
        return False
    target = Path(dataset.path).resolve()
    allowed_roots = {configured.resolve() for configured in roots()}
    if target.parent not in allowed_roots:
        raise ValueError("dataset is not a direct child of a configured dataset root")
    if target.is_dir():
        shutil.rmtree(target)
    else:
        target.unlink()
    return True


def upload_root() -> Path:
    """Writable root for user-uploaded datasets (first configured scan root)."""
    root = roots()[0]
    root.mkdir(parents=True, exist_ok=True)
    return root


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower().strip())
    slug = slug.strip("-")
    if not slug:
        raise ValueError("dataset name must contain at least one letter or number")
    return slug


def _validate_upload(content: bytes) -> None:
    if not content.strip():
        raise ValueError("file is empty")
    if len(content) > MAX_UPLOAD_BYTES:
        limit_mb = MAX_UPLOAD_BYTES // (1024 * 1024)
        raise ValueError(f"file exceeds {limit_mb}MB limit")


def profile_upload(
    content: bytes,
    *,
    name: str,
    description: str | None = None,
    column_descriptions: dict[str, str] | None = None,
) -> StudySpec:
    """Profile CSV bytes without persisting them."""
    _validate_upload(content)
    slug = slugify(name)
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as handle:
        handle.write(content)
        csv_path = Path(handle.name)
    try:
        return s1_study.profile(
            csv_path,
            dataset_name=slug,
            dataset_description=description,
            column_descriptions=column_descriptions,
        )
    except Exception as exc:
        message = str(exc)
        if "EmptyDataError" in type(exc).__name__ or "No columns" in message:
            raise ValueError("CSV must have a header row and at least one data row") from exc
        if "ParserError" in type(exc).__name__ or "Error tokenizing" in message:
            raise ValueError(f"invalid CSV: {message}") from exc
        raise
    finally:
        csv_path.unlink(missing_ok=True)


def _preview_from_spec(spec: StudySpec, *, available: bool) -> dict:
    return {
        "name": spec.dataset_name,
        "n_rows": spec.n_rows,
        "n_columns": len(spec.columns),
        "description": spec.dataset_description,
        "columns": [column.model_dump() for column in spec.columns],
        "available": available,
    }


def preview_upload(
    content: bytes,
    *,
    name: str,
    description: str | None = None,
    column_descriptions: dict[str, str] | None = None,
) -> dict:
    slug = slugify(name)
    spec = profile_upload(
        content,
        name=slug,
        description=description,
        column_descriptions=column_descriptions,
    )
    return _preview_from_spec(spec, available=get(slug) is None)


def import_upload(
    content: bytes,
    *,
    name: str,
    description: str | None = None,
    column_descriptions: dict[str, str] | None = None,
) -> DatasetInfo:
    """Persist an uploaded CSV as a canonical AstaVerse dataset folder."""
    slug = slugify(name)
    if get(slug) is not None:
        raise ValueError(f"dataset '{slug}' already exists")

    spec = profile_upload(
        content,
        name=slug,
        description=description,
        column_descriptions=column_descriptions,
    )
    folder = upload_root() / slug
    if folder.exists():
        raise ValueError(f"dataset '{slug}' already exists")

    folder.mkdir(parents=True, exist_ok=False)
    csv_path = folder / "data.csv"
    csv_path.write_bytes(content)
    info_path = folder / "info.json"
    info_path.write_text(json.dumps(s1_study.info_json_from_spec(spec), indent=2) + "\n")

    dataset = _from_astaverse(folder)
    if dataset is None:
        shutil.rmtree(folder)
        raise ValueError("failed to register uploaded dataset")
    return dataset
