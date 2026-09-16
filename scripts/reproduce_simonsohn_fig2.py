#!/usr/bin/env python3
"""Reproduce Figure 2 of Simonsohn, Simmons & Nelson (2020) inside Astaverse.

"Specification curve analysis", Nature Human Behaviour 4, 1208–1214. Figure 2
is the descriptive specification curve for Jung et al.'s (2014) claim that
female-named hurricanes kill more people: 1,728 specifications, each plotted
as the extra deaths predicted for a female versus a male name.

What this script does, end to end and with no LLM in the path:

1. Downloads the authors' data (`hurricanes_2015_01_09.dta`) and code from
   OSF (https://osf.io/9rvps/), applies their data-preparation step, and
   imports the result as a new AstaVerse dataset (`hurricane-simonsohn`).
2. Creates a hypothesis and an experiment on that dataset.
3. Writes the paper's seven analytic decisions as the experiment's decision
   space (stage 3), enumerates the full 1,728-universe grid (stage 4) and
   emits the Harbor task (stage 5).
4. Executes the sweep locally with `scripts/simonsohn_fig2_reference.py` — a
   port of the authors' Stata program — in the job layout stage 6 would have
   produced, and runs the task's structural verifier over the output.
5. Converts statistics to verdicts (stage 7), so the experiment page shows the
   specification curve.
6. Compares every universe against the authors' own results file
   (`specifications_hurricanes.dta`) and renders the figure.

Usage:
    uv run --with matplotlib python scripts/reproduce_simonsohn_fig2.py
"""

from __future__ import annotations

import argparse
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import simonsohn_fig2_reference as reference

from astaverse.core import claims as claims_core
from astaverse.core import config as run_cfg
from astaverse.core import settings as app_settings
from astaverse.core.schemas import Decision, DecisionKind, DecisionSpec, Option
from astaverse.core.stages import s1_study, s4_universes, s5_task, s7_verdicts
from astaverse.core.stages.s3_decisions import _verdict_rule_decision
from astaverse.core.stages.s6_execute import ExecuteArtifact, JobRecord, _job_name
from astaverse.core.store import Run
from astaverse.integrations import datasets, hypotheses
from astaverse.integrations.astra_io import write_astra_yaml

OSF_DATA_URL = "https://osf.io/download/w3br2/"  # hurricanes_2015_01_09.dta
OSF_CODE_URL = "https://osf.io/download/tqpru/"  # Specification Curve.zip (Stata)
STATA_RESULTS = "Results for plotting/specifications_hurricanes.dta"

DATASET_NAME = "hurricane-simonsohn"
HYPOTHESIS = (
    "Hurricanes with more feminine names cause more deaths, "
    "because people take fewer precautions against them."
)
AGENT = "local-statsmodels"

DATASET_DESCRIPTION = (
    "Jung et al.'s (2014) hurricane data as prepared by Simonsohn, Simmons and Nelson "
    "for the specification-curve analysis in Figure 2 of 'Specification curve analysis' "
    "(Nature Human Behaviour, 2020; data and Stata code at https://osf.io/9rvps/). "
    "94 Atlantic hurricanes that made landfall in the United States between 1950 and 2012. "
    "Following the authors' file '(6) Jung et al - Getting data ready', femininity is the "
    "32-rater MTurk rating (so that Katrina and Audrey, absent from the original 9-rater "
    "index, can be analysed), damages are the 2015-dollar normalised values, and the "
    "derived columns lnd, lndam, post79, zmin, zwin, zcat and z3 are the ones the 1,728 "
    "specifications use. The original 9-rater femininity index and 2013-dollar damages "
    "are kept for reference."
)

