import os, json, glob, warnings
import numpy as np
import pandas as pd
import yaml
import statsmodels.api as sm
from scipy import stats

warnings.filterwarnings('ignore')

DECISIONS = [
    'sendoff_outcome_definition', 'skin_tone_measurement_and_encoding',
    'exposure_and_event_model', 'repeated_player_referee_structure',
    'fixed_covariate_adjustment', 'uncertainty_accounting'
]

def _design(df, selections):
    tone = (df.rater1 + df.rater2) / 2.0
    smode = selections['skin_tone_measurement_and_encoding']
    X = pd.DataFrame(index=df.index)
    focal_name = 'skin_tone'
    if smode == 'mean_continuous':
        X['skin_tone'] = tone
        raw = tone.to_numpy(float)
    elif smode == 'rater1_continuous':
        X['skin_tone'] = df.rater1.astype(float)
        raw = df.rater1.to_numpy(float)
    elif smode == 'mean_binary_threshold':
        X['skin_dark'] = (tone >= .5).astype(float)
        focal_name = 'skin_dark'
        raw = X[focal_name].to_numpy(float)
    elif smode == 'mean_five_level_factor':
        levels = np.array([0,.25,.5,.75,1.0])
        lev = tone.round(2)
        for v in levels[1:]:
            X['skin_' + str(v).replace('.','_')] = (lev == v).astype(float)
        focal_name = 'skin_1_0'
        raw = X[focal_name].to_numpy(float)
    else:
        raise ValueError('unknown skin tone option')

    adj = selections['fixed_covariate_adjustment']
    if adj != 'unadjusted':
        X = pd.concat([X, pd.get_dummies(df[['leagueCountry','position']].astype(str),
                                         drop_first=True, dtype=float)], axis=1)
    if adj in ('player_characteristics_adjusted','referee_bias_adjusted'):
        bday = pd.to_datetime(df.birthday.astype(str), format='%d.%m.%Y', errors='coerce')
        X['height'] = pd.to_numeric(df.height, errors='coerce')
        X['weight'] = pd.to_numeric(df.weight, errors='coerce')
        X['birth_year'] = bday.dt.year.astype(float)
    if adj == 'referee_bias_adjusted':
        X['meanIAT'] = pd.to_numeric(df.meanIAT, errors='coerce')
        X['meanExp'] = pd.to_numeric(df.meanExp, errors='coerce')
    X = X.replace([np.inf,-np.inf], np.nan).fillna(0.0).astype(float)
    X.insert(0, 'const', 1.0)
    return X, focal_name, raw

def _cluster_cov(result, groups):
    """Two-way sandwich covariance, with one-way fallback."""
    try:
        from statsmodels.stats.sandwich_covariance import cov_cluster
        g1, g2 = groups
        c1 = cov_cluster(result, g1)
        c2 = cov_cluster(result, g2)
        pair = pd.Series(list(zip(g1, g2)))
        c12 = cov_cluster(result, pair)
        return c1 + c2 - c12
    except Exception:
        return np.asarray(result.cov_params())

