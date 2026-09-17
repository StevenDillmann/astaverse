import os, json, glob, math, warnings
import numpy as np
import pandas as pd
import yaml
from scipy import sparse
import scipy.linalg
from scipy.special import expit
import statsmodels.api as sm

DATA='/app/data.csv'
OUT='/app/universes.jsonl'
RACES=['black','white','hispanic','asian/pacific islander','other','unknown']
KNOWN=RACES[:-1]

def _bool(s):
    return pd.to_numeric(s.replace({'TRUE':1,'FALSE':0,'True':1,'False':0}), errors='coerce')

def _race(df, opt):
    if opt.startswith('subject_race'):
        r=df['subject_race'].astype('string').str.lower()
        allowed=RACES if opt.endswith('with_unknown') else KNOWN
        return r.where(r.isin(allowed))
    raw=df['raw_Race'].astype('string').str.upper()
    eth=df['raw_Ethnicity'].astype('string').str.upper()
    # Hispanic ethnicity supersedes the raw race field; remaining source codes are recoded directly.
    return pd.Series(np.select([eth.eq('H'),raw.eq('B'),raw.eq('W'),raw.eq('A'),raw.eq('I')],
        ['hispanic','black','white','asian/pacific islander','other'], default='unknown'), index=df.index).astype('string')

def _groups(r):
    return [x for x in RACES if (r==x).any()]

def _contrast(groups, rates, mode):
    pairs=[]
    if mode=='white_reference' and 'white' in groups:
        pairs=[(g,'white') for g in groups if g!='white' and g!='unknown']
        if not pairs: pairs=[(groups[-1],groups[0])]
    else:
        pairs=[(groups[i],groups[j]) for i in range(len(groups)) for j in range(i)]
    vals=[(rates[a]-rates[b],a,b) for a,b in pairs]
    if not vals: return None
    # The primary scalar is the largest absolute requested race contrast.
    return max(vals,key=lambda z:abs(z[0]))

def _cluster_se(influence, df, mode):
    if mode=='iid': return math.sqrt(max(float(np.sum(influence**2)),0.0))
    def one(key):
        z=pd.Series(influence,index=df.index).groupby(df[key].astype('string'),dropna=False).sum().to_numpy()
        return float(np.sum(z*z))
    if mode=='cluster_officer': v=one('officer_id_hash')
    elif mode=='cluster_department': v=one('department_name')
    else: v=one('officer_id_hash')+one('department_name')
    if mode=='two_way_cluster':
        # inclusion-exclusion intersection clusters (officer, department)
        z=pd.DataFrame({'v':influence,'o':df['officer_id_hash'].astype('string'),'d':df['department_name'].astype('string')}).groupby(['o','d'],dropna=False)['v'].sum().to_numpy()
        v-=float(np.sum(z*z))
    return math.sqrt(max(v,0.0))

def _result(n, est, se, outcome_sd, p, conv=True):
    if not conv or any(x is None or not np.isfinite(x) for x in [est,se]):
        return {'estimate':None,'estimate_standardized':None,'std_error':None,'std_error_standardized':None,'ci_low_standardized':None,'ci_high_standardized':None,'p_value':None,'n':int(n),'direction':'none','converged':False}
    scale=1.0/max(float(outcome_sd),1e-12)
    es=est*scale; ss=abs(scale)*se
    return {'estimate':float(est),'estimate_standardized':float(es),'std_error':float(se),'std_error_standardized':float(ss),'ci_low_standardized':float(es-1.96*ss),'ci_high_standardized':float(es+1.96*ss),'p_value':float(2*__import__('scipy').stats.norm.sf(abs(est/se))) if se>0 else 0.0,'n':int(n),'direction':'positive' if est>0 else ('negative' if est<0 else 'none'),'converged':bool(conv)}

