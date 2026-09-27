#!/usr/bin/env python3
"""Retrospective patch experiment; never replaces production fitted artifacts."""
from __future__ import annotations
import argparse, hashlib, json, re, platform
from importlib.metadata import version
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, average_precision_score, log_loss
PARAMETERS='USFLUX MEANGBT MEANJZH MEANPOT SHRGT45 TOTUSJH MEANGBH MEANALP MEANGAM MEANGBZ MEANJZD TOTUSJZ SAVNCPP TOTPOT MEANSHR AREA_ACR R_VALUE ABSNJZH'.split()
HISTORY='PRIOR_M1_COUNT_24H PRIOR_M1_COUNT_7D PRIOR_M1_COUNT_30D PRIOR_X1_COUNT_7D PRIOR_X1_COUNT_30D HOURS_SINCE_M1 HOURS_SINCE_X1'.split()

def tai_utc(values):
    """TAI to UTC over the explicitly reviewed 2012–2025 scope."""
    x=pd.to_datetime(values.astype(str).str.strip(),format='%Y.%m.%d_%H:%M:%S_TAI',errors='coerce',utc=True)
    if x.notna().any() and (x.dropna().min()<pd.Timestamp('2012-07-01',tz='UTC') or x.max()>=pd.Timestamp('2026-01-01',tz='UTC')): raise ValueError('TAI conversion outside reviewed 2012–2025 scope')
    leap=np.where(x>=pd.Timestamp('2017-01-01T00:00:37Z'),37,np.where(x>=pd.Timestamp('2015-07-01T00:00:36Z'),36,35))
    return x-pd.to_timedelta(leap,unit='s')

def members(row):
    vals=[]
    for key in ['NOAA_ARS','NOAA_AR']:
        v=str(row.get(key,'')).strip()
        if v.startswith('-'):continue
        for tok in re.findall(r'\d{3,6}',v):
            n=int(tok)
            if n and n!=9999: vals.append(n+10000 if n<10000 else n)
    return tuple(sorted(set(vals)))

def event_catalog(paths):
    parts=[]; manifest=[]
    for path in sorted(paths):
        f=pd.read_csv(path,low_memory=False);needed={'time','start_time','flare_class','active_region','flare_id'}
        if not needed<=set(f):raise ValueError('Unrecognized source schema: '+str(path))
        x=f[['flare_id','flare_class','active_region']].copy();x['peak']=pd.to_datetime(f.time,utc=True,errors='coerce');x['start']=pd.to_datetime(f.start_time,utc=True,errors='coerce');x['end']=pd.to_datetime(f.get('end_time'),utc=True,errors='coerce')
        x['known']=pd.concat([x.peak,x.end],axis=1).max(axis=1)
        x['region']=pd.to_numeric(x.active_region,errors='coerce').where(lambda v:(v>0)&(v!=9999));x['region']=x.region.where(x.region>=10000,x.region+10000)
        c=x.flare_class.astype(str).str.strip().str.upper().str.extract(r'^([ABCMX])([0-9]+(?:\.[0-9]+)?)$')
        scale=c[0].map({'A':1e-8,'B':1e-7,'C':1e-6,'M':1e-5,'X':1e-4});x['flux']=pd.to_numeric(c[1],errors='coerce')*scale
        x['M1']=x.flux.ge(1e-5);x['X1']=x.flux.ge(1e-4)
        x['source']=path.name;parts.append(x);manifest.append({'file':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'rows':len(f)})
    e=pd.concat(parts,ignore_index=True).sort_values(['peak','source']).drop_duplicates('flare_id')
    if e.start.isna().any() or e.peak.isna().any():raise ValueError('Missing event timing')
    e['valid_day']=e.start.dt.floor('D')
    return e,manifest

class Groups:
    def __init__(self):self.parent={}
    def root(self,x):
        self.parent.setdefault(x,x)
        while x!=self.parent[x]:self.parent[x]=self.parent[self.parent[x]];x=self.parent[x]
        return x
    def join(self,a,b):
        a,b=self.root(a),self.root(b)
        if a!=b:self.parent[max(a,b)]=min(a,b)

