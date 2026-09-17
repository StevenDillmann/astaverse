import json, glob, os, warnings
import numpy as np
import pandas as pd
import yaml
from scipy.special import expit
from scipy.stats import norm
import statsmodels.api as sm

warnings.filterwarnings('ignore')


def _bool(s):
    return s.fillna(False).astype(bool)


def _se_diff(y, black, groups=None):
    """Difference in rates (Black minus comparison), with optional clustering."""
    b = black.to_numpy(dtype=bool)
    yy = y.to_numpy(dtype=float)
    nb, nw = b.sum(), (~b).sum()
    if nb == 0 or nw == 0:
        return np.nan
    pb, pw = yy[b].mean(), yy[~b].mean()
    infl = np.zeros(len(yy), dtype=float)
    infl[b] = (yy[b] - pb) / nb
    infl[~b] = -(yy[~b] - pw) / nw
    if groups is None:
        return float(np.sqrt(np.sum(infl * infl)))
    g = pd.Series(groups).fillna('__MISSING__').astype(str).to_numpy()
    sums = pd.Series(infl).groupby(g, sort=False).sum().to_numpy()
    return float(np.sqrt(np.sum(sums * sums)))


def _result_null(n=0):
    return {'estimate': None, 'estimate_standardized': None,
            'std_error': None, 'std_error_standardized': None,
            'ci_low_standardized': None, 'ci_high_standardized': None,
            'p_value': None, 'n': int(n), 'direction': 'none',
            'converged': False}


