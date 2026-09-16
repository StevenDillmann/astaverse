"""s1 — study: hypothesis + dataset -> StudySpec.

Profiles the dataset so later stages can describe it to a model accurately.
Where the dataset is an AstaVerse bundle, its `info.json` carries dataset and
per-column descriptions; prefer those over anything inferred from the CSV.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from ..schemas import Column, StudySpec
from ..store import Run


def _dataset_info(dataset_path: Path) -> tuple[Path, dict | None]:
    """Resolve a dataset path to its CSV and optional AstaVerse metadata."""
    if dataset_path.is_dir():
        info_path = dataset_path / "info.json"
        csv_path = dataset_path / "data.csv"
        if info_path.exists() and csv_path.exists():
            return csv_path, json.loads(info_path.read_text())
        csvs = sorted(dataset_path.glob("*.csv"))
        if not csvs:
            raise FileNotFoundError(f"no CSV found in {dataset_path}")
        return csvs[0], None
    sibling = dataset_path.parent / "info.json"
    if sibling.exists():
        return dataset_path, json.loads(sibling.read_text())
    return dataset_path, None


def _columns_from_info(info: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for field in (info.get("data_desc") or {}).get("fields") or []:
        out[field["column"]] = field.get("properties") or {}
    return out


def _infer_dtype(series: pd.Series) -> str:
    if pd.api.types.is_numeric_dtype(series):
        return "number"
    if pd.api.types.is_bool_dtype(series):
        return "category"
    nunique = int(series.nunique(dropna=True))
    if nunique <= 20:
        return "category"
    return "string"


def _sample_values(series: pd.Series) -> list[Any]:
    values: list[Any] = []
    for value in series.dropna().head(3).tolist():
        if pd.isna(value):
            values.append(None)
        elif hasattr(value, "item"):
            values.append(value.item())
        else:
            values.append(value)
    return values


def _column_from_series(name: str, series: pd.Series, props: dict[str, Any] | None = None) -> Column:
    props = props or {}
    numeric = pd.api.types.is_numeric_dtype(series)
    dtype = props.get("dtype") or _infer_dtype(series)
    nunique = int(series.nunique(dropna=True))
    std = float(series.std()) if numeric and series.notna().any() else None
    min_val = float(series.min()) if numeric and series.notna().any() else props.get("min")
    max_val = float(series.max()) if numeric and series.notna().any() else props.get("max")
    if min_val is not None and not isinstance(min_val, (int, float)):
        min_val = None
    if max_val is not None and not isinstance(max_val, (int, float)):
        max_val = None
    return Column(
        name=str(name),
        dtype=dtype,
        description=props.get("description") or None,
        n_missing=int(series.isna().sum()),
        min=min_val,
        max=max_val,
        samples=_sample_values(series) if not props.get("samples") else list(props.get("samples") or []),
        std=props.get("std") if props.get("std") is not None else std,
        num_unique_values=props.get("num_unique_values") or nunique,
    )


def profile(
    dataset: str | Path,
    *,
    hypothesis: str = "",
    dataset_name: str | None = None,
    dataset_description: str | None = None,
    column_descriptions: dict[str, str] | None = None,
) -> StudySpec:
    """Profile a dataset path without writing pipeline artifacts."""
    dataset_path = Path(dataset).expanduser().resolve()
    if not dataset_path.exists():
        raise FileNotFoundError(f"dataset not found: {dataset_path}")

    csv_path, info = _dataset_info(dataset_path)
    df = pd.read_csv(csv_path)
    if df.empty or len(df.columns) == 0:
        raise ValueError("CSV must have a header row and at least one data row")
    described_columns = _columns_from_info(info) if info else {}

    columns = [
        _column_from_series(name, df[name], described_columns.get(str(name), {}))
        for name in df.columns
    ]
    if column_descriptions:
        columns = [
            col.model_copy(
                update={
                    "description": column_descriptions[col.name].strip() or None,
                }
            )
            if col.name in column_descriptions
            else col
            for col in columns
        ]

    description = dataset_description
    if description is None and info:
        description = (info.get("data_desc") or {}).get("dataset_description")

    resolved_name = dataset_name or (
        csv_path.parent.name if csv_path.name == "data.csv" else csv_path.stem
    )

    return StudySpec(
        hypothesis=hypothesis,
        dataset_path=str(csv_path),
        dataset_name=resolved_name,
        dataset_description=description,
        n_rows=len(df),
        columns=columns,
    )


def run(
    run_obj: Run,
    hypothesis: str,
    dataset: str | Path,
    dataset_description: str | None = None,
) -> StudySpec:
    spec = profile(dataset, hypothesis=hypothesis, dataset_description=dataset_description)

    run_obj.write_artifact("study", spec)
    run_obj.record_stage(
        "study",
        dataset=spec.dataset_path,
        n_rows=spec.n_rows,
        n_columns=len(spec.columns),
    )
    run_obj.log(
        "study",
        f"profiled {spec.dataset_path} ({spec.n_rows} rows, {len(spec.columns)} columns)",
    )
    return spec


def info_json_from_spec(spec: StudySpec) -> dict:
    """Canonical AstaVerse metadata for a profiled dataset."""
    fields = []
    for col in spec.columns:
        props: dict[str, object] = {
            "dtype": col.dtype,
            "description": col.description or "",
            "semantic_type": "",
            "num_unique_values": col.num_unique_values,
            "samples": col.samples,
        }
        if col.min is not None:
            props["min"] = col.min
        if col.max is not None:
            props["max"] = col.max
        if col.std is not None:
            props["std"] = col.std
        if col.n_missing is not None:
            props["n_missing"] = col.n_missing
        fields.append({"column": col.name, "properties": props})
    return {
        "data_desc": {
            "dataset_description": spec.dataset_description or "",
            "fields": fields,
            "field_names": [col.name for col in spec.columns],
            "num_rows": spec.n_rows,
        }
    }


def render_columns_markdown(spec: StudySpec) -> str:
    """Column table shared by the s2/s3 prompts and the Harbor instruction."""
    lines = ["| column | dtype | range | description |", "|---|---|---|---|"]
    for col in spec.columns:
        if col.min is not None and col.max is not None:
            rng = f"{col.min:g} – {col.max:g}"
        else:
            samples = ", ".join(str(s) for s in col.samples[:3])
            rng = f"e.g. {samples}" if samples else ""
        lines.append(f"| `{col.name}` | {col.dtype} | {rng} | {col.description or ''} |")
    return "\n".join(lines)