def construct(raw_paths,event_paths):
    raw=pd.concat([pd.read_csv(p) for p in sorted(raw_paths)],ignore_index=True)
    f=raw.copy();f['observed']=tai_utc(f.T_REC);f['issue']=f.observed.dt.floor('D')+pd.Timedelta(hours=21);f['valid_day']=f.issue.dt.floor('D')+pd.Timedelta(days=1)
    for k in PARAMETERS+['LON_FWT','LAT_FWT','OBS_VR','H_MERGE','HARPNUM']:f[k]=pd.to_numeric(f[k],errors='coerce')
    f['members']=f.apply(members,axis=1);f['finite']=np.isfinite(f[PARAMETERS]).sum(axis=1);f['mapped']=f.members.map(len)>0
    masks=[('Mapped To NOAA',f.mapped),('Central 50 Degrees',f.LON_FWT.abs().le(50)),('No HARP Merge',f.H_MERGE.fillna(0).eq(0)),('Observer Velocity',f.OBS_VR.isna()|f.OBS_VR.abs().lt(3500)),('Finite Inputs',f.finite.ge(12)),('Before Issue',f.observed.lt(f.issue))]
    keep=pd.Series(True,index=f.index);attr=[{'stage':'Raw NRT Snapshots','rows':len(f)}]
    for stage,m in masks:keep &=m;attr.append({'stage':stage,'rows':int(keep.sum())})
    f=f[keep].sort_values(['issue','HARPNUM','observed']).drop_duplicates(['issue','HARPNUM'],keep='last').copy()
    # Do not duplicate a NOAA source across simultaneous ambiguous patches.
    exploded=f[['issue','HARPNUM','members']].explode('members')
    ambiguous_map=exploded[exploded.duplicated(['issue','members'],keep=False)]
    bad=set(zip(ambiguous_map.issue,ambiguous_map.HARPNUM))
    overlap=np.array([(t,h) in bad for t,h in zip(f.issue,f.HARPNUM)])
    f=f.loc[~overlap].copy();attr.append({'stage':'Unambiguous Concurrent Patch Mapping','rows':len(f),'removed':int(overlap.sum())})
    # Previous inputs precede future-outcome censoring: no label-driven missingness.
    f=f.sort_values(['HARPNUM','issue']);g=f.groupby('HARPNUM');previous_time=g.issue.shift();gap=(f.issue-previous_time).dt.total_seconds()/3600
    previous_members=g.members.shift();continuity=gap.between(18,36)&f.members.eq(previous_members)
    for k in PARAMETERS:f['PREV_'+k]=g[k].shift().where(continuity)
    f['previous_available']=continuity
    e,manifest=event_catalog(event_paths);major=e[e.M1];known_sources={int(k):x.sort_values('known') for k,x in major.dropna(subset=['region']).groupby('region')}
    years=set(e.peak.dt.year);f=f[f.valid_day.dt.year.isin(years)].copy()
    ambiguous=set(major[major.region.isna()].valid_day)
    byday={k:x for k,x in major.groupby('valid_day')}
    labels=[];hist=[]
    for row in f.itertuples():
        events=byday.get(row.valid_day,pd.DataFrame(columns=['region','X1','M1']))
        match=events[events.region.isin(row.members)];labels.append((int(len(match)>0),int(match.X1.any()),row.valid_day in ambiguous))
        before=[known_sources[n] for n in row.members if n in known_sources]
        past=pd.concat(before,ignore_index=True).drop_duplicates('flare_id') if before else major.iloc[:0]
        past=past[past.known<row.issue]
        def count(days,x=False):return int(((past.start>=row.issue-pd.Timedelta(days=days)) & (past.X1 if x else past.M1)).sum())
        def since(x=False):
            p=past[past.X1] if x else past
            return min(720.,(row.issue-p.start.max()).total_seconds()/3600) if len(p) else 720.
        hist.append([count(1),count(7),count(30),count(7,True),count(30,True),since(),since(True)])
    f[['M1','X1','ambiguous']]=pd.DataFrame(labels,index=f.index);f[HISTORY]=pd.DataFrame(hist,index=f.index)
    before=len(f);f=f[~(f.ambiguous & f.M1.eq(0))].copy();attr.append({'stage':'Exclude Ambiguous Negative Labels','rows':len(f),'removed':before-len(f)})
    f=f[f.issue>=e.start.min()+pd.Timedelta(days=30)].copy()
    f['region_count']=f.members.map(len)
    graph=Groups()
    for row in f.itertuples():
        for n in row.members:graph.join('H'+str(int(row.HARPNUM)),'N'+str(n))
    f['group']=['G'+graph.root('H'+str(int(n))) for n in f.HARPNUM]
    f=f.sort_values(['issue','HARPNUM']).reset_index(drop=True)
    return f,e,{'selection':attr,'events':manifest,'source_series':'hmi.sharp_cea_720s_nrt','target':'At least one event starting during next UTC calendar day in any NOAA member mapped at issue','label_censoring':'Negatives on days with unassigned M1+ events are excluded. Shared patches are counted once.','raw_months':len(raw_paths),'raw_rows':len(raw),'rows':len(f),'M1':int(f.M1.sum()),'X1':int(f.X1.sum())}

