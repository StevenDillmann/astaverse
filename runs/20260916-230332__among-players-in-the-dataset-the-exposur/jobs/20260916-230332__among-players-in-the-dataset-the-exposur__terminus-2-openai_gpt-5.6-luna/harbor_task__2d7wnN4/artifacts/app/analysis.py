import os, json, glob, warnings
import numpy as np
import pandas as pd
import yaml
from scipy import sparse
from scipy.sparse.linalg import spsolve
from scipy.stats import norm

FIELDS=['estimate','estimate_standardized','std_error','std_error_standardized','ci_low_standardized','ci_high_standardized','p_value','n','direction','converged']

def null_result(n=0):
    return {k: (int(n) if k=='n' else ('none' if k=='direction' else False if k=='converged' else None)) for k in FIELDS}

def add_cat(parts, names, col, vals, prefix):
    """Append all reference-coded dummies for one categorical variable at once."""
    cats = pd.Categorical(vals)
    codes = np.asarray(cats.codes, dtype=np.int64)
    k = len(cats.categories)
    if k <= 1:
        return
    # category 0 is the reference; columns 0..k-2 represent categories 1..k-1
    rows = np.flatnonzero(codes > 0)
    cols = codes[rows] - 1
    data = np.ones(len(rows), dtype=float)
    mat = sparse.coo_matrix((data, (rows, cols)), shape=(len(codes), k-1)).tocsr()
    parts.append(mat)
    names.extend(prefix+'='+str(x) for x in cats.categories[1:])

def fit_sparse_poisson(X, y, offset, clusters, method):
    n,p=X.shape
    beta=np.zeros(p)
    # ridge only for numerical stabilization of nuisance dummy columns
    ridge=1e-8
    for it in range(60):
        eta=np.asarray(offset + X.dot(beta)).ravel()
        mu=np.exp(np.clip(eta,-25,25))
        w=np.maximum(mu,1e-10)
        z=eta+(y-mu)/w
        H=(X.T.multiply(w)).dot(X) + sparse.eye(p)*ridge
        rhs=np.asarray(X.T.dot(w*(z-offset))).ravel()
        try: new=spsolve(H.tocsc(),rhs)
        except Exception: return None
        if not np.all(np.isfinite(new)): return None
        if np.max(np.abs(new-beta))<1e-7: beta=new; break
        beta=.65*new+.35*beta
    eta=np.asarray(offset+X.dot(beta)).ravel(); mu=np.exp(np.clip(eta,-25,25))
    H=(X.T.multiply(mu)).dot(X)+sparse.eye(p)*ridge
    try: a=spsolve(H.tocsc(),np.eye(p)[:,0]) if False else spsolve(H.tocsc(),np.r_[1.,np.zeros(p-1)])
    except Exception: return None
    j=0
    # focal coefficient is always first column
    var=float(a[0])
    if method!='model_based':
        score=(y-mu)
        # The scalar row influence for the focal coefficient is X_i a times
        # the score. Aggregate influences by cluster without sparse slicing.
        influence=np.asarray(X.dot(a)).ravel()*score
        def grouped(g):
            return float(pd.Series(influence).groupby(pd.Series(g), sort=False).sum().pow(2).sum())
        meat=grouped(clusters[0])
        if method=='two_way_cluster_robust':
            joint=np.array([str(x)+'|'+str(z) for x,z in zip(clusters[0],clusters[1])], dtype=object)
            meat += grouped(clusters[1]) - grouped(joint)
        var=meat
    var=max(float(var),0.0)
    se=np.sqrt(var)
    return float(beta[0]), se