def analyze(df, selections: dict[str, str]) -> dict:
    """Run the analysis for ONE universe."""
    try:
        d = df.copy()
        raceopt = selections['race_analytic_sample']
        if raceopt == 'black_white_only':
            d = d[d['subject_race'].isin(['black', 'white'])].copy()
            d['_black'] = (d['subject_race'] == 'black')
        elif raceopt == 'use_raw_race_mapping':
            # Stanford source race codes: B is Black and W is White.
            d = d[d['raw_Race'].isin(['B', 'W'])].copy()
            d['_black'] = (d['raw_Race'] == 'B')
        elif raceopt == 'include_unknown_as_nonwhite':
            d['_black'] = (d['subject_race'] == 'black')
        else:
            return _result_null()
        if len(d) == 0:
            return _result_null()

        sopt = selections['searched_stop_definition']
        sc = _bool(d['search_conducted'])
        sp = _bool(d['search_person'])
        sv = _bool(d['search_vehicle'])
        fr = _bool(d['frisk_performed'])
        if sopt == 'search_conducted':
            keep = sc
        elif sopt == 'person_or_vehicle_search':
            keep = sp | sv
        elif sopt == 'any_search_related_action':
            keep = sc | sp | sv | fr
        else:
            return _result_null()
        d = d[keep].copy()
        if len(d) == 0:
            return _result_null()

        hopt = selections['contraband_hit_coding']
        cf = d['contraband_found']
        cd = d['contraband_drugs']
        cw = d['contraband_weapons']
        if hopt == 'direct_contraband_complete_case':
            ok = cf.notna()
            d = d[ok].copy()
            d['_hit'] = (d['contraband_found'] == True).astype(float)
        elif hopt == 'direct_contraband_missing_nonhit':
            d['_hit'] = (d['contraband_found'] == True).astype(float)
        elif hopt == 'drug_or_weapon_union':
            ok = ~(cd.isna() & cw.isna())
            d = d[ok].copy()
            d['_hit'] = ((_bool(d['contraband_drugs'])) | _bool(d['contraband_weapons'])).astype(float)
        else:
            return _result_null(len(d))

        date = pd.to_datetime(d['date'], errors='coerce')
        dateopt = selections['date_scope']
        if dateopt == 'stated_2002_2015_window':
            d = d[(date >= '2002-01-01') & (date <= '2015-12-31')].copy()
            date = date.loc[d.index]
        elif dateopt == 'complete_date_only':
            d = d[date.notna()].copy()
            date = date.loc[d.index]
        elif dateopt != 'all_supplied_rows':
            return _result_null(len(d))
        if len(d) == 0 or d['_black'].nunique() < 2 or d['_hit'].nunique() < 2 and selections['race_comparison_model'] != 'unadjusted_rate_comparison':
            return _result_null(len(d))

        modelopt = selections['race_comparison_model']
        dep = selections['dependence_and_uncertainty']
        groups = None
        if dep == 'cluster_officer': groups = d['officer_id_hash']
        elif dep == 'cluster_department': groups = d['department_name']
        elif dep != 'independent_stops': return _result_null(len(d))

        if modelopt == 'unadjusted_rate_comparison':
            b = d['_black'].astype(bool)
            if b.sum() == 0 or (~b).sum() == 0:
                return _result_null(len(d))
            est = float(d.loc[b, '_hit'].mean() - d.loc[~b, '_hit'].mean())
            se = _se_diff(d['_hit'], b, groups)
            if not np.isfinite(se): return _result_null(len(d))
            # Standardize the binary focal predictor; binary outcome is standardized too.
            xs = float(np.sqrt(b.mean() * (1 - b.mean())))
            ys = float(np.sqrt(d['_hit'].mean() * (1 - d['_hit'].mean())))
            scale = xs / ys if ys > 0 else xs
            es, ses = est * scale, abs(scale) * se
            converged = True
        elif modelopt in ('race_only_logistic', 'adjusted_logistic'):
            x = pd.DataFrame({'black': d['_black'].astype(float).to_numpy()}, index=d.index)
            if modelopt == 'adjusted_logistic':
                x['subject_age'] = pd.to_numeric(d['subject_age'], errors='coerce')
                x['calendar_year'] = date.dt.year
                for col in ['subject_sex', 'reason_for_stop', 'department_name']:
                    z = d[col].astype('string').fillna('__MISSING__')
                    dum = pd.get_dummies(z, prefix=col, drop_first=True, dtype=float)
                    x = pd.concat([x, dum], axis=1)
            dat = pd.concat([d[['_hit']], x], axis=1).replace([np.inf, -np.inf], np.nan).dropna()
            if len(dat) < 10 or dat['black'].nunique() < 2 or dat['_hit'].nunique() < 2:
                return _result_null(len(dat))
            X = sm.add_constant(dat.drop(columns=['_hit']), has_constant='add').astype(float)
            y = dat['_hit'].astype(float)
            kwargs = {}
            if dep != 'independent_stops':
                g = d.loc[dat.index, 'officer_id_hash' if dep == 'cluster_officer' else 'department_name'].fillna('__MISSING__')
                kwargs = {'cov_type': 'cluster', 'cov_kwds': {'groups': g}}
            fit = sm.GLM(y, X, family=sm.families.Binomial()).fit(**kwargs)
            if 'black' not in fit.params or not np.isfinite(fit.params['black']):
                return _result_null(len(dat))
            est = float(fit.params['black'])
            se = float(fit.bse['black'])
            xs = float(np.sqrt(dat['black'].mean() * (1 - dat['black'].mean())))
            ys = float(np.sqrt(y.mean() * (1 - y.mean())))
            scale = xs / ys if ys > 0 else xs
            es, ses = est * scale, abs(scale) * se
            converged = bool(fit.converged)
        else:
            return _result_null(len(d))
        if not np.isfinite(es) or not np.isfinite(ses):
            return _result_null(len(d))
        p = float(2 * norm.sf(abs(es / ses))) if ses > 0 else (0.0 if es != 0 else 1.0)
        lo, hi = float(es - 1.96 * ses), float(es + 1.96 * ses)
        direction = 'positive' if est > 0 else ('negative' if est < 0 else 'none')
        return {'estimate': float(est), 'estimate_standardized': float(es),
                'std_error': float(se), 'std_error_standardized': float(ses),
                'ci_low_standardized': lo, 'ci_high_standardized': hi,
                'p_value': p, 'n': int(len(d)), 'direction': direction,
                'converged': converged}
    except Exception:
        return _result_null(len(df))


def _load_selection(path):
    with open(path) as f: u = yaml.safe_load(f)
    return u['id'], {x['decision_id']: x['option_id'] for x in u['decisions']}


def main():
    df = pd.read_csv('/app/data.csv', low_memory=False)
    rows = []
    for path in sorted(glob.glob('/app/universes/*.yaml')):
        uid, selections = _load_selection(path)
        out = analyze(df, selections)
        rows.append({'universe_id': uid, 'decisions': selections, **out})
    with open('/app/universes.jsonl', 'w') as f:
        for row in rows: f.write(json.dumps(row, allow_nan=False) + '\n')
    print(f'wrote {len(rows)} universes')

if __name__ == '__main__': main()