COLUMN_DESCRIPTIONS = {
    "year": "Year of US landfall.",
    "name": "Name of the hurricane.",
    "female": "1 if the name is female, 0 if male (Jung et al.'s Gender_MF).",
    "masfem": (
        "Femininity of the name: mean rating of 32 MTurk respondents on a 1 (very masculine) "
        "to 11 (very feminine) scale. Replaces the 9-rater index in the specification curve."
    ),
    "masfem_9raters": (
        "Jung et al.'s original masculinity-femininity index from 9 coders (1-11). "
        "Not used by the specification curve."
    ),
    "min": "Minimum central pressure at landfall in millibars (NOAA). Lower means more intense.",
    "wind": "Maximum sustained wind speed at landfall in mph; added by Simonsohn et al.",
    "category": "Saffir-Simpson category at landfall (1-5).",
    "alldeaths": "Total deaths attributed to the hurricane.",
    "dam": (
        "Normalised property damage in millions of 2015 dollars (Jung et al.'s NDAM updated), "
        "as used in the specification curve."
    ),
    "ndam_2013": (
        "Jung et al.'s original normalised damage in millions of 2013 dollars (two values "
        "missing). Not used by the specification curve."
    ),
    "elapsedyrs": "Years elapsed between the hurricane and 2013.",
    "source": "Source of the death count (MWR = Monthly Weather Review).",
    "lnd": "log(alldeaths + 1): the outcome of the OLS specifications.",
    "lndam": "log(dam): the log-damages functional form.",
    "post79": "1 if year > 1979, when hurricanes began to receive male names; else 0.",
    "zmin": (
        "Standardised minimum pressure with the sign flipped, so that higher values mean a "
        "more intense storm."
    ),
    "zwin": "Standardised maximum wind speed.",
    "zcat": "Standardised Saffir-Simpson category.",
    "z3": "Mean of zmin, zwin and zcat: a composite storm-intensity index.",
}

# Simonsohn's loop counters k1..k7 -> the decision ids/options used here.
STATA_LEVELS: dict[str, dict[int, str]] = {
    "outliers": {1: "keep_all", 2: "drop_katrina", 3: "drop_katrina_audrey"},
    "leverage_points": {1: "keep_all", 2: "below_75260", 3: "below_62030", 4: "below_52270"},
    "femininity": {1: "female_binary", 2: "masfem_rating"},
    "model": {1: "ols_log_deaths", 2: "negative_binomial"},
    "damages_form": {1: "dollars", 2: "log_dollars"},
    "intensity_terms": {
        1: "damages_only",
        2: "damages_and_pressure",
        3: "damages_and_wind",
        4: "damages_and_category",
        5: "damages_and_mean_intensity",
        6: "main_effects_only",
    },
    "year_control": {1: "none", 2: "year_x_damages", 3: "post79_x_damages"},
}
STATA_COLUMNS = ["k1", "k2", "k3", "k4", "k5", "k6", "k7"]
DECISION_ORDER = list(STATA_LEVELS)

# Figure 2's dashboard labels, in the paper's wording.
FIGURE_LABELS: dict[str, tuple[str, dict[str, str]]] = {
    "outliers": (
        "Dropping outliers",
        {
            "keep_all": "Drop none",
            "drop_katrina": "Drop 1 highest deaths",
            "drop_katrina_audrey": "Drop 2 highest deaths",
        },
    ),
    "leverage_points": (
        "Dropping leverage points",
        {
            "keep_all": "Drop none",
            "below_75260": "Drop 1 highest damages",
            "below_62030": "Drop 2 highest damages",
            "below_52270": "Drop 3 highest damages",
        },
    ),
    "femininity": (
        "Femininity of name",
        {"female_binary": "Female (1/0)", "masfem_rating": "Rating on Likert scale (1–11)"},
    ),
    "model": (
        "Model",
        {"ols_log_deaths": "Log(fatalities + 1)", "negative_binomial": "Negative binomial"},
    ),
    "damages_form": (
        "Functional form for damages",
        {"dollars": "Linear: $", "log_dollars": "Log: ln($)"},
    ),
    "intensity_terms": (
        "Femininity of name: main effect or interaction with intensity",
        {
            "damages_only": "Interaction with damages",
            "damages_and_pressure": "Interaction with damages and min. pressure",
            "damages_and_wind": "Interaction with damages & wind",
            "damages_and_category": "Interaction with damages and hurricane category",
            "damages_and_mean_intensity": "Interaction with damages and with mean (pressure, wind, category)",
            "main_effects_only": "Main effect",
        },
    ),
    "year_control": (
        "Controlling for year",
        {"none": "None", "year_x_damages": "Year × damages", "post79_x_damages": "Post 1979 (1/0) × damages"},
    ),
}


# --------------------------------------------------------------------------
# 1. data
# --------------------------------------------------------------------------


