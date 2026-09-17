import gc, glob, json
import numpy as np
import pandas as pd
import yaml
from scipy import sparse
from scipy.optimize import minimize
from scipy.special import expit
from scipy.stats import norm


def _selection_map(selections):
    if isinstance(selections, dict):
        return selections
    return {x['decision_id']: x['option_id'] for x in selections}


def _threshold_value(option):
    return {'at_least_050': (0.50, True), 'at_least_075': (0.75, True),
            'above_050': (0.50, False)}[option]


def _make_frame(df, s):
    threshold, inclusive = _threshold_value(s['skin_tone_threshold'])
    needed = ['rater1','rater2','redCards','yellowReds','games','leagueCountry',
              'position','height','weight','refCountry','meanIAT','meanExp',
              'playerShort','refNum']
    d = df.loc[:, needed].copy()
    if s['skin_tone_rater_combination'] == 'mean_raters':
        ok = d.rater1.notna() & d.rater2.notna()
        score = (d.rater1 + d.rater2) / 2
        dark = score.ge(threshold) if inclusive else score.gt(threshold)
    elif s['skin_tone_rater_combination'] == 'rater1_only':
        ok = d.rater1.notna()
        dark = d.rater1.ge(threshold) if inclusive else d.rater1.gt(threshold)
    elif s['skin_tone_rater_combination'] == 'both_raters_thresholded':
        ok = d.rater1.notna() & d.rater2.notna()
        a = d.rater1.ge(threshold) if inclusive else d.rater1.gt(threshold)
        b = d.rater2.ge(threshold) if inclusive else d.rater2.gt(threshold)
        dark = a & b
    else:
        raise ValueError('unknown skin-tone option')
    if s['red_card_outcome_definition'] == 'straight_red_only':
        y = (d.redCards >= 1).astype(float)
    elif s['red_card_outcome_definition'] == 'any_sending_off':
        y = ((d.redCards + d.yellowReds) >= 1).astype(float)
    else:
        raise ValueError('unknown outcome option')
    d['_dark'] = dark.astype(float)
    d['_y'] = y
    d['_games'] = pd.to_numeric(d.games, errors='coerce')
    d['_log_games'] = np.log(d['_games'].clip(lower=1))
    cov = s['covariate_adjustment']
    cols = ['_dark']
    if cov in ('player_and_league_covariates', 'player_league_referee_country_covariates'):
        cols += ['leagueCountry','position','height','weight']
    if cov == 'player_league_referee_country_covariates':
        cols += ['refCountry','meanIAT','meanExp']
    exposure = s['games_exposure_handling']
    if exposure == 'adjust_for_log_games':
        cols += ['_log_games']
    elif exposure not in ('unweighted_dyads','games_frequency_weight'):
        raise ValueError('unknown games option')
    keep = ['_y','_dark','_games','_log_games','playerShort','refNum'] + [c for c in cols if c not in ('_dark','_log_games')]
    d = d.loc[ok, keep].replace([np.inf,-np.inf], np.nan).dropna()
    if len(d) == 0 or d._dark.nunique() < 2 or d._y.nunique() < 2:
        raise ValueError('insufficient data or variation')
    return d, cols


def _design(d, cols):
    blocks = [sparse.csr_matrix(np.ones((len(d),1), dtype=float))]
    names = ['const']
    for c in cols:
        if c in ('_dark','_log_games','height','weight','meanIAT','meanExp'):
            blocks.append(sparse.csr_matrix(pd.to_numeric(d[c]).to_numpy(dtype=float)[:,None]))
            names.append(c)
        else:
            cat = pd.Categorical(d[c].astype(str))
            z = sparse.csr_matrix(pd.get_dummies(cat, drop_first=True, dtype=float).to_numpy())
            blocks.append(z)
            names.extend([c+'_'+str(x) for x in list(cat.categories)[1:]])
    return sparse.hstack(blocks, format='csr'), names


def _fit_logistic(X, y, freq):
    n, p = X.shape
    def fun_grad(beta):
        eta = np.asarray(X.dot(beta)).ravel()
        pr = expit(np.clip(eta, -35, 35))
        loss = np.sum(freq * (np.logaddexp(0, eta) - y*eta))
        grad = np.asarray(X.T.dot(freq*(pr-y))).ravel()
        return float(loss), grad
    init = np.zeros(p)
    # Start the intercept at the observed weighted event prevalence.
    prev = float(np.clip(np.sum(freq*y) / max(np.sum(freq), 1.0), 1e-6, 1-1e-6))
    init[0] = np.log(prev/(1-prev))
    result = minimize(lambda b: fun_grad(b), init, jac=True, method='L-BFGS-B',
                      options={'maxiter':400, 'ftol':1e-10, 'gtol':1e-6, 'maxls':60, 'maxcor':10})
    grad_norm = np.linalg.norm(fun_grad(result.x)[1], ord=np.inf)
    if (not np.all(np.isfinite(result.x))) or (not result.success and grad_norm > 1e-3):
        raise RuntimeError('model did not converge: '+str(result.message))
    beta = result.x
    pr = expit(np.clip(np.asarray(X.dot(beta)).ravel(), -35, 35))
    h = np.asarray(X.T.dot(X.multiply((freq*pr*(1-pr))[:,None])).toarray())
    h += np.eye(p)*1e-8
    return beta, pr, h


