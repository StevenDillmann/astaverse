#!/usr/bin/env python3
"""Hand-written reference multiverse for the BLADE `hurricane` study.

Two jobs:

1. It is the oracle solution for the emitted Harbor task — copy it in as
   `/app/reference_analysis.py` to run `harbor run -a oracle`, and to
   spot-check an agent's parametric sweep against known-good cells.
2. Run directly, it produces a real `universes.jsonl` with no LLM anywhere in
   the path, which is enough to answer the motivating question: does this
   multiverse actually split on the minimum-pressure direction?

The decision axes are the ones documented in the sibling experiments repo's
`findings/hurricane__node_0.md`, plus the standard specification-curve choices
from Simonsohn et al., whose paper this dataset comes from.

Usage:
    python scripts/hurricane_reference.py --data <path/to/data.csv> \
        --universes <dir of universe_*.yaml> --out universes.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
import yaml


def analyze(df: pd.DataFrame, selections: dict[str, str]) -> dict:
    """Run the analysis for ONE universe.

    Every analytic choice is driven by `selections`; nothing branches on the
    universe id. This is the structure the Harbor task requires of the agent.
    """
    data = df.copy()

    # -- outcome ----------------------------------------------------------
    outcome = selections.get("outcome_transform", "raw")
    y = data["alldeaths"].astype(float)
    if outcome == "log1p":
        y = np.log1p(y)

    # -- femininity operationalisation ------------------------------------
    fem = selections.get("femininity_measure", "continuous")
    x = data["masfem"].astype(float) if fem == "continuous" else data["gender_mf"].astype(float)

    # -- minimum pressure direction ---------------------------------------
    # The documented fork. `min` is minimum pressure, so LOWER means a stronger
    # storm, while category and wind both run higher = stronger. Averaging raw
    # z-scores without negating pressure yields a near-meaningless composite
    # (the reference implementation got r=0.039 this way); negating it aligns
    # all three components and gives r=0.240.
    #
    # This choice bites only where the severity *index* is used. As a plain
    # OLS control, negating one regressor cannot change any other coefficient
    # — an inert axis, which the sensitivity table will report as such.
    direction = selections.get("min_pressure_direction", "raw")
    pressure = data["min"].astype(float)
    if direction == "flipped":
        pressure = -pressure

    def zscore(s: pd.Series) -> pd.Series:
        return (s - s.mean()) / s.std(ddof=0)

    severity = (
        zscore(data["category"].astype(float))
        + zscore(data["wind"].astype(float))
        + zscore(pressure)
    ) / 3.0

    # -- outlier handling --------------------------------------------------
    frame = pd.DataFrame(
        {
            "y": y,
            "x": x,
            "pressure": pressure,
            "severity": severity,
            "damage": data["ndam"].astype(float),
        }
    )
    frame = frame.dropna()
    outliers = selections.get("outlier_handling", "keep")
    if outliers == "drop_extreme_deaths":
        # Katrina and Audrey dominate the outcome; dropping them is a standard
        # robustness check in the original literature.
        cutoff = frame["y"].quantile(0.98)
        frame = frame[frame["y"] <= cutoff]

    # -- covariates --------------------------------------------------------
    covariates = selections.get("covariates", "severity_damage")
    columns = {"x": frame["x"]}
    if covariates in ("severity_damage", "severity_only"):
        columns["severity"] = frame["severity"]
    if covariates == "pressure_damage":
        columns["pressure"] = frame["pressure"]
    if covariates in ("severity_damage", "pressure_damage", "damage_only"):
        columns["damage"] = np.log1p(frame["damage"])

    design = sm.add_constant(pd.DataFrame(columns), has_constant="add")

    # -- model family ------------------------------------------------------
    # Deaths are an overdispersed count, and the original paper used negative
    # binomial regression. OLS on the same data is the more common default.
    family = selections.get("model_family", "ols")

    try:
        if family == "negative_binomial":
            model = sm.GLM(
                frame["y"], design, family=sm.families.NegativeBinomial(alpha=1.0)
            ).fit()
        else:
            model = sm.OLS(frame["y"], design).fit()
        estimate = float(model.params["x"])
        std_error = float(model.bse["x"])
        p_value = float(model.pvalues["x"])
        converged = bool(np.isfinite(estimate) and np.isfinite(p_value))
    except Exception as exc:  # noqa: BLE001
        return {
            "estimate": None,
            "std_error": None,
            "p_value": None,
            "n": int(len(frame)),
            "direction": None,
            "converged": False,
            "notes": f"fit failed: {exc}",
        }

    if not converged:
        direction_label = None
    elif estimate > 0:
        direction_label = "positive"
    elif estimate < 0:
        direction_label = "negative"
    else:
        direction_label = "none"

    return {
        "estimate": estimate,
        "std_error": std_error,
        "p_value": p_value,
        "n": int(len(frame)),
        "direction": direction_label,
        "converged": converged,
        "notes": None,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="/app/data.csv")
    parser.add_argument("--universes", default="/app/universes")
    parser.add_argument("--out", default="/app/universes.jsonl")
    args = parser.parse_args()

    df = pd.read_csv(args.data)
    universe_files = sorted(Path(args.universes).glob("universe_*.yaml"))
    if not universe_files:
        print(f"no universe files in {args.universes}", file=sys.stderr)
        return 1

    rows = []
    for path in universe_files:
        doc = yaml.safe_load(path.read_text())
        selections = {d["decision_id"]: d["option_id"] for d in doc["decisions"]}
        rows.append({"universe_id": doc["id"], "decisions": selections, **analyze(df, selections)})

    Path(args.out).write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    print(f"wrote {len(rows)} universes to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