def download(url: str, target: Path) -> Path:
    if target.exists():
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "astaverse-reproduction/0.1"})
    with urllib.request.urlopen(request, timeout=120) as response:
        target.write_bytes(response.read())
    return target


def fetch_stata_results(cache_dir: Path) -> pd.DataFrame:
    """The authors' 1,728 estimates, from `Specification Curve.zip` on OSF."""
    archive = download(OSF_CODE_URL, cache_dir / "Specification Curve.zip")
    with zipfile.ZipFile(archive) as bundle:
        return pd.read_stata(io.BytesIO(bundle.read(STATA_RESULTS)))


def prepare_dataset(dta_path: Path) -> pd.DataFrame:
    """Port of `(6) Jung et al - Getting data ready - 2015 02 19.do`."""
    raw = pd.read_stata(dta_path)
    df = pd.DataFrame(
        {
            "year": raw["year"].astype(int),
            "name": raw["name"],
            "female": raw["gender_mf"].astype(int),
            "masfem": raw["masfem_mturk"].astype(float),
            "masfem_9raters": raw["masfem"].astype(float),
            "min": raw["min"].astype(int),
            "wind": raw["wind"].astype(int),
            "category": raw["category"].astype(int),
            "alldeaths": raw["alldeaths"].astype(int),
            "dam": raw["ndam15"].astype(float),
            "ndam_2013": raw["ndam"],
            "elapsedyrs": raw["elapsedyrs"],
            "source": raw["source"],
        }
    )
    df["lnd"] = np.log1p(df["alldeaths"])
    df["lndam"] = np.log(df["dam"])
    df["post79"] = (df["year"] > 1979).astype(int)

    def standardise(series: pd.Series) -> pd.Series:  # Stata `egen std()` uses the sample SD
        return (series - series.mean()) / series.std(ddof=1)

    df["zmin"] = -standardise(df["min"].astype(float))
    df["zwin"] = standardise(df["wind"].astype(float))
    df["zcat"] = standardise(df["category"].astype(float))
    df["z3"] = (df["zmin"] + df["zwin"] + df["zcat"]) / 3
    return df


def ensure_dataset(cache_dir: Path, name: str):
    existing = datasets.get(name)
    if existing is not None:
        print(f"dataset {name}: already imported at {existing.path}")
        return existing
    dta = download(OSF_DATA_URL, cache_dir / "hurricanes_2015_01_09.dta")
    prepared = prepare_dataset(dta)
    created = datasets.import_upload(
        prepared.to_csv(index=False).encode(),
        name=name,
        description=DATASET_DESCRIPTION,
        column_descriptions=COLUMN_DESCRIPTIONS,
    )
    (Path(created.path) / "SOURCE.md").write_text(
        "# Source\n\n"
        f"- Data: `hurricanes_2015_01_09.dta` from {OSF_DATA_URL} (OSF project https://osf.io/9rvps/,\n"
        "  Simonsohn, Simmons & Nelson 2020, *Specification curve analysis*, Nat. Hum. Behav.).\n"
        "- Preparation: `scripts/reproduce_simonsohn_fig2.py::prepare_dataset`, a port of the authors'\n"
        "  Stata file `(6) Jung et al - Getting data ready - 2015 02 19.do`.\n"
        "- Original study: Jung, Shavitt, Viswanathan & Hilbe (2014), PNAS 111(24), 8782–8787.\n"
    )
    print(f"dataset {name}: imported {created.n_rows} rows x {created.n_columns} columns")
    return created


# --------------------------------------------------------------------------
# 2–3. experiment and decision space
# --------------------------------------------------------------------------


