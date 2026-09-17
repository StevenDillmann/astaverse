import json, math, os, warnings, gc
from pathlib import Path
import numpy as np
import pandas as pd
import yaml
import statsmodels.api as sm
from scipy import sparse
from scipy.optimize import minimize
from scipy.sparse.linalg import spsolve

warnings.filterwarnings('ignore')


def _empty(n=0, note=''):
    return {'estimate': None, 'estimate_standardized': None,
            'std_error': None, 'std_error_standardized': None,
            'ci_low_standardized': None, 'ci_high_standardized': None,
            'p_value': None, 'n': int(n), 'direction': 'none',
            'converged': False, **({'notes': note} if note else {})}


def _design(d, spec, include_games=False):
    mats = [sparse.csr_matrix(np.ones((len(d), 1), dtype=float)),
            sparse.csr_matrix(d[['dark_skin']].to_numpy(float))]
    names = ['const', 'dark_skin']
    def add_cat(col, prefix):
        vals = pd.Categorical(d[col].astype(str))
        codes = vals.codes
        k = len(vals.categories)
        if k > 1:
            rows = np.arange(len(d))[codes > 0]
            cols = codes[codes > 0] - 1
            dat = np.ones(len(rows), dtype=float)
            mats.append(sparse.csr_matrix((dat, (rows, cols)), shape=(len(d), k-1)))
            names.extend([prefix + '_' + str(x) for x in vals.categories[1:]])
    if spec in ('adjusted_player_league_logistic', 'referee_fixed_effect_logistic'):
        add_cat('leagueCountry', 'leagueCountry')
        add_cat('position', 'position')
        
        cont = d[['height','weight']].to_numpy(float)
        cont = (cont - cont.mean(axis=0)) / np.where(cont.std(axis=0) > 0, cont.std(axis=0), 1.0)
        mats.append(sparse.csr_matrix(cont))
        names.extend(['height', 'weight'])
    if spec == 'referee_fixed_effect_logistic':
        add_cat('refNum', 'ref')
    if spec == 'crossed_random_intercepts':
        add_cat('playerShort', 'player')
        add_cat('refNum', 'ref')
    if include_games:
        g = d[['games']].to_numpy(float)
        g = (g - g.mean(axis=0)) / np.where(g.std(axis=0) > 0, g.std(axis=0), 1.0)
        mats.append(sparse.csr_matrix(g))
        names.append('games')
    return sparse.hstack(mats, format='csr'), names

def _logistic_sparse(X, y, weights=None, penalty=None, maxiter=160):
    n, p = X.shape
    y = np.asarray(y, float)
    w = np.ones(n) if weights is None else np.asarray(weights, float)
    pen = np.zeros(p) if penalty is None else np.asarray(penalty, float)
    def fun_grad(b):
        eta = np.asarray(X @ b).ravel()
        eta = np.clip(eta, -35, 35)
        pr = 1/(1+np.exp(-eta))
        val = np.sum(w*(np.logaddexp(0, eta)-y*eta)) + .5*np.sum(pen*b*b)
        gr = np.asarray(X.T @ (w*(pr-y))).ravel() + pen*b
        return val, gr
    b0 = np.zeros(p)
    res = minimize(lambda b: fun_grad(b), b0, jac=True, method='L-BFGS-B',
                   options={'maxiter': maxiter, 'ftol': 1e-10, 'gtol': 1e-5, 'maxls': 50})
    b = res.x
    eta = np.clip(np.asarray(X @ b).ravel(), -35, 35)
    pr = 1/(1+np.exp(-eta))
    ww = w*pr*(1-pr)
    H = (X.T @ X.multiply(ww[:, None])).tocsc() + sparse.diags(pen)
    grad_norm = float(np.max(np.abs(fun_grad(b)[1]))) if np.all(np.isfinite(b)) else np.inf
    ok = bool(np.all(np.isfinite(b)) and np.isfinite(fun_grad(b)[0]) and (res.success or grad_norm < 1e-3))
    return b, pr, H, ok


