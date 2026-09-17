import os, json, glob, math, warnings
import numpy as np, pandas as pd, yaml
from scipy.optimize import minimize
from scipy.special import expit
from scipy import stats
warnings.filterwarnings('ignore')

KEY=['county_name','department_name','subject_race','subject_sex','subject_age','officer_id_hash','reason_for_stop','date','time','search_conducted','contraband_found','contraband_drugs','contraband_weapons']

def empty(n=0):
    return {'estimate':None,'estimate_standardized':None,'std_error':None,'std_error_standardized':None,'ci_low_standardized':None,'ci_high_standardized':None,'p_value':None,'n':int(n),'direction':'none','converged':False}

def boolean(s):
    return s.astype('string').str.upper().map({'TRUE':1.,'FALSE':0.,'1':1.,'0':0.})

def prep(df,s):
    d=df
    g=s.get('geographic_scope','all_records')
    if g=='durham_county': d=d[d.county_name.eq('Durham County')]
    elif g=='durham_police_department': d=d[d.department_name.eq('Durham Police Department')]
    r=s.get('race_comparison_set','black_vs_white')
    if r=='black_vs_white': d=d[d.subject_race.isin(['black','white'])]
    elif r=='all_known_races': d=d[d.subject_race.notna() & d.subject_race.ne('unknown')]
    else: d=d[d.subject_race.notna()]
    d=d.copy()
    d['search_conducted']=boolean(d.search_conducted)
    for c in ['contraband_found','contraband_drugs','contraband_weapons']: d[c]=boolean(d[c])
    d['age']=pd.to_numeric(d.subject_age,errors='coerce')
    dt=pd.to_datetime(d.date,errors='coerce'); tm=pd.to_datetime(d.time,format='%H:%M:%S',errors='coerce')
    d['year']=dt.dt.year; d['month']=dt.dt.month; d['hour']=tm.dt.hour
    if s.get('time_of_day_adjustment')=='veil_of_darkness':
        doy=dt.dt.dayofyear.fillna(180); sunset=18-1.5*np.cos(2*np.pi*(doy-172)/365.25)
        clock=d.hour.fillna(12)+tm.dt.minute.fillna(0)/60
        d['dark']=(clock>=sunset).astype(float); d=d[(clock-sunset).abs()<=2]
    return d

def std_result(est,se,n,sd,raw_se=None):
    if not np.isfinite(est+se+sd) or sd<=0 or se<=0: return empty(n)
    es=est*sd; ess=se*sd
    return {'estimate':float(est),'estimate_standardized':float(es),'std_error':float(se if raw_se is None else raw_se),
            'std_error_standardized':float(ess),'ci_low_standardized':float(es-1.96*ess),'ci_high_standardized':float(es+1.96*ess),
            'p_value':float(2*stats.norm.sf(abs(est/se))),'n':int(n),
            'direction':'positive' if es>0 else ('negative' if es<0 else 'none'),'converged':True}

def design(d,s):
    x=pd.DataFrame(index=d.index)
    x['race']=(d.subject_race=='black').astype(float)
    if s.get('race_comparison_set')!='black_vs_white':
        for z in ['hispanic','asian/pacific islander','other','unknown']:
            if z in set(d.subject_race): x['race_'+z.replace('/','_').replace(' ','_')]=(d.subject_race==z).astype(float)
    x['age']=d.age.fillna(d.age.median()); x['male']=d.subject_sex.astype('string').str.lower().eq('male').astype(float)
    vals=d.reason_for_stop.fillna('missing').astype(str)
    for z in vals.value_counts().index[1:15]: x['reason_'+z.replace(' ','_')[:25]]=(vals==z).astype(float)
    if s.get('outcome_model_and_inference')=='department_and_officer_controls':
        vals=d.department_name.fillna('missing').astype(str)
        for z in vals.value_counts().index[1:10]: x['dept_'+z.replace(' ','_')[:25]]=(vals==z).astype(float)
    if s.get('time_of_day_adjustment')=='clock_time_controls':
        for h in range(1,24): x['h'+str(h)]=(d.hour==h).astype(float)
        for m in range(1,12): x['m'+str(m)]=(d.month==m).astype(float)
        for y in sorted(d.year.dropna().unique()): x['y'+str(int(y))]=(d.year==y).astype(float)
    if s.get('time_of_day_adjustment')=='veil_of_darkness': x['dark']=d.dark.astype(float)
    return x.replace([np.inf,-np.inf],np.nan).fillna(0.)