def decision_space(hypothesis: str, dataset_path: str, dataset_name: str) -> DecisionSpec:
    """The seven loops of Simonsohn's Stata program, defaults = Jung et al.'s model."""
    decisions: dict[str, Decision] = {
        "outliers": Decision(
            label="Dropping outliers",
            rationale=(
                "Two storms (Katrina, 1,833 deaths; Audrey, 416) dominate the death counts. "
                "Jung et al. excluded both; critics argued about which, if any, to drop."
            ),
            default="drop_katrina_audrey",
            kind=DecisionKind.preprocessing,
            options={
                "keep_all": Option(label="Drop none", description="All 94 landfalling hurricanes."),
                "drop_katrina": Option(
                    label="Drop 1 highest deaths",
                    description="Keep storms with fewer than 1,833 deaths: excludes Katrina.",
                ),
                "drop_katrina_audrey": Option(
                    label="Drop 2 highest deaths",
                    description="Keep storms with fewer than 416 deaths: excludes Katrina and Audrey, as Jung et al. did.",
                ),
            },
        ),
        "leverage_points": Decision(
            label="Dropping leverage points",
            rationale=(
                "Normalised damages are extremely skewed, so the costliest storms have high "
                "leverage on any damages term. The thresholds are the ones in the authors' code."
            ),
            default="keep_all",
            kind=DecisionKind.preprocessing,
            options={
                "keep_all": Option(label="Drop none", description="No damages threshold."),
                "below_75260": Option(
                    label="Drop 1 highest damages",
                    description="Keep storms with damages below $75,260M (2015 dollars). With the updated damages this excludes Katrina ($88,420M) and Andrew ($75,260M).",
                ),
                "below_62030": Option(
                    label="Drop 2 highest damages",
                    description="Keep storms with damages below $62,030M: additionally excludes Donna.",
                ),
                "below_52270": Option(
                    label="Drop 3 highest damages",
                    description="Keep storms with damages below $52,270M: additionally excludes Sandy.",
                ),
            },
        ),
        "femininity": Decision(
            label="Femininity of name",
            rationale="The construct is the perceived gender of the name; it can be a dummy or a graded rating.",
            default="masfem_rating",
            kind=DecisionKind.variable_choice,
            options={
                "female_binary": Option(
                    label="Female (1/0)",
                    description="The binary gender of the name (`female`); predictions compare female = 1 with female = 0.",
                ),
                "masfem_rating": Option(
                    label="Rating on Likert scale (1–11)",
                    description="The MTurk femininity rating (`masfem`); predictions compare 8.29 with 2.53, the mean ratings of female- and male-named storms.",
                ),
            },
        ),
        "model": Decision(
            label="Model",
            rationale="Deaths are an over-dispersed count. Jung et al. fit a negative binomial; OLS on log(deaths + 1) is the common alternative.",
            default="negative_binomial",
            kind=DecisionKind.model,
            options={
                "ols_log_deaths": Option(
                    label="Log(fatalities + 1)",
                    description="OLS on `lnd` with HC1 robust standard errors; predicted deaths are exp(prediction) rescaled by the smearing factor from regressing deaths on exp(fitted) - 1 without a constant.",
                ),
                "negative_binomial": Option(
                    label="Negative binomial",
                    description="NB2 negative binomial on `alldeaths` by maximum likelihood with robust (sandwich) standard errors.",
                ),
            },
        ),
        "damages_form": Decision(
            label="Functional form for damages",
            rationale="Damages enter every specification; whether they enter linearly or in logs is a free choice.",
            default="dollars",
            kind=DecisionKind.variable_choice,
            options={
                "dollars": Option(label="Linear: $", description="Damages in millions of 2015 dollars (`dam`)."),
                "log_dollars": Option(label="Log: ln($)", description="Natural log of damages (`lndam`)."),
            },
        ),
        "intensity_terms": Decision(
            label="Femininity of name: main effect or interaction with intensity",
            rationale=(
                "Jung et al.'s hypothesis is that femininity matters more for severe storms, so they "
                "interacted femininity with damages and with minimum pressure. Other intensity measures, "
                "or no interaction at all, are equally defensible."
            ),
            default="damages_and_pressure",
            kind=DecisionKind.model,
            options={
                "damages_only": Option(
                    label="Interaction with damages",
                    description="femininity × damages, damages, femininity.",
                ),
                "damages_and_pressure": Option(
                    label="Interaction with damages and min. pressure",
                    description="Adds zmin and femininity × zmin (Jung et al.'s model).",
                ),
                "damages_and_wind": Option(
                    label="Interaction with damages & wind",
                    description="Adds zwin and femininity × zwin.",
                ),
                "damages_and_category": Option(
                    label="Interaction with damages and hurricane category",
                    description="Adds zcat and femininity × zcat.",
                ),
                "damages_and_mean_intensity": Option(
                    label="Interaction with damages and with mean (pressure, wind, category)",
                    description="Adds z3 and femininity × z3.",
                ),
                "main_effects_only": Option(
                    label="Main effect",
                    description="femininity, damages and z3 as main effects, no interactions.",
                ),
            },
        ),
        "year_control": Decision(
            label="Controlling for year",
            rationale="Deaths per unit of damage have fallen over time; the year can be ignored, entered linearly, or as a pre/post-1979 indicator (when male names were introduced), each interacted with damages.",
            default="none",
            kind=DecisionKind.variable_choice,
            options={
                "none": Option(label="None", description="No year terms."),
                "year_x_damages": Option(label="Year × damages", description="Adds year and year × damages."),
                "post79_x_damages": Option(label="Post 1979 (1/0) × damages", description="Adds post79 and post79 × damages."),
            },
        ),
        "verdict_rule": _verdict_rule_decision(),
    }
    return DecisionSpec(
        id=f"{dataset_name}_multiverse",
        name=f"{dataset_name}: Simonsohn et al. (2020) Figure 2",
        description=(
            "The 1,728 specifications of Figure 2 in Simonsohn, Simmons & Nelson (2020), "
            "transcribed from the authors' Stata program '(7) Jung et al - Descriptive "
            "Specification Curve.do'. Defaults reproduce Jung et al.'s original model."
        ),
        hypothesis=hypothesis,
        dataset_path=dataset_path,
        decisions=decisions,
    )