def _model_fit(d, spec, weights=None, include_games=False):
    X, names = _design(d, spec, include_games)
    penalty = np.zeros(X.shape[1])
    if spec == 'crossed_random_intercepts':
        penalty[2:] = 1.0
    maxiter = 100 if spec == 'crossed_random_intercepts' else 120
    return (*_logistic_sparse(X, d.outcome, weights, penalty, maxiter), X, names)

def _model_based_se(H, focal):
    try:
        v = spsolve(H, H[:, focal].toarray().ravel())
        z = float(v[focal])
        return math.sqrt(max(z, 0.0))
    except Exception:
        return float('nan')


def _cluster_se(X, y, pr, H, focal, clusters1, clusters2, weights=None):
    try:
        n = len(y); w = np.ones(n) if weights is None else np.asarray(weights, float)
        v = spsolve(H, H[:, focal].toarray().ravel())
        xv = np.asarray(X @ v).ravel()
        score = w*(np.asarray(y,float)-pr)*xv
        a = pd.Series(score).groupby(np.asarray(clusters1)).sum()
        b = pd.Series(score).groupby(np.asarray(clusters2)).sum()
        pairs = pd.Series(score).groupby(pd.MultiIndex.from_arrays([np.asarray(clusters1),np.asarray(clusters2)])).sum()
        meat = float(np.sum(a*a)+np.sum(b*b)-np.sum(pairs*pairs))
        return math.sqrt(max(meat, 0.0))
    except Exception:
        return float('nan')


def analyze(df, selections: dict[str, str]) -> dict:
    try:
        d = df.copy()
        outopt = selections['sending_off_outcome']
        d['outcome'] = ((d.redCards > 0) | ((d.yellowReds > 0) if outopt == 'include_second_yellows' else False)).astype(int)
        comb = selections['skin_tone_combination']
        if comb == 'mean_raters': d['skin_score'] = (d.rater1+d.rater2)/2
        elif comb == 'rater1_only': d['skin_score'] = d.rater1
        elif comb == 'rater2_only': d['skin_score'] = d.rater2
        else:
            d = d.loc[d.rater1 == d.rater2].copy(); d['skin_score'] = d.rater1
        th = selections['skin_tone_threshold']
        if th == 'dark_at_least_half': d['dark_skin'] = (d.skin_score >= .5).astype(int)
        elif th == 'dark_above_half': d['dark_skin'] = (d.skin_score > .5).astype(int)
        else: d['dark_skin'] = (d.skin_score >= .75).astype(int)
        d = d.replace([np.inf, -np.inf], np.nan).dropna(subset=['outcome','dark_skin','height','weight','games'])
        n = len(d)
        if n < 20 or d.dark_skin.nunique() < 2 or d.outcome.nunique() < 2: return _empty(n, 'insufficient variation')
        sd = float(d.dark_skin.std(ddof=1))
        if not np.isfinite(sd) or sd <= 0: return _empty(n, 'zero exposure variance')
        gameopt = selections['games_exposure_handling']
        weights = d.games.to_numpy(float) if gameopt == 'games_frequency_weights' else None
        spec = selections['logistic_model_specification']
        include_games = (gameopt == 'games_as_predictor')
        b, pr, H, ok, X, names = _model_fit(d, spec, weights, include_games)
        focal = names.index('dark_skin')
        beta = float(b[focal])
        if not ok or not np.isfinite(beta): return _empty(n, 'optimizer did not converge')
        unc = selections['uncertainty_estimation']
        se = _model_based_se(H, focal)
        if unc == 'two_way_cluster_robust': se = _cluster_se(X, d.outcome, pr, H, focal, d.playerShort, d.refNum, weights)
        elif unc == 'cluster_bootstrap':
            # Two-way cluster bootstrap approximation using multiplicative player/referee weights.
            rng = np.random.default_rng(202503)
            vals = []
            players = d.playerShort.unique(); refs = d.refNum.unique()
            for _ in range(4):
                wp = pd.Series(rng.multinomial(len(players), np.ones(len(players))/len(players)), index=players)
                wr = pd.Series(rng.multinomial(len(refs), np.ones(len(refs))/len(refs)), index=refs)
                bw = wp.reindex(d.playerShort).to_numpy()*wr.reindex(d.refNum).to_numpy()
                try:
                    bb, _, _, good, _, nn = _model_fit(d, spec, (np.ones(len(d)) if weights is None else weights)*bw, include_games)
                    if good: vals.append(float(bb[nn.index('dark_skin')]))
                    del bb
                except Exception: pass
            if len(vals) >= 3: se = float(np.std(vals, ddof=1))
            else: return _empty(n, 'insufficient successful bootstrap replicates')
            gc.collect()
        if not np.isfinite(se): return _empty(n, 'variance estimation failed')
        eststd = beta*sd; sestd = abs(sd)*se
        lo = eststd - 1.96*sestd; hi = eststd + 1.96*sestd
        z = beta/se if se > 0 else 0.0
        p = float(2*0.5*math.erfc(abs(z)/math.sqrt(2))) if se > 0 else 0.0
        direction = 'positive' if beta > 0 else ('negative' if beta < 0 else 'none')
        return {'estimate': beta, 'estimate_standardized': eststd, 'std_error': se,
                'std_error_standardized': sestd, 'ci_low_standardized': lo,
                'ci_high_standardized': hi, 'p_value': p, 'n': n,
                'direction': direction, 'converged': True}
    except Exception as e:
        return _empty(len(df), type(e).__name__ + ': ' + str(e)[:180])