def features(d):
    x=pd.DataFrame(index=d.index)
    slog=lambda v:np.sign(v)*np.log1p(np.abs(v))
    for p in PARAMETERS:
        x[p+'__STATE']=slog(d[p]);x[p+'__EVOLUTION']=slog(d[p])-slog(d['PREV_'+p])
    x['Abs Longitude']=d.LON_FWT.abs();x['Latitude']=d.LAT_FWT
    for h in HISTORY:x[h]=np.log1p(d[h])
    return x.replace([np.inf,-np.inf],np.nan)

def split(d):
    tr=d.issue.lt(pd.Timestamp('2019-12-25',tz='UTC'));ca=d.issue.ge(pd.Timestamp('2020-01-01',tz='UTC'))&d.issue.lt(pd.Timestamp('2022-12-25',tz='UTC'));te=d.issue.ge(pd.Timestamp('2023-01-01',tz='UTC'))&d.valid_day.le(pd.Timestamp('2025-12-31',tz='UTC'))
    testgroups=set(d.loc[te,'group']);ca &=~d.group.isin(testgroups);tr &=~d.group.isin(testgroups|set(d.loc[ca,'group']))
    return tr,ca,te

def logit(p):p=np.clip(p,1e-6,1-1e-6);return np.log(p/(1-p)).reshape(-1,1)
def forecast(x,y,tr,ca,te,C):
    p=make_pipeline(SimpleImputer(strategy='median',keep_empty_features=True),StandardScaler(),LogisticRegression(C=C,class_weight='balanced',max_iter=5000,random_state=42))
    p.fit(x.loc[tr],y[tr]);cal=LogisticRegression(C=1e6,max_iter=3000,random_state=42).fit(logit(p.predict_proba(x.loc[ca])[:,1]),y[ca])
    return cal.predict_proba(logit(p.predict_proba(x.loc[te])[:,1]))[:,1]