def create_experiment(runs_dir: Path, dataset) -> Run:
    hypothesis_id = claims_core.claim_id(HYPOTHESIS, dataset.path)
    hypotheses.save(hypothesis_id, HYPOTHESIS, dataset.path)
    run = Run.create(runs_dir, HYPOTHESIS, dataset.path)
    app_settings.apply_to_manifest(run, app_settings.load(runs_dir))
    # No plans are sampled: the decision space is transcribed from the paper.
    run_cfg.update(run, {"decisions": {"mode": "direct"}, "through": "verdicts"})
    s1_study.run(run, HYPOTHESIS, dataset.path)
    return run


# --------------------------------------------------------------------------
# 4–5. local execution in the stage-6 job layout
# --------------------------------------------------------------------------


def execute_locally(run: Run) -> Path:
    task_dir = run.task_dir
    job_name = _job_name(run.run_id, AGENT, None)
    job_dir = run.jobs_dir / job_name
    app = job_dir / "artifacts" / "app"
    if job_dir.exists():
        shutil.rmtree(job_dir)
    app.mkdir(parents=True)
    shutil.copyfile(task_dir / "environment" / "data.csv", app / "data.csv")
    shutil.copyfile(task_dir / "environment" / "astra.yaml", app / "astra.yaml")
    shutil.copytree(task_dir / "environment" / "universes", app / "universes")
    shutil.copyfile(Path(reference.__file__), app / "analysis.py")

    command = [
        sys.executable,
        "analysis.py",
        "--data",
        "data.csv",
        "--universes",
        "universes",
        "--out",
        "universes.jsonl",
    ]
    run.log("execute", f"running locally: {' '.join(command)} (cwd {app})")
    completed = subprocess.run(command, cwd=app, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"local sweep exited {completed.returncode}")

    check = subprocess.run(
        [sys.executable, str(task_dir / "tests" / "check_universes.py")],
        cwd=app,
        env={**os.environ, "ASTAVERSE_APP_DIR": str(app)},
        capture_output=True,
        text=True,
        check=False,
    )
    print(check.stdout.strip())
    if check.returncode != 0:
        raise RuntimeError("structural check failed:\n" + check.stdout + check.stderr)

    (app / "results.md").write_text(results_markdown(app / "universes.jsonl"))

    record = JobRecord(
        job_name=job_name,
        agent=AGENT,
        model=None,
        command=command,
        returncode=0,
        job_dir=str(job_dir),
    )
    run.write_artifact("execute", ExecuteArtifact(jobs=[record]))
    run.record_stage("execute", agent=AGENT, models=[], n_jobs=1)
    return app / "universes.jsonl"


def load_universes(path: Path) -> pd.DataFrame:
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    frame = pd.DataFrame(rows)
    for decision in DECISION_ORDER:
        frame[decision] = frame["decisions"].map(lambda d, key=decision: d[key])
    return frame