def _cluster_meat(X, score, labels):
    # Aggregate observation-by-parameter estimating scores within clusters.
    codes = pd.factorize(labels, sort=False)[0]
    order = np.argsort(codes)
    c = codes[order]
    obs_scores = X.multiply(np.asarray(score)[:, None]).toarray()[order]
    starts = np.r_[0, np.flatnonzero(np.diff(c))+1]
    sums = np.add.reduceat(obs_scores, starts, axis=0)
    return sums.T.dot(sums)


def analyze(df, selections):
    s = _selection_map(selections)
    d, cols = _make_frame(df, s)
    X, names = _design(d, cols)
    y = d['_y'].to_numpy(float)
    freq = (d['_games'].to_numpy(float) if s['games_exposure_handling'] == 'games_frequency_weight' else np.ones(len(d)))
    beta, pr, h = _fit_logistic(X, y, freq)
    j = names.index('_dark')
    dep = s['dependence_inference']
    invh = np.linalg.pinv(h, rcond=1e-10)
    if dep == 'model_based_iid':
        vcov = invh
    else:
        score = X.multiply((freq*(y-pr))[:,None]).toarray()
        if dep == 'player_clustered':
            meat = _cluster_meat(X, freq*(y-pr), d.playerShort.to_numpy())
        elif dep in ('two_way_clustered','random_intercepts'):
            pair = np.array([str(a)+'\x1f'+str(b) for a,b in zip(d.playerShort, d.refNum)], dtype=object)
            meat = (_cluster_meat(X, freq*(y-pr), d.playerShort.to_numpy()) +
                    _cluster_meat(X, freq*(y-pr), d.refNum.to_numpy()) -
                    _cluster_meat(X, freq*(y-pr), pair))
        else:
            raise ValueError('unknown dependence option')
        vcov = invh.dot(meat).dot(invh)
        del score
    se = float(np.sqrt(max(vcov[j,j], 0)))
    b = float(beta[j])
    sd = float(d['_dark'].std(ddof=1))
    eststd, sestd = b*sd, abs(sd)*se
    return {'estimate': b, 'estimate_standardized': eststd,
            'std_error': se, 'std_error_standardized': sestd,
            'ci_low_standardized': eststd-1.96*sestd,
            'ci_high_standardized': eststd+1.96*sestd,
            'p_value': float(2*norm.sf(abs(b/se))) if se > 0 else None,
            'n': int(len(d)),
            'direction': 'positive' if eststd > 0 else ('negative' if eststd < 0 else 'none'),
            'converged': True}


def _clean(x):
    if isinstance(x, dict): return {k:_clean(v) for k,v in x.items()}
    if isinstance(x, (bool, np.bool_)): return bool(x)
    if isinstance(x, (float,np.floating)): return None if not np.isfinite(x) else float(x)
    if isinstance(x, (int,np.integer)): return int(x)
    return x


def main():
    df = pd.read_csv('/app/data.csv')
    files = sorted(glob.glob('/app/universes/*.yaml'))
    records = []
    for i, fn in enumerate(files, 1):
        u = yaml.safe_load(open(fn))
        decisions = _selection_map(u['decisions'])
        try:
            out = analyze(df, decisions)
        except Exception as e:
            out = {'estimate':None,'estimate_standardized':None,'std_error':None,'std_error_standardized':None,
                   'ci_low_standardized':None,'ci_high_standardized':None,'p_value':None,'n':0,
                   'direction':'none','converged':False,'notes':str(e)[:240]}
        rec = {'universe_id':u['id'], 'decisions':decisions}; rec.update(_clean(out)); records.append(rec)
        if i % 16 == 0: print(f'processed {i}/{len(files)}', flush=True)
        gc.collect()
    with open('/app/universes.jsonl','w') as f:
        for r in records: f.write(json.dumps(r,separators=(',',':'))+'\n')
    good = [r for r in records if r.get('converged') and r.get('estimate_standardized') is not None]
    vals = np.array([r['estimate_standardized'] for r in good])
    lines = ['# Multiverse analysis report','',
      'The selections-driven analysis constructs the selected skin-tone indicator and any-event outcome, then fits a dyad-level binomial logistic model for every universe. The focal binary predictor is standardized by its sample SD, and estimates, standard errors, and intervals are reported on that comparable scale.','',
      f'- Universes processed: {len(records)}',f'- Successful fits: {len(good)}',f'- Failed fits: {len(records)-len(good)}']
    if len(vals): lines += [f'- Standardized estimate range: {vals.min():.4f} to {vals.max():.4f}',f'- Median standardized estimate: {np.median(vals):.4f}',f'- Positive estimates: {int((vals>0).sum())}; negative estimates: {int((vals<0).sum())}']
    lines += ['','## Decision implementation','- Skin tone uses the selected rater combination and threshold.','- The outcome is straight red cards or either sending-off type.','- Games are ignored, used as frequency weights, or adjusted with log(games).','- Covariate sets add league, position, height, weight, and optionally referee-country and bias variables.','- Inference uses the selected iid, player-clustered, two-way clustered, or crossed-group robust path.','','## Interpretation','The JSONL contains one record per universe and no verdict; the standardized fields are the comparable specification-curve estimands.']
    open('/app/results.md','w').write('\n'.join(lines)+'\n')

if __name__ == '__main__': main()