def score(y,p,prior,groups,draws=2000):
    y=np.asarray(y,dtype=int);p=np.asarray(p,float);ref=(y-prior)**2;err=(y-p)**2
    bins=[]
    for lo,hi in zip([0,.01,.03,.1,.2,.4,.6,.8],[.01,.03,.1,.2,.4,.6,.8,1.000001]):
        m=(p>=lo)&(p<hi);n=int(m.sum())
        if not n:continue
        rate=float(y[m].mean());z=1.96;center=(rate+z*z/(2*n))/(1+z*z/n);half=z*np.sqrt(rate*(1-rate)/n+z*z/(4*n*n))/(1+z*z/n)
        bins.append({'lower':lo,'upper':min(hi,1),'n':n,'events':int(y[m].sum()),'predicted':float(p[m].mean()),'observed':rate,'wilson95':[max(0,center-half),min(1,center+half)]})
    g=pd.DataFrame({'group':groups,'n':1,'err':err,'ref':ref}).groupby('group').sum();rng=np.random.default_rng(20260927);boot=[]
    for _ in range(draws):
        v=g.iloc[rng.integers(0,len(g),len(g))];boot.append(1-v.err.sum()/v.ref.sum())
    threshold=.2;flag=p>=threshold;h=int((flag&(y==1)).sum());fa=int((flag&(y==0)).sum());miss=int((~flag&(y==1)).sum());cn=int((~flag&(y==0)).sum())
    return {'n':len(y),'positive_days':int(y.sum()),'groups':len(g),'brier':float(err.mean()),'baseline_brier':float(ref.mean()),'baseline_probability':float(prior),'brier_skill':float(1-err.mean()/ref.mean()),'brier_skill_95':list(np.quantile(boot,[.025,.975])),'roc_auc':float(roc_auc_score(y,p)),'average_precision':float(average_precision_score(y,p)),'log_loss':float(log_loss(y,p,labels=[0,1])),'reliability':bins,'threshold':threshold,'hits':h,'false_alarms':fa,'misses':miss,'correct_negatives':cn,'TSS':h/(h+miss)-fa/(fa+cn),'POD':h/(h+miss),'FAR':fa/(h+fa) if h+fa else None}

def paired_gain(y,a,b,groups):
    z=pd.DataFrame({'g':groups,'sum':(y-b)**2-(y-a)**2,'n':1}).groupby('g').sum();rng=np.random.default_rng(771);v=[]
    for _ in range(2000):
        q=z.iloc[rng.integers(0,len(z),len(z))];v.append(q['sum'].sum()/q.n.sum())
    return {'brier_reduction':float(z['sum'].sum()/z.n.sum()),'bootstrap95':list(np.quantile(v,[.025,.975]))}