def results_markdown(universes_jsonl: Path) -> str:
    frame = load_universes(universes_jsonl)
    ok = frame[frame["converged"] & frame["estimate"].notna()]
    significant = ok[ok["p_value"] < 0.05]
    lines = [
        "# Simonsohn et al. (2020), Figure 2 — local reference sweep",
        "",
        ("`analysis.py` is a port of the authors' Stata program `(7) Jung et al - Descriptive "
        "Specification Curve.do`. Each universe fits one regression (OLS on log(deaths + 1) or a "
        "negative binomial on deaths, both with robust standard errors) and reports, as `estimate`, "
        "the predicted deaths for a female-named minus a male-named hurricane with every other "
        "regressor at its estimation-sample mean. `p_value` is the robust p-value of the focal "
        "term (femininity × damages, or the femininity main effect)."),
        "",
        "## Spread",
        "",
        f"- {len(ok)} of {len(frame)} universes converged.",
        (f"- Extra deaths range from {ok['estimate'].min():.2f} to {ok['estimate'].max():.2f}; "
        f"median {ok['estimate'].median():.2f}."),
        f"- {int((ok['estimate'] > 0).sum())} estimates are positive, {int((ok['estimate'] < 0).sum())} negative.",
        (f"- {len(significant)} universes have p < 0.05 for the focal term "
        f"({int((significant['estimate'] > 0).sum())} of them positive)."),
        "",
        "## Which decisions move the estimate",
        "",
        "Mean extra deaths by option (spread = max − min across options):",
        "",
    ]
    spreads = []
    for decision in DECISION_ORDER:
        means = ok.groupby(decision)["estimate"].mean().sort_values()
        spreads.append((means.max() - means.min(), decision, means))
    for spread, decision, means in sorted(spreads, reverse=True):
        lines.append(f"- **{decision}** (spread {spread:.2f}): " + ", ".join(f"{k} = {v:.2f}" for k, v in means.items()))
    lines += [
        "",
        "## Notes",
        "",
        ("- Option labels follow the paper's Figure 2 dashboard. The damages thresholds in the "
        "authors' code (`dam < 75260 / 62030 / 52270`) drop Katrina together with Andrew, then "
        "Donna, then Sandy, so 'Drop 1 highest damages' removes two storms with the 2015-dollar data."),
        ("- `estimate_standardized` is null on purpose: extra deaths are already on one comparable "
        "scale for every universe, so the specification curve is read on the raw scale."),
        "",
    ]
    return "\n".join(lines)


# --------------------------------------------------------------------------
# 6. comparison with the authors' results and the figure
# --------------------------------------------------------------------------


def compare_with_stata(ours: pd.DataFrame, theirs: pd.DataFrame, out_path: Path) -> dict:
    theirs = theirs.copy()
    for column, decision in zip(STATA_COLUMNS, DECISION_ORDER):
        theirs[decision] = theirs[column].astype(int).map(STATA_LEVELS[decision])
    merged = ours.merge(theirs, on=DECISION_ORDER, how="inner", suffixes=("", "_stata"))
    ok = merged[merged["converged"] & merged["estimate"].notna()]
    delta = ok["estimate"] - ok["edif"]
    delta_p = ok["p_value"] - ok["p"]
    original = ok[
        (ok["outliers"] == "drop_katrina_audrey")
        & (ok["leverage_points"] == "keep_all")
        & (ok["femininity"] == "masfem_rating")
        & (ok["model"] == "negative_binomial")
        & (ok["damages_form"] == "dollars")
        & (ok["intensity_terms"] == "damages_and_pressure")
        & (ok["year_control"] == "none")
    ].iloc[0]
    summary = {
        "n_universes": len(ours),
        "n_matched_to_stata": len(merged),
        "n_converged": len(ok),
        "sample_sizes_match": bool((ok["n"] == ok["n_stata"]).all()),
        "extra_deaths": {
            "correlation": float(np.corrcoef(ok["estimate"], ok["edif"])[0, 1]),
            "max_abs_difference": float(delta.abs().max()),
            "median_abs_difference": float(delta.abs().median()),
        },
        "p_value": {"max_abs_difference": float(delta_p.abs().max())},
        "n_significant_p05": {"reproduction": int((ok["p_value"] < 0.05).sum()), "stata": int((ok["p"] < 0.05).sum())},
        "n_negative": {"reproduction": int((ok["estimate"] < 0).sum()), "stata": int((ok["edif"] < 0).sum())},
        "median_extra_deaths": {"reproduction": float(ok["estimate"].median()), "stata": float(ok["edif"].median())},
        "range_extra_deaths": {
            "reproduction": [float(ok["estimate"].min()), float(ok["estimate"].max())],
            "stata": [float(ok["edif"].min()), float(ok["edif"].max())],
        },
        "jung_original_specification": {
            "universe_id": str(original["universe_id"]),
            "extra_deaths": {"reproduction": float(original["estimate"]), "stata": float(original["edif"])},
            "p_value": {"reproduction": float(original["p_value"]), "stata": float(original["p"])},
            "n": int(original["n"]),
        },
    }
    out_path.write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def paper_subset(sorted_frame: pd.DataFrame, seed: int = 1976) -> pd.DataFrame:
    """Figure 2 shows the 50 lowest, the 50 highest, ~200 random others and the original."""
    n = len(sorted_frame)
    if n <= 300:
        return sorted_frame
    rank = np.arange(1, n + 1)
    keep = (rank <= 50) | (rank > n - 50) | sorted_frame["is_original"].to_numpy()
    middle = np.flatnonzero(~keep)
    rng = np.random.default_rng(seed)
    keep[rng.choice(middle, size=min(199, len(middle)), replace=False)] = True
    return sorted_frame[keep]