def main():
    df = pd.read_csv('/app/data.csv')
    files = sorted(Path('/app/universes').glob('*.yaml'))
    rows=[]
    with open('/app/universes.jsonl','w') as f:
        for path in files:
            u = yaml.safe_load(path.read_text())
            selections = {x['decision_id']: x['option_id'] for x in u['decisions']}
            result = analyze(df, selections)
            row = {'universe_id': u['id'], 'decisions': selections, **result}
            f.write(json.dumps(row, allow_nan=False) + '\n'); rows.append(row)
    good=[r for r in rows if r.get('converged')]
    lines=['# Multiverse analysis report','',f'Analyzed {len(rows)} universes; {len(good)} converged.']
    lines += ['', '## Analysis', 'The parameterized `analyze` function constructs the selected sending-off outcome, combines raters and applies the selected threshold, then fits the selected logistic specification. The focal dark-skin coefficient is reported on the log-odds scale. `estimate_standardized` and its uncertainty multiply the natural coefficient scale by the sample SD of the binary exposure.']
    lines += ['', 'Second yellows are either included with straight reds or excluded. Rater scores are averaged, taken singly, or restricted to exact agreement. Games are ignored, used as frequency weights, or included as a covariate. Models are crude, adjusted for league/position/height/weight where applicable, referee fixed-effect, or penalized crossed player/referee intercept models. Uncertainty is model-based, two-way clustered, or bootstrap as selected.']
    if good:
        vals=np.array([r['estimate_standardized'] for r in good]); lines += ['', '## Spread', f'Standardized estimates ranged from {vals.min():.4g} to {vals.max():.4g}; median {np.median(vals):.4g}.']
        for dec in ['sending_off_outcome','skin_tone_combination','skin_tone_threshold','games_exposure_handling','logistic_model_specification','uncertainty_estimation']:
            groups={}
            for r in good: groups.setdefault(r['decisions'][dec],[]).append(r['estimate_standardized'])
            lines.append(f'### {dec}')
            for k,v in sorted(groups.items()): lines.append(f'- `{k}`: median {np.median(v):.4g}, range {min(v):.4g} to {max(v):.4g}')
    Path('/app/results.md').write_text('\n'.join(lines)+'\n')

if __name__ == '__main__': main()