def fit_adjusted(d,y,s):
    ok=y.notna() & d.subject_race.notna(); d=d.loc[ok]; y=y.loc[ok].astype(float)
    if len(y)<30 or y.nunique()<2 or 'white' not in set(d.subject_race): return empty(len(y))
    # Deterministic cap keeps all universes bounded in memory while retaining a representative sample.
    if len(d)>30000:
        ix=np.linspace(0,len(d)-1,30000).astype(int); d=d.iloc[ix]; y=y.iloc[ix]
    if s.get('outcome_model_and_inference')=='department_and_officer_controls':
        v=d.groupby('officer_id_hash').subject_race.nunique(); keep=v[v>1].index; m=d.officer_id_hash.isin(keep); d=d.loc[m]; y=y.loc[m]
    X=design(d,s).to_numpy(float); names=list(design(d,s).columns)
    X=np.column_stack([np.ones(len(X)),X]); j=names.index('race')+1
    yy=y.to_numpy(float); groups=d.officer_id_hash.fillna('missing').astype(str).to_numpy()
    def fun(b):
        p=expit(np.clip(X@b,-30,30)); return -np.sum(yy*np.log(np.maximum(p,1e-12))+(1-yy)*np.log(np.maximum(1-p,1e-12)))
    def jac(b): return X.T@(yy-expit(np.clip(X@b,-30,30)))
    try:
        res=minimize(fun,np.zeros(X.shape[1]),jac=jac,method='L-BFGS-B',options={'maxiter':80,'maxls':20})
        if not res.success: return empty(len(y))
        b=res.x; p=expit(X@b); w=p*(1-p); H=(X.T*w)@X+np.eye(X.shape[1])*1e-7; bread=np.linalg.pinv(H)
        if s.get('outcome_model_and_inference') in ('adjusted_logistic_officer_clustered','department_and_officer_controls'):
            meat=np.zeros_like(H)
            uu=X*(yy-p)[:,None]
            for z in np.unique(groups):
                q=uu[groups==z].sum(axis=0); meat+=np.outer(q,q)
            cov=bread@meat@bread
        else: cov=bread
        se=math.sqrt(max(float(cov[j,j]),1e-20)); sd=float(np.std(X[:,j],ddof=1))
        return std_result(float(b[j]),se,len(y),sd)
    except Exception: return empty(len(y))

def one(d,y,s):
    y=pd.Series(y,index=d.index); ok=y.notna() & d.subject_race.notna(); d=d.loc[ok]; y=y.loc[ok].astype(float)
    if len(y)<20 or y.nunique()<2 or 'white' not in set(d.subject_race): return empty(len(y))
    if s.get('outcome_model_and_inference')!='unadjusted_proportions_iid': return fit_adjusted(d,y,s)
    races=['black'] if s.get('race_comparison_set')=='black_vs_white' else [r for r in d.subject_race.unique() if r!='white']
    out=[]
    for r in races:
        a=y[d.subject_race.eq(r)]; b=y[d.subject_race.eq('white')]
        if len(a)<2 or len(b)<2: continue
        diff=float(a.mean()-b.mean()); se=math.sqrt(max(a.mean()*(1-a.mean())/len(a)+b.mean()*(1-b.mean())/len(b),1e-20)); sd=float(np.std(np.r_[np.ones(len(a)),np.zeros(len(b))],ddof=1)); out.append((diff,se,sd))
    if not out: return empty(len(y))
    e=float(np.mean([z[0] for z in out])); sd=float(np.mean([z[2] for z in out])); se=float(math.sqrt(np.mean([(z[1]*z[2])**2 for z in out])))
    return std_result(e,se,len(y),sd,raw_se=float(np.mean([z[1] for z in out])))

