import json, glob, math
import numpy as np
import pandas as pd
import yaml
from scipy import stats

DATA='/app/data.csv'; OUT='/app/universes.jsonl'

def num(x):
    try: return None if x is None or not np.isfinite(x) else float(x)
    except Exception: return None

def empty(n=0):
    return {'estimate':None,'estimate_standardized':None,'std_error':None,'std_error_standardized':None,'ci_low_standardized':None,'ci_high_standardized':None,'p_value':None,'n':int(n),'direction':'none','converged':False}

def direction(x):
    return 'none' if x is None or not np.isfinite(x) or abs(x)<1e-15 else ('positive' if x>0 else 'negative')

def codes(s):
    return pd.factorize(s, sort=True)[0].astype(float)

def cluster_se(X, resid, groups, bread):
    _, inv=np.unique(np.asarray(groups).astype(str), return_inverse=True)
    scores=X*np.asarray(resid)[:,None]
    sums=np.zeros((inv.max()+1,X.shape[1]))
    np.add.at(sums,inv,scores)
    return np.sqrt(np.maximum(np.diag(bread@(sums.T@sums)@bread),0))

def logistic(X,y,groups=None):
    p=X.shape[1]; b=np.zeros(p); ok=False; ridge=1e-5
    for _ in range(15):
        eta=np.clip(X@b,-30,30); pr=1/(1+np.exp(-eta)); w=np.maximum(pr*(1-pr),1e-5)
        H=X.T@(w[:,None]*X)+ridge*np.eye(p); score=X.T@(y-pr)
        try: step=np.linalg.solve(H,score)
        except Exception: step=np.linalg.lstsq(H,score,rcond=None)[0]
        b += step
        if np.max(np.abs(step))<1e-5: ok=True; break
    eta=np.clip(X@b,-30,30); pr=1/(1+np.exp(-eta)); w=np.maximum(pr*(1-pr),1e-5)
    H=X.T@(w[:,None]*X)+ridge*np.eye(p)
    try: bread=np.linalg.inv(H)
    except Exception: bread=np.linalg.pinv(H)
    se=np.sqrt(np.maximum(np.diag(bread),0)) if groups is None else cluster_se(X,y-pr,groups,bread)
    return b,se,ok

