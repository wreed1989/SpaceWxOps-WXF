"""Reproducible chronological hindcast with fixed model and reporting parameters."""
from pathlib import Path
import argparse, hashlib, json
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score, average_precision_score
from .model import VERSION,FEATURES,TARGETS,feature_values,predict,exceeds


def build_table(root):
    frames=[]
    for p in sorted(root.glob('particles-*.csv')):
        d=pd.read_csv(p,header=None,names=['time','P10','P50','satellite']);frames.append(d)
    flux=pd.concat(frames,ignore_index=True);flux['time']=pd.to_datetime(flux.time,utc=True);flux=flux.drop_duplicates('time').set_index('time').sort_index()
    flux[['P10','P50']]=flux[['P10','P50']].apply(pd.to_numeric,errors='coerce').mask(lambda x:x<0)
    flux=flux.reindex(pd.date_range(flux.index.min(),flux.index.max(),freq='5min'))
    flares=pd.concat([pd.read_csv(p) for p in sorted(root.glob('flares-*.csv'))],ignore_index=True)
    flares['time']=pd.to_datetime(flares.time,utc=True);flares['start_time']=pd.to_datetime(flares.start_time,utc=True)
    flares=flares[(flares.xrsb_irrad>=1e-6)&(flares.time>=flux.index.min()+pd.Timedelta(days=1))&(flares.time<flux.index.max()-pd.Timedelta(days=1))].drop_duplicates('time').sort_values('time')
    rows=[];times=pd.DatetimeIndex(flares.time).as_unit("ns").asi8;print('Eligible C1+ flares',len(flares),flush=True)
    for n,(_,f) in enumerate(flares.iterrows()):
        peak=f.time;issue=peak+pd.Timedelta(minutes=10);future=flux.loc[issue:issue+pd.Timedelta(hours=24)].iloc[:288]
        prior=flux.loc[peak-pd.Timedelta(hours=24):peak-pd.Timedelta(microseconds=1)]
        if len(prior)<270 or len(future)<288:continue
        lon=f.get('flare_loc_swpc_hgs_lon');lat=f.get('flare_loc_swpc_hgs_lat')
        # GOES XRS triangulated positions are a fallback, not fabricated zero locations.
        if not pd.notna(lon):lon=f.get('flare_loc_xrs_hgs_lon')
        if not pd.notna(lat):lat=f.get('flare_loc_xrs_hgs_lat')
        if pd.notna(lon) and abs(lon)>90:lon=np.nan
        if pd.notna(lat) and abs(lat)>90:lat=np.nan
        event={'peakFlux':f.xrsb_irrad,'riseMinutes':(peak-f.start_time).total_seconds()/60,'longitude':lon,'latitude':lat}
        count=int(np.searchsorted(times,peak.value)-np.searchsorted(times,(peak-pd.Timedelta(hours=24)).value))
        values=feature_values(event,prior[['P10','P50']].to_dict('records'),int(count))
        record={'time':issue.isoformat(),'region':f.get('active_region'),'flareClass':f.flare_class,**dict(zip(FEATURES,values))}
        for key,(channel,threshold) in TARGETS.items():
            series=future[channel];before=flux.loc[issue-pd.Timedelta(minutes=15):issue-pd.Timedelta(microseconds=1),channel]
            # Withhold labels with inadequate truth coverage or an event already active.
            gap=series.isna().astype(int).groupby(series.notna().cumsum()).sum().max()
            valid=series.notna().mean()>=.95 and gap<=6 and before.notna().all() and len(before)>=3 and not (before>= (10 if key=='p10_40' else threshold)).all()
            crossing=(series.map(lambda value: exceeds(value,key)).rolling(3,min_periods=3).sum()==3)
            record[key]=int(crossing.any()) if valid else np.nan
            record[key+'_onset']=float((crossing[crossing].index[0]-issue).total_seconds()/3600) if valid and crossing.any() else np.nan
        rows.append(record)
        if n%5000==0:print('Prepared',n,flush=True)
    return pd.DataFrame(rows)


def metrics(y,p,base,decision):
    y=np.array(y);p=np.array(p);pred=p>=decision;tp=int(((y==1)&pred).sum());fp=int(((y==0)&pred).sum());fn=int(((y==1)&~pred).sum())
    score=brier_score_loss(y,p);reference=brier_score_loss(y,np.full(len(y),base))
    bins=[]
    for lo,hi in zip([0,.01,.03,.1,.3,.6],[.01,.03,.1,.3,.6,1.00001]):
        mask=(p>=lo)&(p<hi)
        if mask.sum():bins.append({'min':lo,'max':min(1,hi),'n':int(mask.sum()),'meanProbability':float(p[mask].mean()),'observedFraction':float(y[mask].mean())})
    return {'n':len(y),'events':int(y.sum()),'brier':score,'brierSkill':1-score/reference,'auc':roc_auc_score(y,p) if len(set(y))==2 else None,'averagePrecision':average_precision_score(y,p),'decisionProbability':decision,'POD':tp/(tp+fn) if tp+fn else None,'FAR':fp/(tp+fp) if tp+fp else None,'hits':tp,'falseAlarms':fp,'misses':fn,'reliability':bins}


