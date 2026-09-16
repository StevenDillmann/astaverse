#!/usr/bin/env python3
"""Reference multiverse for Figure 2 of Simonsohn, Simmons & Nelson (2020).

"Specification curve analysis", Nature Human Behaviour 4, 1208–1214,
https://doi.org/10.1038/s41562-020-0912-z. Figure 2 re-analyses Jung et al.'s
(2014) hurricane data under 1,728 specifications and plots, for each, the
extra deaths predicted for a female-named versus a male-named hurricane.

This file is a line-by-line port of the authors' Stata program
`(7) Jung et al - Descriptive Specification Curve.do` (OSF: https://osf.io/9rvps/),
in the parametric `analyze(df, selections)` shape the Harbor task requires, so
it doubles as the oracle solution for the emitted task. The seven execution
decisions are the seven nested loops of that program:

    k1 outliers          keep all / deaths < 1833 / deaths < 416
    k2 leverage_points   keep all / damages < 75,260 / < 62,030 / < 52,270 ($M, 2015)
    k3 femininity        female dummy / MTurk femininity rating (1–11)
    k4 model             OLS on log(deaths + 1) / negative binomial on deaths
    k5 damages_form      damages in $ / log($)
    k6 intensity_terms   femininity × damages, optionally × one intensity measure, or main effects only
    k7 year_control      none / year × damages / post-1979 × damages

The reported `estimate` is Simonsohn's `edif`: predicted deaths for a female
name minus predicted deaths for a male name, with every other regressor held at
its estimation-sample mean (Stata `margins, atmeans`). For the OLS models the
log-scale predictions are exponentiated and rescaled by a smearing factor
(`reg d exp(lnd_hat)-1, noconstant`), exactly as the Stata code does. That
quantity is already in deaths for every universe, so no standardisation is
applied and `estimate_standardized` is null; the curve is read on the raw scale.

`p_value` is the robust p-value of the first regressor in the model — the
femininity × damages interaction, or the femininity main effect when there is
no interaction — which is what colours the points in Figure 2. `std_error` is
a delta-method standard error for the extra-deaths estimate.

Usage:
    python scripts/simonsohn_fig2_reference.py --data <data.csv> \
        --universes <dir of universe_*.yaml> --out universes.jsonl
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
import yaml
from scipy import stats as sps

# --------------------------------------------------------------------------
# decision space (ids shared with scripts/reproduce_simonsohn_fig2.py)
# --------------------------------------------------------------------------

DEATH_CAP: dict[str, float] = {
    "keep_all": math.inf,
    "drop_katrina": 1833,  # Stata: d < 1833 drops Katrina only
    "drop_katrina_audrey": 416,  # Stata: d < 416 drops Katrina and Audrey (Jung et al.)
}
DAMAGE_CAP: dict[str, float] = {
    "keep_all": math.inf,
    "below_75260": 75260,  # drops Katrina (88,420) and Andrew (75,260)
    "below_62030": 62030,  # also drops Donna (62,030)
    "below_52270": 52270,  # also drops Sandy (52,270)
}
FEMININITY: dict[str, str] = {"female_binary": "female", "masfem_rating": "masfem"}
MODEL: tuple[str, str] = ("ols_log_deaths", "negative_binomial")
DAMAGE_FORM: dict[str, str] = {"dollars": "dam", "log_dollars": "lndam"}
INTENSITY: dict[str, str | None] = {
    "damages_only": None,
    "damages_and_pressure": "zmin",
    "damages_and_wind": "zwin",
    "damages_and_category": "zcat",
    "damages_and_mean_intensity": "z3",
    "main_effects_only": "main",
}
YEAR_CONTROL: dict[str, str | None] = {
    "none": None,
    "year_x_damages": "year",
    "post79_x_damages": "post79",
}

# `margins, atmeans at(masfem=2.53)` and `at(masfem=8.29)`: the mean MTurk
# femininity rating of male-named and female-named storms, as hard-coded in the
# Stata program (sample values are 2.5302 and 8.2852).
MASFEM_MALE = 2.53
MASFEM_FEMALE = 8.29


# --------------------------------------------------------------------------
# one universe
# --------------------------------------------------------------------------


def design(frame: pd.DataFrame, selections: dict[str, str]) -> pd.DataFrame:
    """The regressor matrix for one specification, focal term first.

    Mirrors the Stata `xb` and `cov` macros: `c.dam#c.fem dam fem`, then
    optionally `c.<z>#c.fem <z>`, then `c.year##c.dam` or `c.post79##c.dam`
    (whose `dam` main effect is already present, so Stata omits it).
    """
    fem = frame[FEMININITY[selections["femininity"]]].astype(float)
    dam = frame[DAMAGE_FORM[selections["damages_form"]]].astype(float)
    intensity = INTENSITY[selections["intensity_terms"]]

    columns: dict[str, pd.Series] = {}
    if intensity == "main":
        columns["fem"] = fem
        columns["dam"] = dam
        columns["z3"] = frame["z3"].astype(float)
    else:
        columns["dam_x_fem"] = dam * fem
        columns["dam"] = dam
        columns["fem"] = fem
        if intensity is not None:
            columns[f"{intensity}_x_fem"] = frame[intensity].astype(float) * fem
            columns[intensity] = frame[intensity].astype(float)

    year = YEAR_CONTROL[selections["year_control"]]
    if year is not None:
        columns[year] = frame[year].astype(float)
        columns[f"{year}_x_dam"] = frame[year].astype(float) * dam

    matrix = pd.DataFrame(columns, index=frame.index)
    matrix["const"] = 1.0
    return matrix


def _profile_start(y: pd.Series, Xs: pd.DataFrame) -> np.ndarray:
    """Start values for the NB2 fit: IRLS coefficients at the profile-likelihood alpha."""
    from scipy.optimize import minimize_scalar

    def negative_loglike(log_alpha: float) -> float:
        family = sm.families.NegativeBinomial(alpha=math.exp(log_alpha))
        try:
            return -sm.GLM(y, Xs, family=family).fit().llf
        except Exception:  # noqa: BLE001  (IRLS can overflow at extreme alpha)
            return math.inf

    # Coarse grid first, so a region where IRLS fails cannot derail the search,
    # then a bounded refinement around the best grid point.
    grid = np.arange(-4.0, 4.01, 0.25)
    values = np.array([negative_loglike(g) for g in grid])
    if not np.isfinite(values).any():
        raise RuntimeError("profile likelihood is infeasible everywhere")
    centre = grid[int(np.nanargmin(np.where(np.isfinite(values), values, np.inf)))]
    best = minimize_scalar(
        negative_loglike, bounds=(centre - 0.25, centre + 0.25), method="bounded"
    )
    log_alpha = best.x if math.isfinite(best.fun) else centre
    alpha = math.exp(log_alpha)
    coefficients = sm.GLM(y, Xs, family=sm.families.NegativeBinomial(alpha=alpha)).fit().params
    return np.append(coefficients.to_numpy(), alpha)


def _fit(y: pd.Series, X: pd.DataFrame, model: str) -> tuple[pd.Series, np.ndarray, float, bool, str | None]:
    """Fit one model with Stata-style robust inference.

    Returns (coefficients, robust covariance of the mean parameters, p-value of
    the first regressor, converged, note). Columns are rescaled to unit SD for
    the optimiser and mapped back: that is a linear reparameterisation, so
    predictions, t-statistics and marginal effects are unchanged.
    """
    scale = X.std(ddof=0).replace(0.0, 1.0)
    scale["const"] = 1.0
    Xs = X / scale
    back = np.diag(1.0 / scale.to_numpy())
    k = X.shape[1]
    n = len(y)

    if model == "ols_log_deaths":
        # `reg lnd ..., robust` = HC1 with t(n - k) reference distribution.
        res = sm.OLS(y, Xs).fit(cov_type="HC1", use_t=True)
        params = res.params / scale
        cov = back @ res.cov_params().to_numpy() @ back
        return params, cov, float(res.pvalues.iloc[0]), True, None

    # `nbreg d ..., robust`: NB2 by maximum likelihood, sandwich covariance
    # scaled by N/(N-1) (Stata's vce(robust) for ML estimators), z reference.
    nb = sm.NegativeBinomial(y, Xs, loglike_method="nb2")
    try:
        start = np.append(sm.Poisson(y, Xs).fit(disp=0, maxiter=300).params.to_numpy(), 1.0)
    except Exception:  # noqa: BLE001
        start = None
    res = None
    note = None
    attempts = [("newton", 300, start), ("bfgs", 3000, start), ("nm", 30000, start)]
    # Ill-conditioned cells (a 1,833-death storm plus interaction terms) can
    # defeat the joint optimiser from a Poisson start. Profiling alpha with the
    # much more stable IRLS fit gives a start next to the maximum, from which
    # Newton converges to the same joint MLE Stata reports.
    try:
        profiled = _profile_start(y, Xs)
    except Exception as exc:  # noqa: BLE001
        note = f"profile start failed: {exc}"
    else:
        attempts.append(("newton", 300, profiled))
        attempts.append(("bfgs", 5000, profiled))
        attempts.append(("lbfgs", 5000, profiled))
    for method, maxiter, start_params in attempts:
        try:
            candidate = nb.fit(
                start_params=start_params, method=method, maxiter=maxiter, disp=0, cov_type="HC0"
            )
        except Exception as exc:  # noqa: BLE001
            note = f"{method}: {exc}"
            continue
        if candidate.mle_retvals.get("converged") and np.isfinite(candidate.params).all():
            res = candidate
            if method != "newton" or start_params is not start:
                note = f"negative binomial converged with {method} from a profiled start"
            break
    if res is None:
        raise RuntimeError(f"negative binomial did not converge ({note})")

    cov_full = res.cov_params().to_numpy() * n / (n - 1)
    params = res.params.iloc[:k] / scale
    cov = back @ cov_full[:k, :k] @ back
    z = params.iloc[0] / math.sqrt(cov[0, 0])
    return params, cov, float(2 * sps.norm.sf(abs(z))), True, note


def analyze(df: pd.DataFrame, selections: dict[str, str]) -> dict:
    """Run the analysis for ONE universe.

    Every analytic choice is driven by `selections`; nothing branches on the
    universe id. This is the structure the Harbor task requires of the agent.
    """
    model = selections["model"]
    if model not in MODEL:
        raise ValueError(f"unknown model option {model!r}")

    # -- sample: Stata `if d<d_max & dam<dam_max` (dollars, whatever k5 says) --
    frame = df[
        (df["alldeaths"] < DEATH_CAP[selections["outliers"]])
        & (df["dam"] < DAMAGE_CAP[selections["leverage_points"]])
    ]
    X = design(frame, selections)
    keep = X.notna().all(axis=1) & frame["alldeaths"].notna()
    frame, X = frame[keep], X[keep]
    deaths = frame["alldeaths"].astype(float)
    y = np.log1p(deaths) if model == "ols_log_deaths" else deaths
    n = len(frame)
    focal_term = X.columns[0]

    try:
        params, cov, p_value, converged, note = _fit(y, X, model)

        # -- predictions at sample means, female vs male name ----------------
        # Stata's `margins, atmeans` fixes every underlying variable at its
        # estimation-sample mean and rebuilds interaction terms from those
        # values, so the at-rows go through the same `design()`.
        means = frame.mean(numeric_only=True).to_frame().T
        fem_column = FEMININITY[selections["femininity"]]
        at_values = (
            (0.0, 1.0) if selections["femininity"] == "female_binary" else (MASFEM_MALE, MASFEM_FEMALE)
        )
        rows = []
        for value in at_values:
            at = means.copy()
            at[fem_column] = value
            rows.append(design(at, selections).to_numpy()[0])
        x_male, x_female = rows
        beta = params.to_numpy()
        xb_male, xb_female = float(x_male @ beta), float(x_female @ beta)

        if model == "ols_log_deaths":
            # Smearing-type retransformation: `reg d exp(lnd_hat)-1, noconstant`.
            fitted = X.to_numpy() @ beta
            e_hat = np.exp(fitted) - 1.0
            adjust = float((deaths.to_numpy() @ e_hat) / (e_hat @ e_hat))
            predicted_male = math.exp(xb_male) * adjust
            predicted_female = math.exp(xb_female) * adjust
            gradient = adjust * (math.exp(xb_female) * x_female - math.exp(xb_male) * x_male)
        else:
            adjust = None
            predicted_male = math.exp(xb_male)
            predicted_female = math.exp(xb_female)
            gradient = predicted_female * x_female - predicted_male * x_male

        estimate = predicted_female - predicted_male
        std_error = float(math.sqrt(max(gradient @ cov @ gradient, 0.0)))
    except Exception as exc:  # noqa: BLE001
        return {
            "estimate": None,
            "estimate_standardized": None,
            "std_error": None,
            "std_error_standardized": None,
            "ci_low_standardized": None,
            "ci_high_standardized": None,
            "p_value": None,
            "n": n,
            "direction": None,
            "converged": False,
            "notes": f"fit failed: {exc}",
        }

    if not (math.isfinite(estimate) and math.isfinite(p_value)):
        converged = False
    direction = None
    if converged:
        direction = "positive" if estimate > 0 else "negative" if estimate < 0 else "none"

    notes = (
        f"estimate = extra deaths (female - male name) at sample means; "
        f"p_value is for the focal term `{focal_term}` (robust)"
    )
    if note:
        notes += f"; {note}"

    return {
        "estimate": float(estimate),
        # Extra deaths is already comparable across every universe (OLS and
        # negative binomial alike), so no standardisation is applied.
        "estimate_standardized": None,
        "std_error": std_error,
        "std_error_standardized": None,
        "ci_low_standardized": None,
        "ci_high_standardized": None,
        "p_value": float(p_value),
        "n": n,
        "direction": direction,
        "converged": bool(converged),
        "notes": notes,
        # Provenance for comparing against Simonsohn's `specifications_hurricanes.dta`
        # (columns b, em, ef, edif).
        "focal_term": str(focal_term),
        "focal_coefficient": float(params.iloc[0]),
        "predicted_deaths_male": float(predicted_male),
        "predicted_deaths_female": float(predicted_female),
        "log_retransformation_factor": adjust,
    }


# --------------------------------------------------------------------------
# driver
# --------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
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
    for index, path in enumerate(universe_files, 1):
        doc = yaml.safe_load(path.read_text())
        selections = {d["decision_id"]: d["option_id"] for d in doc["decisions"]}
        rows.append({"universe_id": doc["id"], "decisions": selections, **analyze(df, selections)})
        if index % 200 == 0:
            print(f"  {index}/{len(universe_files)} universes", file=sys.stderr)

    Path(args.out).write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    failed = sum(1 for r in rows if not r["converged"])
    print(f"wrote {len(rows)} universes to {args.out} ({failed} did not converge)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