def analyze(df, selections: dict[str,str]) -> dict:
    try:
        race=selections['race_variable_definition']; scope=selections['stop_scope']; out=selections['search_outcome_definition']; miss=selections['missing_search_handling']; adj=selections['confounding_adjustment']; dep=selections['uncertainty_dependence']
        # Arrays are created without copying the complete dataframe per universe.
        if scope=='durham_county_only': scope_mask=(df['county_name'].to_numpy()== 'Durham County')
        elif scope=='durham_police_only': scope_mask=(df['department_name'].to_numpy()== 'Durham Police Department')
        else: scope_mask=np.ones(len(df),dtype=bool)
        sr=df['subject_race'].astype('string').fillna('').to_numpy(dtype=object); rr=df['raw_Race'].astype('string').fillna('').to_numpy(dtype=object)
        if race=='subject_race_black_white': keep=np.isin(sr,['black','white']); black=(sr=='black').astype(float)
        elif race=='raw_race_black_white': keep=np.isin(rr,['B','W']); black=(rr=='B').astype(float)
        else: keep=pd.notna(sr); black=(sr=='black').astype(float)
        mask=scope_mask&keep
        if out=='search_conducted': y=pd.to_numeric(df['search_conducted'],errors='coerce').to_numpy(float)
        elif out=='person_search_only': y=pd.to_numeric(df['search_person'],errors='coerce').to_numpy(float)
        elif out=='vehicle_search_only': y=pd.to_numeric(df['search_vehicle'],errors='coerce').to_numpy(float)
        else:
            a=pd.to_numeric(df['search_person'],errors='coerce').to_numpy(float); b=pd.to_numeric(df['search_vehicle'],errors='coerce').to_numpy(float)
            y=np.where(np.isfinite(a)&np.isfinite(b),((a==1)|(b==1)).astype(float),np.nan)
        if miss=='missing_as_no_search': y=np.nan_to_num(y,nan=0.)
        else: mask &= np.isfinite(y)
        x=black[mask]; yy=y[mask]; n=len(yy)
        if n<2 or len(np.unique(x))<2 or len(np.unique(yy))<2: return empty(n)
        if adj=='unadjusted_rate_comparison':
            nb=int(x.sum()); nw=n-nb; pb=yy[x==1].mean(); pw=yy[x==0].mean(); est=pb-pw
            X=np.column_stack([np.ones(n),x]); resid=yy-(pw+est*x)
            if dep=='iid_two_proportion': se=math.sqrt(pb*(1-pb)/nb+pw*(1-pw)/nw)
            else:
                g=df['officer_id_hash'].to_numpy()[mask] if dep=='officer_cluster_robust' else df['department_name'].to_numpy()[mask]
                bread=np.linalg.inv(X.T@X); se=cluster_se(X,resid,g,bread)[1]
            p=2*stats.norm.sf(abs(est/se)) if se else (0. if est else 1.); sx=x.std(ddof=1); sy=yy.std(ddof=1); scale=sx/sy if sy else sx; es=est*scale; ses=abs(scale)*se
            return {'estimate':num(est),'estimate_standardized':num(es),'std_error':num(se),'std_error_standardized':num(ses),'ci_low_standardized':num(es-1.96*ses),'ci_high_standardized':num(es+1.96*ses),'p_value':num(p),'n':n,'direction':direction(es),'converged':True}
        # Compact numeric representation of the specified adjustment covariates.
        age=pd.to_numeric(df['subject_age'],errors='coerce').to_numpy(float)[mask]
        sex=codes(df['subject_sex'])[mask]; reason=codes(df['reason_for_stop'])[mask]; dept=codes(df['department_name'])[mask]; county=codes(df['county_name'])[mask]; year=pd.to_datetime(df['date'],errors='coerce').dt.year.to_numpy(float)[mask]
        valid=np.isfinite(age)&np.isfinite(sex)&np.isfinite(reason)&np.isfinite(dept)&np.isfinite(county)&np.isfinite(year)
        x=x[valid]; yy=yy[valid]; n=len(yy); age=age[valid]; sex=sex[valid]; reason=reason[valid]; dept=dept[valid]; county=county[valid]; year=year[valid]
        if n<2 or len(np.unique(x))<2 or len(np.unique(yy))<2: return empty(n)
        sx=x.std(ddof=1); xs=(x-x.mean())/sx
        def z(a): return (a-a.mean())/(a.std(ddof=1) or 1)
        X=np.column_stack([np.ones(n),xs,z(age),z(sex),z(reason),z(dept),z(county),z(year)])
        if dep=='iid_two_proportion': g=None
        elif dep=='officer_cluster_robust': g=df['officer_id_hash'].to_numpy()[mask][valid]
        else: g=df['department_name'].to_numpy()[mask][valid]
        b,sevec,ok=logistic(X,yy,g)
        if not ok: return empty(n)
        es=float(b[1]); ses=float(sevec[1]); est=es/sx; se=ses/sx; p=2*stats.norm.sf(abs(es/ses)) if ses else (0. if es else 1.)
        return {'estimate':num(est),'estimate_standardized':num(es),'std_error':num(se),'std_error_standardized':num(ses),'ci_low_standardized':num(es-1.96*ses),'ci_high_standardized':num(es+1.96*ses),'p_value':num(p),'n':n,'direction':direction(es),'converged':True}
    except Exception:
        return empty(0)