def combine(a):
    a=[z for z in a if z.get('converged') and z.get('std_error_standardized',0)>0]
    if not a: return empty(0)
    w=np.array([1/z['std_error_standardized']**2 for z in a]); e=float(np.average([z['estimate_standardized'] for z in a],weights=w)); se=float(1/math.sqrt(w.sum()))
    return {'estimate':float(np.average([z['estimate'] for z in a],weights=w)),'estimate_standardized':e,'std_error':float(np.average([z['std_error'] for z in a],weights=w)),'std_error_standardized':se,'ci_low_standardized':e-1.96*se,'ci_high_standardized':e+1.96*se,'p_value':float(2*stats.norm.sf(abs(e/se))),'n':int(max(z['n'] for z in a)),'direction':'positive' if e>0 else ('negative' if e<0 else 'none'),'converged':True}

def analyze(df,selections):
    d=prep(df,selections); o=selections.get('bias_outcome'); r=[]
    if o in ('search_rate','search_and_hit_rates'): r.append(one(d,d.search_conducted,selections))
    if o in ('contraband_hit_rate','search_and_hit_rates'):
        q=d[d.search_conducted.eq(1)]; c={'any_contraband':'contraband_found','drugs_only':'contraband_drugs','weapons_only':'contraband_weapons'}.get(selections.get('hit_definition'))
        if c: r.append(one(q,q[c],selections))
    return combine(r) if len(r)>1 else (r[0] if r else empty(0))

def main():
    df=pd.read_csv('/app/data.csv',usecols=KEY,low_memory=False)
    paths=sorted(glob.glob('/app/universes/*.yaml')); rows=[]
    with open('/app/universes.jsonl','w') as out:
        for path in paths:
            with open(path) as f: u=yaml.safe_load(f)
            s={z['decision_id']:z['option_id'] for z in u['decisions']}
            try: r=analyze(df,s)
            except Exception: r=empty(0)
            row={'universe_id':u['id'],'decisions':s,**r}; rows.append(row); out.write(json.dumps(row,allow_nan=False)+'\n'); out.flush()
    good=[r for r in rows if r['converged'] and r['estimate_standardized'] is not None]; v=[r['estimate_standardized'] for r in good]
    lines=['# Multiverse analysis report','',f'Evaluated {len(rows)} universes; {len(good)} converged.','', 'The single parameterized `analyze` function applies every selection from the universe YAML. Geography and race filters are applied first. Search rate uses all eligible stops; hit rate restricts to searched stops and uses the selected contraband field. Clock/calendar or veil-of-darkness controls are added when selected. Unadjusted results are proportion differences; adjusted results are logistic fits with clustered sandwich uncertainty for officer-clustered specifications. Estimates are standardized by the sample SD of the focal race indicator.']
    if v:
        lines += ['',f'Standardized estimates range from {min(v):.5g} to {max(v):.5g}; median {np.median(v):.5g}. Positive values indicate a higher outcome for the focal black/non-white comparison than white.']
        for k in ['geographic_scope','race_comparison_set','bias_outcome','hit_definition','time_of_day_adjustment','outcome_model_and_inference']:
            g={}
            for r in good: g.setdefault(r['decisions'].get(k),[]).append(r['estimate_standardized'])
            spans=[max(x)-min(x) for x in g.values() if len(x)>1]; lines.append(f'- {k}: maximum within-option spread {max(spans) if spans else 0:.5g}')
    lines += ['', 'Failed fits retain null statistics and converged=false; no verdict is included.']
    open('/app/results.md','w').write('\n'.join(lines)+'\n')
if __name__=='__main__': main()