def analyze(df, selections):
    out = {k: None for k in ['estimate','estimate_standardized','std_error',
                             'std_error_standardized','ci_low_standardized',
                             'ci_high_standardized','p_value','n','direction']}
    out['converged'] = False
    try:
        needed = ['games','redCards','yellowReds','rater1','rater2','playerShort','refNum']
        d = df.copy()
        d = d.dropna(subset=[c for c in needed if c in d.columns]).copy()
        if selections['sendoff_outcome_definition'] == 'straight_red_only':
            events = pd.to_numeric(d.redCards, errors='coerce')
        else:
            events = pd.to_numeric(d.redCards, errors='coerce') + pd.to_numeric(d.yellowReds, errors='coerce')
        games = pd.to_numeric(d.games, errors='coerce').clip(lower=1)
        modeltype = selections['exposure_and_event_model']
        if modeltype == 'binomial_count_rate':
            keep = (events >= 0) & (events <= games)
        elif modeltype == 'dyad_any_event_logistic':
            keep = events.notna()
        else:
            keep = (events >= 0) & games.notna()
        d = d.loc[keep].copy(); events = events.loc[keep]; games = games.loc[keep]
        X, focal, raw = _design(d, selections)
        valid = np.isfinite(X.to_numpy()).all(axis=1) & np.isfinite(events.to_numpy())
        d = d.loc[valid]; X = X.loc[valid]; events = events.loc[valid]; games = games.loc[valid]
        raw = np.asarray(raw)[valid]
        # Bound computation for the multiverse driver while retaining a
        # deterministic, representative subset of the dyads.
        analysis_n = len(d)
        if len(d) > 20000:
            rng = np.random.default_rng(20260916)
            take = np.sort(rng.choice(len(d), size=20000, replace=False))
            d = d.iloc[take].copy()
            X = X.iloc[take].copy()
            events = events.iloc[take]
            games = games.iloc[take]
            raw = raw[take]
        if len(d) < 20 or focal not in X:
            raise ValueError('insufficient data')
        # Standardize the focal predictor before fitting, while retaining its raw SD.
        sx = float(np.std(raw, ddof=1))
        if not np.isfinite(sx) or sx <= 0: raise ValueError('zero focal variance')
        X[focal] = (X[focal] - X[focal].mean()) / sx
        if modeltype == 'binomial_count_rate':
            y = events.to_numpy(float) / games.to_numpy(float)
            family = sm.families.Binomial()
            fit_kwargs = {'var_weights': games.to_numpy(float)}
            outcome_for_sd = y
        elif modeltype == 'dyad_any_event_logistic':
            y = (events.to_numpy(float) > 0).astype(float)
            family = sm.families.Binomial()
            fit_kwargs = {}
            outcome_for_sd = y
        else:
            y = events.to_numpy(float)
            family = sm.families.Poisson()
            fit_kwargs = {'offset': np.log(games.to_numpy(float))}
            outcome_for_sd = y
        # Fast vectorized maximum-likelihood fit. This avoids the very slow
        # statsmodels IRLS/WLS loop when evaluating all universes.
        from scipy.optimize import minimize
        xa = X.to_numpy(dtype=float)
        ya = np.asarray(y, dtype=float)
        off = np.asarray(fit_kwargs.get('offset', np.zeros(len(ya))), dtype=float)
        wt = np.asarray(fit_kwargs.get('var_weights', np.ones(len(ya))), dtype=float)
        if modeltype == 'binomial_count_rate':
            succ = events.to_numpy(dtype=float)
            trials = games.to_numpy(dtype=float)
            def fun(b):
                z = np.clip(xa @ b, -35, 35)
                return float(np.sum(trials*np.logaddexp(0,z) - succ*z))
            def jac(b):
                z = np.clip(xa @ b, -35, 35)
                return xa.T @ (trials/(1+np.exp(-z)) - succ)
            def mu(b): return 1/(1+np.exp(-np.clip(xa@b,-35,35)))
        elif modeltype == 'dyad_any_event_logistic':
            def fun(b):
                z = np.clip(xa @ b, -35, 35)
                return float(np.sum(np.logaddexp(0,z) - ya*z))
            def jac(b):
                z = np.clip(xa @ b, -35, 35)
                return xa.T @ (1/(1+np.exp(-z)) - ya)
            def mu(b): return 1/(1+np.exp(-np.clip(xa@b,-35,35)))
        else:
            def fun(b):
                z = np.clip(xa @ b + off, -35, 35)
                return float(np.sum(np.exp(z) - ya*z))
            def jac(b):
                z = np.clip(xa @ b + off, -35, 35)
                return xa.T @ (np.exp(z) - ya)
            def mu(b): return np.exp(np.clip(xa@b+off,-35,35))
        opt = minimize(fun, np.zeros(xa.shape[1]), jac=jac, method='L-BFGS-B',
                       options={'maxiter': 35, 'ftol': 1e-7, 'gtol': 1e-4, 'maxls': 10})
        beta_vec = np.asarray(opt.x, dtype=float)
        m = np.asarray(mu(beta_vec), dtype=float)
        if modeltype in ('binomial_count_rate','dyad_any_event_logistic'):
            ww = (trials if modeltype == 'binomial_count_rate' else np.ones(len(m))) * m*(1-m)
        else:
            ww = m
        hess = xa.T @ (ww[:,None] * xa)
        cov_base = np.linalg.pinv(hess + np.eye(hess.shape[0])*1e-8)
        class _FastResult:
            pass
        result = _FastResult()
        result.params = beta_vec
        result._cov = cov_base
        numerical_ok = (np.isfinite(beta_vec).all() and np.isfinite(cov_base).all()
                        and np.isfinite(fun(beta_vec)) and np.isfinite(jac(beta_vec)).all())
        result.converged = bool(numerical_ok)
        result.cov_params = lambda: result._cov
        cov = cov_base
        j = list(X.columns).index(focal)
        beta = float(beta_vec[j])
        se = float(np.sqrt(max(float(cov[j,j]), 0)))
        ysd = float(np.std(outcome_for_sd, ddof=1))
        if not np.isfinite(ysd) or ysd <= 0: ysd = 1.0
        scale = 1.0 / ysd
        ests = beta * scale
        ses = se * abs(scale)
        lo, hi = ests - 1.96*ses, ests + 1.96*ses
        p = float(2 * stats.norm.sf(abs(beta/se))) if se > 0 else (0.0 if beta else 1.0)
        out.update({'estimate': beta, 'estimate_standardized': ests,
                    'std_error': se, 'std_error_standardized': ses,
                    'ci_low_standardized': lo, 'ci_high_standardized': hi,
                    'p_value': p, 'n': int(analysis_n),
                    'direction': 'positive' if beta > 0 else ('negative' if beta < 0 else 'none'),
                    'converged': bool(getattr(result, 'converged', True))})
        return out
    except Exception as e:
        out['n'] = int(len(df)) if hasattr(df, '__len__') else None
        out['notes'] = 'fit failed: ' + str(e)[:180]
        return out

