"""s1 — study: hypothesis + dataset -> StudySpec.

Profiles the dataset so later stages can describe it to a model accurately.
Where the dataset is a BLADE folder, its `info.json` already carries
expert-written column descriptions and research questions; prefer those over
anything we could infer from the CSV alone.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..schemas import Column, StudySpec
from ..store import Run


def _blade_info(dataset_path: Path) -> tuple[Path, dict | None]:
    """Resolve a dataset path to (csv_path, blade_info_or_None)."""
    if dataset_path.is_dir():
        info_path = dataset_path / "info.json"
        csv_path = dataset_path / "data.csv"
        if info_path.exists() and csv_path.exists():
            return csv_path, json.loads(info_path.read_text())
        csvs = sorted(dataset_path.glob("*.csv"))
        if not csvs:
            raise FileNotFoundError(f"no CSV found in {dataset_path}")
        return csvs[0], None
    # A CSV sitting inside a BLADE folder still has its info.json alongside.
    sibling = dataset_path.parent / "info.json"
    if sibling.exists():
        return dataset_path, json.loads(sibling.read_text())
    return dataset_path, None


def _columns_from_blade(info: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for field in (info.get("data_desc") or {}).get("fields") or []:
        out[field["column"]] = field.get("properties") or {}
    return out


def run(
    run_obj: Run,
    hypothesis: str,
    dataset: str | Path,
    dataset_description: str | None = None,
) -> StudySpec:
    import pandas as pd

    dataset_path = Path(dataset).expanduser().resolve()
    if not dataset_path.exists():
        raise FileNotFoundError(f"dataset not found: {dataset_path}")

    csv_path, info = _blade_info(dataset_path)
    df = pd.read_csv(csv_path)
    blade_cols = _columns_from_blade(info) if info else {}

    columns: list[Column] = []
    for name in df.columns:
        series = df[name]
        props = blade_cols.get(name, {})
        numeric = pd.api.types.is_numeric_dtype(series)
        columns.append(
            Column(
                name=str(name),
                dtype=props.get("dtype") or ("number" if numeric else "string"),
                description=props.get("description") or None,
                n_missing=int(series.isna().sum()),
                min=float(series.min()) if numeric and series.notna().any() else None,
                max=float(series.max()) if numeric and series.notna().any() else None,
                samples=[
                    None if pd.isna(v) else (v.item() if hasattr(v, "item") else v)
                    for v in series.dropna().head(3).tolist()
                ],
            )
        )

    description = dataset_description
    if description is None and info:
        description = (info.get("data_desc") or {}).get("dataset_description")

    spec = StudySpec(
        hypothesis=hypothesis,
        dataset_path=str(csv_path),
        dataset_name=csv_path.parent.name if csv_path.name == "data.csv" else csv_path.stem,
        dataset_description=description,
        n_rows=int(len(df)),
        columns=columns,
        research_questions=list((info or {}).get("research_questions") or []),
    )

    run_obj.write_artifact("study", spec)
    run_obj.record_stage(
        "study", dataset=str(csv_path), n_rows=spec.n_rows, n_columns=len(columns)
    )
    run_obj.log("study", f"profiled {csv_path} ({spec.n_rows} rows, {len(columns)} columns)")
    return spec


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