def missing_note(df, selections):
    if selections.get('missing_search_handling') != 'report_missing_as_separate_status':
        return None
    scope=selections['stop_scope']
    if scope=='durham_county_only': scope_mask=(df['county_name'].to_numpy()=='Durham County')
    elif scope=='durham_police_only': scope_mask=(df['department_name'].to_numpy()=='Durham Police Department')
    else: scope_mask=np.ones(len(df),dtype=bool)
    sr=df['subject_race'].astype('string').fillna('').to_numpy(dtype=object)
    rr=df['raw_Race'].astype('string').fillna('').to_numpy(dtype=object)
    race=selections['race_variable_definition']
    if race=='subject_race_black_white': keep=np.isin(sr,['black','white']); black=(sr=='black')
    elif race=='raw_race_black_white': keep=np.isin(rr,['B','W']); black=(rr=='B')
    else: keep=sr!=''; black=(sr=='black')
    if selections['search_outcome_definition']=='search_conducted': y=pd.to_numeric(df['search_conducted'],errors='coerce').to_numpy(float)
    elif selections['search_outcome_definition']=='person_search_only': y=pd.to_numeric(df['search_person'],errors='coerce').to_numpy(float)
    elif selections['search_outcome_definition']=='vehicle_search_only': y=pd.to_numeric(df['search_vehicle'],errors='coerce').to_numpy(float)
    else:
        a=pd.to_numeric(df['search_person'],errors='coerce').to_numpy(float); b=pd.to_numeric(df['search_vehicle'],errors='coerce').to_numpy(float)
        y=np.where(np.isfinite(a)&np.isfinite(b),((a==1)|(b==1)).astype(float),np.nan)
    m=scope_mask&keep
    out=[]
    for label, g in [('black',black),('white',~black)]:
        z=m&g; total=int(z.sum()); missing=int((z&~np.isfinite(y)).sum())
        out.append(f'{label}: {missing}/{total} missing ({missing/total:.6g})' if total else f'{label}: 0/0 missing (null)')
    return '; '.join(out)

def load_u(path):
    with open(path) as f: u=yaml.safe_load(f)
    return u['id'],{z['decision_id']:z['option_id'] for z in u['decisions']}

def main():
    df=pd.read_csv(DATA,low_memory=False)
    rows=[]
    for path in sorted(glob.glob('/app/universes/*.yaml')):
        uid,dec=load_u(path); result=analyze(df,dec); note=missing_note(df,dec); row={'universe_id':uid,'decisions':dec,**result};
        if note is not None: row['notes']=note
        rows.append(row)
    with open(OUT,'w') as f:
        for r in rows: f.write(json.dumps(r,allow_nan=False)+'\n')
    good=[r for r in rows if r['converged'] and r['estimate_standardized'] is not None]
    lines=['# Multiverse analysis report','',f'Evaluated **{len(rows)}** universes; **{len(good)}** converged.','', 'All six decisions are applied inside one parameterized `analyze` function. Unadjusted estimates are Black-minus-White rate differences; adjusted estimates use logistic regression with the specified age, sex, stop reason, department, county, and year covariates.','']
    if good:
        v=np.array([r['estimate_standardized'] for r in good]); lines += [f'Standardized estimate range: **{v.min():.6g}** to **{v.max():.6g}**.',f'Positive estimates: **{int((v>0).sum())} / {len(v)}**.','']
        for dec in sorted(good[0]['decisions']):
            lines.append('## '+dec)
            for opt in sorted({r['decisions'][dec] for r in good}):
                a=np.array([r['estimate_standardized'] for r in good if r['decisions'][dec]==opt]); lines.append(f'- `{opt}`: mean {a.mean():.6g}; range {a.min():.6g} to {a.max():.6g}; n={len(a)}')
            lines.append('')
    lines += ['## Standardization','Unadjusted estimates are scaled by the SDs of race and outcome; adjusted coefficients are for a one-SD race-indicator contrast. Cluster choices use cluster-robust sandwich covariance.']
    open('/app/results.md','w').write('\n'.join(lines)+'\n'); print(f'wrote {len(rows)} universes; successful {len(good)}')
if __name__=='__main__': main()