def draw_curve(frame: pd.DataFrame, path: Path, title: str) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    frame = frame.reset_index(drop=True)
    frame["rank"] = np.arange(1, len(frame) + 1)
    ns = frame[frame["p_value"] >= 0.05]
    sig = frame[frame["p_value"] < 0.05]
    original = frame[frame["is_original"]]

    n_rows = sum(len(options) for _, options in FIGURE_LABELS.values())
    fig = plt.figure(figsize=(11, 4.2 + 0.34 * n_rows + 0.4 * len(FIGURE_LABELS)))
    grid = fig.add_gridspec(2, 1, height_ratios=[3.2, 0.34 * n_rows + 0.4 * len(FIGURE_LABELS)], hspace=0.05)

    top = fig.add_subplot(grid[0])
    top.set_facecolor("#eef6ec")
    top.axhline(0, color="#999999", linewidth=0.8)
    top.scatter(ns["rank"], ns["estimate"], s=9, color="#7fb2d8", label="NS", zorder=2)
    top.scatter(sig["rank"], sig["estimate"], s=9, color="black", label="P < 0.05", zorder=3)
    if len(original):
        top.scatter(
            original["rank"], original["estimate"], s=70, marker="o", facecolor="none",
            edgecolor="#c0392b", linewidth=1.6, label="Original specification", zorder=4,
        )
    top.set_ylabel("Extra deaths", fontweight="bold")
    top.set_title(title, loc="left", fontsize=11)
    top.legend(loc="upper left", frameon=False, fontsize=9, ncol=3)
    top.tick_params(axis="x", labelbottom=False)
    top.set_xlim(0, len(frame) + 1)

    bottom = fig.add_subplot(grid[1], sharex=top)
    y = 0
    ticks, labels = [], []
    for decision in reversed(DECISION_ORDER):
        header, options = FIGURE_LABELS[decision]
        for option in reversed(list(options)):
            rows = frame[frame[decision] == option]
            bottom.vlines(rows["rank"], y - 0.32, y + 0.32, color="#333333", linewidth=0.6)
            ticks.append(y)
            labels.append(options[option])
            y += 1
        ticks.append(y)
        labels.append(header)
        y += 1.2
    bottom.set_yticks(ticks)
    bottom.set_yticklabels(labels, fontsize=7.5)
    for label in bottom.get_yticklabels():
        if label.get_text() in {h for h, _ in FIGURE_LABELS.values()}:
            label.set_fontweight("bold")
    bottom.set_ylim(-0.8, y)
    bottom.set_xlabel("Specification (n)", fontweight="bold")
    xt = [1] + [t for t in (50, 250, 500, 1000, 1500) if t < len(frame)] + [len(frame)]
    bottom.set_xticks(sorted(set(xt)))
    for spine in ("top", "right"):
        top.spines[spine].set_visible(False)
        bottom.spines[spine].set_visible(False)
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def draw_validation(ours: pd.DataFrame, theirs: pd.DataFrame, path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    theirs = theirs.copy()
    for column, decision in zip(STATA_COLUMNS, DECISION_ORDER):
        theirs[decision] = theirs[column].astype(int).map(STATA_LEVELS[decision])
    merged = ours.merge(theirs, on=DECISION_ORDER, how="inner")
    fig, axes = plt.subplots(1, 2, figsize=(9, 4))
    for axis, (x, y, label) in zip(
        axes,
        (("edif", "estimate", "Extra deaths"), ("p", "p_value", "p-value of focal term")),
    ):
        axis.scatter(merged[x], merged[y], s=6, color="#2c3e50", alpha=0.6)
        lo, hi = merged[x].min(), merged[x].max()
        axis.plot([lo, hi], [lo, hi], color="#c0392b", linewidth=0.8)
        axis.set_xlabel(f"{label} — Simonsohn et al. (Stata)")
        axis.set_ylabel(f"{label} — this reproduction")
        axis.set_title(f"max |Δ| = {(merged[x] - merged[y]).abs().max():.2g}", fontsize=9)
    fig.suptitle("1,728 specifications: reproduction vs. the authors' results file", fontsize=10)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path(tempfile.gettempdir()) / "astaverse-simonsohn-2020",
        help="Where the OSF downloads are kept between runs.",
    )
    parser.add_argument("--dataset-name", default=DATASET_NAME)
    parser.add_argument("--skip-figure", action="store_true")
    args = parser.parse_args()

    runs_dir = Path(os.environ.get("ASTAVERSE_RUNS", Path.cwd() / "runs"))

    dataset = ensure_dataset(args.cache_dir, args.dataset_name)
    run = create_experiment(runs_dir, dataset)
    print(f"experiment {run.run_id}")

    spec = decision_space(HYPOTHESIS, dataset.csv_path, dataset.name)
    write_astra_yaml(spec, run.artifact_path("decisions"))
    run.record_stage(
        "decisions",
        mode="manual",
        models=[],
        critique=False,
        n_decisions=len(spec.decisions),
        n_execution_decisions=len(spec.execution_decisions()),
        source="Simonsohn, Simmons & Nelson (2020), Stata file (7), https://osf.io/9rvps/",
    )
    run.log("decisions", "transcribed from Simonsohn et al. (2020) Stata code -> 7 execution decisions")

    universe_set = s4_universes.run(run, cap=None)
    print(f"universes: {len(universe_set.universes)} (grid {universe_set.n_total_grid})")
    s5_task.run(run)

    universes_jsonl = execute_locally(run)
    verdicts = s7_verdicts.run(run)
    print(f"verdicts: {verdicts.n_reported} results, {len(verdicts.missing_universe_ids)} missing")

    ours = load_universes(universes_jsonl)
    defaults = {decision: spec.decisions[decision].default for decision in DECISION_ORDER}
    ours["is_original"] = ours["decisions"].map(
        lambda d: all(d[k] == v for k, v in defaults.items())
    )
    theirs = fetch_stata_results(args.cache_dir)
    summary = compare_with_stata(ours, theirs, run.root / "simonsohn_comparison.json")
    print(json.dumps(summary, indent=2))

    if not args.skip_figure:
        try:
            import matplotlib  # noqa: F401
        except ImportError:
            print("matplotlib is not installed; skipping the figure "
                  "(run with `uv run --with matplotlib ...`)")
        else:
            ok = ours[ours["converged"] & ours["estimate"].notna()].sort_values("estimate")
            draw_curve(
                paper_subset(ok),
                run.root / "figure2_reproduction.png",
                "Reproduction of Simonsohn et al. (2020) Fig. 2 — 50 lowest, 50 highest and 200 random of 1,728 specifications",
            )
            draw_curve(
                ok,
                run.root / "figure2_reproduction_all.png",
                "Reproduction of Simonsohn et al. (2020) Fig. 2 — all 1,728 specifications",
            )
            draw_validation(ours, theirs, run.root / "figure2_validation.png")
            print(f"figures written to {run.root}")

    print(f"\nopen the experiment at /experiments/{run.run_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