def analyze(df, selections):
    try:
        d=df.copy()
        au=selections['analysis_universe']
        dates=pd.to_datetime(d['date'],errors='coerce')
        if au!='all_recorded_rows':
            m=dates.between('2002-01-01','2015-12-31')
            if au=='period_durham_county': m &= d['county_name'].eq('Durham County')
            d=d.loc[m].copy(); dates=dates.loc[d.index]
        r=_race(d,selections['race_definition'])
        so=selections['search_outcome']
        if so=='search_or_frisk':
            a=_bool(d['search_conducted']); b=_bool(d['frisk_performed']); y=((a==1)|(b==1)).astype(float); ok=a.notna()|b.notna()
        else:
            col={'search_conducted':'search_conducted','person_search':'search_person','vehicle_search':'search_vehicle'}[so]
            y=_bool(d[col]); ok=y.notna()
        ok &= r.notna()
        d=d.loc[ok].copy(); y=y.loc[d.index].astype(float).to_numpy(); r=r.loc[d.index]
        n=len(d); groups=_groups(r)
        if n<20 or len(groups)<2 or len(np.unique(y))<2: return _result(n,None,None,np.std(y),None,False)
        outcome_sd=float(np.std(y,ddof=1)) if n>1 else 1.0
        mode=selections['contrast_structure']; dep=selections['dependence_handling']; model=selections['race_adjustment_model']
        rates={g:float(y[r.to_numpy()==g].mean()) for g in groups}
        if model=='crude_rate_comparison':
            cc=_contrast(groups,rates,mode); est,a,b=cc
            ia=(r.to_numpy()==a); ib=(r.to_numpy()==b)
            influence=(ia*(y-rates[a])/ia.sum())-(ib*(y-rates[b])/ib.sum())
            se=_cluster_se(influence,d,dep)
            return _result(n,est,se,outcome_sd,None,True)
        # Logistic models use a sparse IRLS fit to keep the full dataset memory-safe.
        from scipy import sparse as sp
        from scipy.linalg import solve
        race_cols=[g for g in groups if g!='white']
        mats=[]
        for g in race_cols:
            mats.append(sp.csr_matrix((r.to_numpy()==g).astype(float)[:,None]))
        if model=='adjusted_logistic':
            age=pd.to_numeric(d['subject_age'],errors='coerce')
            age=age.fillna(age.median()).to_numpy(float)
            age=(age-np.mean(age))/max(np.std(age),1.0)
            day=(pd.to_datetime(d['date'],errors='coerce')-pd.Timestamp('2000-01-01')).dt.days.fillna(0).to_numpy(float)
            day=(day-np.mean(day))/max(np.std(day),1.0)
            mats += [sp.csr_matrix(np.column_stack([age,day]))]
            for c in ['subject_sex','reason_for_stop','county_name','department_name']:
                codes=pd.Categorical(d[c].astype('string').fillna('__missing__')).codes
                k=int(codes.max())+1
                # Reference coding avoids exact collinearity with the intercept.
                if k>1:
                    mats.append(sp.csr_matrix((np.ones(n),(np.arange(n),codes)),shape=(n,k))[:,1:])
        X=sp.hstack(mats,format='csr')
        X=sp.hstack([sp.csr_matrix(np.ones((n,1))),X],format='csr')
        p=X.shape[1]; beta=np.zeros(p)
        converged=False
        for _ in range(10):
            eta=np.asarray(X@beta).ravel(); pr=expit(np.clip(eta,-35,35)); w=np.maximum(pr*(1-pr),1e-8)
            score=np.asarray(X.T@(y-pr)).ravel()
            H=(X.T.multiply(w))@X + sp.eye(p)*1e-7
            with warnings.catch_warnings():
                warnings.simplefilter('ignore')
                try: step=np.asarray(scipy.linalg.solve(H.toarray(),score,assume_a='sym',check_finite=False)).ravel()
                except Exception: step=np.asarray(np.linalg.lstsq(H.toarray(),score,rcond=1e-10)[0]).ravel()
            beta += step
            if np.max(np.abs(step))<1e-7: converged=True; break
        if not np.all(np.isfinite(beta)): return _result(n,None,None,outcome_sd,None,False)
        # Counterfactual predictions for each included race, averaging over observed covariates.
        preds={}
        for gi,g in enumerate(groups):
            z=X.copy().tolil()
            for j,c in enumerate(race_cols): z[:,1+j]=float(c==g)
            preds[g]=expit(np.clip(np.asarray(z.tocsr()@beta).ravel(),-35,35))
        means={g:float(preds[g].mean()) for g in groups}; cc=_contrast(groups,means,mode)
        if cc is None: return _result(n,None,None,outcome_sd,None,False)
        est,a,b=cc
        pa=preds[a]; pb=preds[b]
        grad=np.asarray(X.T@((pa*(1-pa)-pb*(1-pb))/n)).ravel()
        score=X.multiply((y-expit(np.clip(np.asarray(X@beta).ravel(),-35,35)))[:,None])
        H=(X.T.multiply(np.maximum(expit(np.clip(np.asarray(X@beta).ravel(),-35,35))*(1-expit(np.clip(np.asarray(X@beta).ravel(),-35,35))),1e-8)))@X + sp.eye(p)*1e-7
        bread=np.linalg.inv(H.toarray()) if np.linalg.cond(H.toarray()) < 1e12 else np.linalg.pinv(H.toarray(),rcond=1e-10)
        infl=np.asarray(score@bread.T@grad).ravel()
        se=_cluster_se(infl,d,dep)
        return _result(n,est,se,outcome_sd,None,True)
    except Exception:
        return _result(len(df),None,None,1.0,None,False)

def main():
    df=pd.read_csv(DATA,low_memory=False)
    import gc
    rows=[]
    with open(OUT,'w') as f:
        for fn in sorted(glob.glob('/app/universes/*.yaml')):
            u=yaml.safe_load(open(fn)); selections={x['decision_id']:x['option_id'] for x in u['decisions']}
            z=analyze(df,selections); z={'universe_id':u['id'],'decisions':selections,**z}
            rows.append(z); f.write(json.dumps(z,separators=(',',':'))+'\n'); f.flush(); gc.collect()
    vals=[z['estimate_standardized'] for z in rows if z['estimate_standardized'] is not None]
    conv=sum(bool(z['converged']) for z in rows)
    with open('/app/results.md','w') as f:
        f.write('# Multiverse analysis report\n\n')
        f.write('`analyze(df, selections)` applies the selected universe filter, race definition, search outcome, race contrast, model, and dependence correction through one parameterized code path. Crude analyses compare observed race-specific search rates; logistic analyses use race alone or race plus age, sex, stop reason, county, department, and calendar date. The reported scalar contrast is the largest absolute requested race contrast. Standardized estimates divide probability contrasts and standard errors by the sample SD of the selected binary outcome.\n\n')
        f.write('## Results\n\n')
        f.write(f'- Universes evaluated: {len(rows)}; converged: {conv}.\n')
        if vals: f.write(f'- Standardized estimate range: {min(vals):.6g} to {max(vals):.6g}; mean {np.mean(vals):.6g}; median {np.median(vals):.6g}.\n')
        f.write('- Results are in `universes.jsonl`; no verdict field is included. Differences reflect the selected universe, race coding, outcome, model, contrast, and uncertainty specification.\n')
if __name__=='__main__': main()