def run(args):
    paths=[p for folder in args.raw for p in Path(folder).glob('hmi_sharp_cea_720s_nrt_*.csv.gz')];events=[p for folder in args.raw for p in Path(folder).glob('sci_xrsf-l2-flrpt_geo_y*.csv')]
    if len({p.name for p in paths})!=len(paths) or len({p.name for p in events})!=len(events):raise ValueError('Duplicate source months/years')
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    d,e,metadata=construct(paths,events);x=features(d);tr,ca,te=split(d)
    report={'schema':'wxf-patch-reassessment-v1','status':'Retrospective Development Experiment — Not Live Coefficients','partitions':{},'source':metadata,'yearly':[],'scores':{},'paired_comparisons':{},'limitations':['2023–2025 already informed this audit; this is not a preregistered untouched final test.','Catalog finalization is gated by peak/end, but historical publication latency is not reconstructed.','Censoring unknown-region events changes the population; no full-disk calibration is established.','Central ±50-degree mapped NRT patches only; no limb, unmapped or farside coverage claim.','QUALITY values retained diagnostically under existing geometry/completeness policy; no new per-bit certification.','Magnetic patch probabilities are not individual NOAA-region probabilities when a patch is shared.']}
    for name,mask in [('training',tr),('calibration',ca),('evaluation',te)]:
        s=d[mask];report['partitions'][name]={'rows':len(s),'groups':s.group.nunique(),'M1':int(s.M1.sum()),'X1':int(s.X1.sum()),'start':str(s.issue.min()),'end':str(s.issue.max()),'shared_rows':int(s.region_count.gt(1).sum())}
    report['group_overlap']={a+'_'+b:len(set(d.loc[ma,'group'])&set(d.loc[mb,'group'])) for a,ma,b,mb in [('train',tr,'calibration',ca),('train',tr,'test',te),('calibration',ca,'test',te)]}
    for year,s in d.groupby(d.valid_day.dt.year):report['yearly'].append({'year':int(year),'patch_days':len(s),'M1':int(s.M1.sum()),'X1':int(s.X1.sum()),'shared_days':int(s.region_count.gt(1).sum())})
    state=[c for c in x if c.endswith('__STATE')]+['Abs Longitude','Latitude'];evolution=state+[c for c in x if c.endswith('__EVOLUTION')]
    variants={'History':HISTORY,'Magnetic State':state,'State + Evolution':evolution,'Combined':list(x)}
    pred=d.loc[te,['issue','valid_day','HARPNUM','members','group','region_count','M1','X1']].copy();cached={}
    for variant,cols in variants.items():
        cached[variant]={};report['scores'][variant]={}
        for label,C in [('M1',1.),('X1',.1)]:
            y=d[label].to_numpy(dtype=int);p=forecast(x[cols],y,tr,ca,te,C)
            if label=='X1':p=np.minimum(p,cached[variant]['M1'])
            cached[variant][label]=p;pred[variant+' '+label]=p
            report['scores'][variant][label]=score(y[te],p,float(y[tr].mean()),d.loc[te,'group'].to_numpy())
            print(variant,label,report['scores'][variant][label]['brier_skill'],flush=True)
    for other in ['History','Magnetic State','State + Evolution']:
        report['paired_comparisons']['Combined vs '+other]={k:paired_gain(d.loc[te,k].to_numpy(),cached['Combined'][k],cached[other][k],d.loc[te,'group'].to_numpy()) for k in ['M1','X1']}
    report['paired_comparisons']['State + Evolution vs Magnetic State']={k:paired_gain(d.loc[te,k].to_numpy(),cached['State + Evolution'][k],cached['Magnetic State'][k],d.loc[te,'group'].to_numpy()) for k in ['M1','X1']}
    blocks=((d.loc[te,'issue']-pd.Timestamp('2023-01-01',tz='UTC')).dt.total_seconds()//(27*86400)).astype(int).to_numpy()
    report['calendar_block_bss_95']={k:score(d.loc[te,k].to_numpy(),cached['Combined'][k],float(d.loc[tr,k].mean()),blocks)['brier_skill_95'] for k in ['M1','X1']}
    report['software']={'python':platform.python_version(),**{p:version(p) for p in ['numpy','pandas','scipy','scikit-learn']}}
    report['limitations'] += ['Bootstrap intervals condition on the fitted coefficients and selected experiment; they exclude fitting, calibration and model-selection uncertainty.', 'The calibration split contains only two X-positive patch-days. X-class probabilities substantially underforecast in the evaluation sample.', 'Changing NRT masks can confound genuine flux emergence; a stable-footprint vector-image experiment remains separate work.', 'Wilson reliability-bin intervals are nominal binomial summaries; repeated patch-days are not independent. Main skill intervals use group/block resampling.']
    for population,mask in [('Single-Region Patches',d.loc[te,'region_count'].eq(1).to_numpy()),('Shared Patches',d.loc[te,'region_count'].gt(1).to_numpy())]:
        report.setdefault('coverage_scores',{})[population]={k:score(d.loc[te,k].to_numpy()[mask],cached['Combined'][k][mask],float(d.loc[tr,k].mean()),d.loc[te,'group'].to_numpy()[mask],draws=1000) for k in ['M1','X1']}
    d.to_csv(out/'patch_dataset.csv.gz',index=False,compression={'method':'gzip','mtime':0});pred.to_csv(out/'patch_holdout_predictions.csv',index=False)
    report['dataset_sha256']=hashlib.sha256((out/'patch_dataset.csv.gz').read_bytes()).hexdigest();report['predictions_sha256']=hashlib.sha256((out/'patch_holdout_predictions.csv').read_bytes()).hexdigest()
    (out/'patch_report.json').write_text(json.dumps(report,indent=2,allow_nan=False));(out/'source_manifest.json').write_text(json.dumps(metadata,indent=2));print(json.dumps(report['partitions'],indent=2),flush=True)
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--raw',nargs='+',required=True);a.add_argument('--out',required=True);run(a.parse_args())