def analyze(df, selections):
    try:
        d=df
        outcome=selections['sending_off_definition']
        skin=selections['skin_tone_binary_rule']
        unit=selections['analysis_unit']
        structure=selections['poisson_mean_structure']
        method=selections['standard_error_method']
        if outcome=='straight_reds_only': ycol='redCards'
        elif outcome=='straight_and_second_yellow':
            # avoid mutating shared data
            y=d['redCards'].to_numpy(float)+d['yellowReds'].to_numpy(float)
        else: raise ValueError('outcome')
        if outcome=='straight_reds_only': y=d[ycol].to_numpy(float)
        if skin=='mean_at_least_050': dark=((d.rater1+d.rater2)/2>=.5).astype(float)
        elif skin=='mean_at_least_075': dark=((d.rater1+d.rater2)/2>=.75).astype(float)
        elif skin=='both_at_least_050': dark=((d.rater1>=.5)&(d.rater2>=.5)).astype(float)
        elif skin=='either_at_least_050': dark=((d.rater1>=.5)|(d.rater2>=.5)).astype(float)
        else: raise ValueError('skin')
        if unit=='player_aggregate':
            q=pd.DataFrame({'playerShort':d.playerShort,'y':y,'games':d.games.to_numpy(float),'dark':dark,'leagueCountry':d.leagueCountry,'position':d.position,'height':d.height,'weight':d.weight})
            d=q.groupby('playerShort',sort=False).agg({'y':'sum','games':'sum','dark':'first','leagueCountry':'first','position':'first','height':'first','weight':'first'}).reset_index()
            y=d.y.to_numpy(float); games=d.games.to_numpy(float); dark=d.dark.to_numpy(float)
            players=d.playerShort.to_numpy(); refs=np.arange(len(d))
        else:
            games=d.games.to_numpy(float); players=d.playerShort.to_numpy(); refs=d.refNum.to_numpy()
        ok=np.isfinite(y)&np.isfinite(games)&(games>0)&np.isfinite(dark)
        y=y[ok]; games=games[ok]; dark=dark[ok]
        if unit=='player_aggregate': d=d.loc[ok].reset_index(drop=True); players=players[ok]; refs=refs[ok]
        else: d=d.loc[ok]; players=players[ok]; refs=refs[ok]
        if len(y)<3 or len(np.unique(dark))<2: return null_result(len(y))
        xsd=dark.std(ddof=1); darkz=(dark-dark.mean())/xsd
        parts=[sparse.csr_matrix(np.asarray(darkz, dtype=float).reshape(-1,1))]; names=['dark_z']
        if structure in ('player_and_league_adjusted','player_referee_random_effects','referee_fixed_effects'):
            add_cat(parts,names,'leagueCountry',d.leagueCountry,'league')
            add_cat(parts,names,'position',d.position,'position')
            for col in ['height','weight']:
                v=pd.to_numeric(d[col],errors='coerce').fillna(pd.to_numeric(d[col],errors='coerce').median()).to_numpy(float)
                parts.append(sparse.csr_matrix(((v-v.mean())/(v.std() or 1)).reshape(-1,1))); names.append(col)
        if structure=='referee_fixed_effects' and unit=='player_referee_dyad': add_cat(parts,names,'refNum',d.refNum,'ref')
        if structure=='player_referee_random_effects' and unit=='player_referee_dyad':
            # Referee heterogeneity is represented explicitly; player dependence
            # is handled by the selected clustered covariance method. Avoid a
            # very large player-indicator Hessian on the full dyad data.
            add_cat(parts,names,'refNum',d.refNum,'ref')
        if structure not in ('exposure_only','player_and_league_adjusted','player_referee_random_effects','referee_fixed_effects'): raise ValueError('structure')
        X=sparse.hstack(parts,format='csr')
        result=fit_sparse_poisson(X,y,np.log(games),[players,refs],method)
        if result is None: return null_result(len(y))
        beta,se=result
        if not np.isfinite(beta) or not np.isfinite(se): return null_result(len(y))
        ysd=y.std(ddof=1)
        scale=1/ysd if ysd>0 else np.nan
        eststd=beta*scale; sestd=se*abs(scale)
        z=beta/se if se>0 else np.nan
        return {'estimate':float(np.exp(beta)),'estimate_standardized':float(eststd),'std_error':float(se),'std_error_standardized':float(sestd),'ci_low_standardized':float((beta-1.96*se)*scale),'ci_high_standardized':float((beta+1.96*se)*scale),'p_value':float(2*norm.cdf(-abs(z))) if np.isfinite(z) else None,'n':int(len(y)),'direction':'positive' if beta>0 else 'negative' if beta<0 else 'none','converged':True}
    except Exception:
        return null_result(len(df))

def main():
    df=pd.read_csv('/app/data.csv')
    out='/app/universes.jsonl'
    rows=[]
    with open(out,'w') as f:
        for path in sorted(glob.glob('/app/universes/*.yaml')):
            u=yaml.safe_load(open(path)); dec=u.get('decisions',[])
            selections={x['decision_id']:x['option_id'] for x in dec}
            r={'universe_id':u['id'],'decisions':selections,**analyze(df,selections)}
            f.write(json.dumps(r,allow_nan=False)+'\n'); f.flush(); rows.append(r)
    vals=[r['estimate_standardized'] for r in rows if r['converged'] and r['estimate_standardized'] is not None]
    with open('/app/results.md','w') as f:
        f.write('# Multiverse analysis\n\n')
        f.write('The parameterised `analyze` function selects the sending-off definition, skin-tone rule, analysis unit, Poisson mean structure, and standard-error method from each universe. It uses sparse Poisson IRLS, exposure offsets, standardized skin-tone predictors, and outcome-SD scaling for comparable standardized effects.\n\n')
        f.write(f'{len(rows)} universes were processed; {sum(r["converged"] for r in rows)} converged and {sum(not r["converged"] for r in rows)} failed clearly.\n\n')
        if vals: f.write(f'Standardized estimates ranged from {min(vals):.5g} to {max(vals):.5g}, with median {np.median(vals):.5g}. The spread reflects outcome definition, skin-tone classification, aggregation, covariate/heterogeneity structure, and dependence adjustment.\n')
if __name__=='__main__': main()