def block_skill_interval(times,y,p,base):
    """14-day calendar blocks retain dependence among overlapping flare windows."""
    blocks=np.asarray(pd.DatetimeIndex(times).as_unit('ns').asi8)//(14*86400*10**9)
    group=pd.DataFrame({'block':blocks,'loss':(p-y)**2,'reference':(base-y)**2}).groupby('block').sum()
    rng=np.random.default_rng(1989)
    sample=rng.integers(0,len(group),size=(1000,len(group)))
    numerator=group.loss.to_numpy()[sample].sum(axis=1);denominator=group.reference.to_numpy()[sample].sum(axis=1)
    skill=1-numerator[denominator>0]/denominator[denominator>0]
    return [float(x) for x in np.quantile(skill,[.025,.975])]


def train(root,out):
    out.mkdir(parents=True,exist_ok=True);table=root/'features.csv.gz'
    df=pd.read_csv(table) if table.exists() else build_table(root)
    if not table.exists():df.to_csv(table,index=False,compression='gzip')
    t=pd.to_datetime(df.time,utc=True)
    train=(t<'2014-12-18');cal=(t>='2015-01-15')&(t<'2021-12-18');test=(t>='2022-01-15')
    # Purge active regions spanning a split, including repeated eruptions.
    reg=pd.to_numeric(df.region,errors='coerce');reg=reg.where(reg>0)
    cross=set(reg[train].dropna())&set(reg[cal|test].dropna());train &= ~reg.isin(cross)
    cross2=set(reg[cal].dropna())&set(reg[test].dropna());cal &= ~reg.isin(cross2)
    x=df[FEATURES].to_numpy(float);med=np.nanmedian(x[train],axis=0);fill=np.where(np.isfinite(x),x,med);mean=fill[train].mean(axis=0);scale=fill[train].std(axis=0);scale[scale==0]=1
    z=np.c_[(fill-mean)/scale,~np.isfinite(x)]
    fitted={'version':VERSION,'features':FEATURES,'median':med.tolist(),'mean':mean.tolist(),'scale':scale.tolist(),'models':{},'trainingEnd':'2014-12-17','calibrationEnd':'2021-12-17','testStart':'2022-01-15','testEnd':df.time.iloc[-1]}
    predictions={};evaluation={'version':VERSION,'split':'2010–2014 training; 2015–2021 calibration; 2022–2026 untouched test; 28-day boundary embargo and crossing-region purge','targets':{}}
    for key,(channel,threshold) in TARGETS.items():
        y=df[key].to_numpy();a=train&np.isfinite(y);b=cal&np.isfinite(y);c=test&np.isfinite(y)
        m=LogisticRegression(C=.1,max_iter=2000).fit(z[a],y[a]);raw=m.decision_function(z)
        # No class balancing: retain the observed base rate. Calibration sees only older data.
        calibrator=LogisticRegression(C=1,max_iter=2000).fit(raw[b].reshape(-1,1),y[b])
        fitted['models'][key]={'energyMeV':int(channel[1:]),'thresholdPfu':threshold,'coef':m.coef_[0].tolist(),'intercept':float(m.intercept_[0]),'calSlope':float(calibrator.coef_[0,0]),'calIntercept':float(calibrator.intercept_[0]),'trainingN':int(a.sum()),'trainingEvents':int(y[a].sum()),'calibrationN':int(b.sum()),'calibrationEvents':int(y[b].sum()),'baseRate':float(y[a].mean())}
        predictions[key]=calibrator.predict_proba(raw.reshape(-1,1))[:,1]
    predictions['p10_40']=np.minimum(predictions['p10_40'],predictions['p10_10'])
    scored=df[['time','region','flareClass',*TARGETS]].copy()
    for key in TARGETS:
        y=df[key].to_numpy();a=train&np.isfinite(y);b=cal&np.isfinite(y);c=test&np.isfinite(y);p=predictions[key]
        decision=.2 # fixed scientific reporting point, not optimized on the test data
        evaluation['targets'][key]=metrics(y[c],p[c],float(y[a].mean()),decision)
        evaluation['targets'][key]['brierSkill95']=block_skill_interval(t[c],y[c],p[c],float(y[a].mean()))
        fitted['models'][key]['verification']=evaluation['targets'][key]
        scored[key+'_probability']=p
        print(key,json.dumps({k:v for k,v in evaluation['targets'][key].items() if k!='reliability'}),flush=True)
    out.joinpath('model.json').write_text(json.dumps(fitted,indent=2,allow_nan=False)+'\n')
    out.joinpath('evaluation.json').write_text(json.dumps(evaluation,indent=2,allow_nan=False)+'\n')
    scored[test].to_csv(out/'hindcast.csv.gz',index=False,compression='gzip')
    manifest=json.loads((root/'manifest.json').read_text());out.joinpath('input-manifest.json').write_text(json.dumps({'sources':manifest,'featureSHA256':hashlib.sha256(table.read_bytes()).hexdigest()},indent=2)+'\n')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--cache',type=Path,required=True);p.add_argument('--output',type=Path,default=Path('research/proton_forecast'));a=p.parse_args();train(a.cache,a.output)