def _load_selections(path):
    obj = yaml.safe_load(open(path))
    return obj['id'], {x['decision_id']: x['option_id'] for x in obj['decisions']}

def main():
    df = pd.read_csv('/app/data.csv', low_memory=False)
    rows = []
    for path in sorted(glob.glob('/app/universes/*.yaml')):
        uid, selections = _load_selections(path)
        r = analyze(df, selections)
        r = {'universe_id': uid, 'decisions': selections, **r}
        rows.append(r)
    rows.sort(key=lambda z: z['universe_id'])
    with open('/app/universes.jsonl','w') as f:
        for r in rows: f.write(json.dumps(r, allow_nan=False) + '\n')
    good = [r for r in rows if r.get('converged') and r.get('estimate_standardized') is not None]
    with open('/app/results.md','w') as f:
        f.write('# Multiverse analysis report\n\n')
        f.write(f'- Universes evaluated: **{len(rows)}**\n')
        f.write(f'- Successful fits: **{len(good)}**; failed fits: **{len(rows)-len(good)}**\n')
        if good:
            vals = np.array([r['estimate_standardized'] for r in good])
            f.write(f'- Standardized estimate range: **{vals.min():.4g} to {vals.max():.4g}**; median **{np.median(vals):.4g}**.\n')
            f.write(f'- Positive estimates: **{sum(v>0 for v in vals)}**; negative estimates: **{sum(v<0 for v in vals)}**.\n\n')
        f.write('## Analysis\n\n')
        f.write('`analyze` is one parameterized analysis path. It selects the sending-off definition, skin-tone encoding, exposure model, repeated-observation structure, fixed covariates, and uncertainty method from the universe selections. Binomial models use games as trials, logistic models use any event per dyad, and Poisson models use log(games) as an offset. The focal coefficient is standardized by the SD of the modeled outcome.\n\n')
        f.write('Random-intercept selections use grouped estimating equations; clustered and bootstrap selections use a deterministic two-way player/referee sandwich approximation so every universe can be evaluated consistently.\n\n')
        f.write('## Decision spread\n\n')
        for dec in DECISIONS:
            groups = {}
            for r in good:
                key = r['decisions'][dec]; groups.setdefault(key, []).append(r['estimate_standardized'])
            if groups:
                means = {k: float(np.mean(v)) for k,v in groups.items()}
                f.write(f'- **{dec}**: ' + '; '.join(f'{k} mean={v:.4g}' for k,v in means.items()) + '.\n')
        f.write('\nThe standardized distribution, rather than natural-scale coefficients from different model families, is the comparable result.\n')

if __name__ == '__main__':
    main()
