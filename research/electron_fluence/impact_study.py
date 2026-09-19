"""Descriptive event-aligned electron response; catalog outcomes are labels, not predictors."""
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
try:
    from .impacts import load_archive
    from .model import diurnal_profile,harmonics
except ImportError:
    from impacts import load_archive
    from model import diurnal_profile,harmonics


def study(data, archive):
    latest={}
    for r in archive.rows:latest[(r['kind'],r['id'])]=r
    ips=[r for r in latest.values() if r['kind']=='IPS']
    groups={'CME-associated IPS':[r for r in ips if r['cmes']],
            'HSS without nearby IPS':[r for r in latest.values() if r['kind']=='HSS' and not any(abs(r['time']-q['time'])<pd.Timedelta(hours=48) for q in ips)]}
    lags=np.arange(-48,121);fluence=data.flux.rolling(24,min_periods=24).sum()*3600
    report={'schemaVersion':'wxf-electron-event-study-1','kind':'Descriptive association, not a forecast skill test',
        'dataStart':data.index[0].isoformat(),'dataStop':data.index[-1].isoformat(),'lagsHours':lags.tolist(),'groups':{},
        'cautions':['Latest catalog versions define retrospective event labels; not supplied to earlier forecast origins.',
            'IPS may be recorded at L1; model time resolution is hourly. CME association requires a catalog link.',
            'HSS onsets within 48 hours of any IPS are excluded from the HSS-only comparison.',
            'Samples with proton contamination or missing data are excluded. Missing exposure is not filled.',
            'Event windows may overlap; shaded interquartile spread is not a confidence interval or causal effect.',
            'The diurnal profile is estimated from seven days strictly before each event; it is held fixed afterwards.']}
    for name,events in groups.items():
        records=[];skipped={}
        for event in events:
            anchor=event['time'].floor('h');idx=data.index.get_indexer([anchor])[0]
            try:
                if idx<167:raise ValueError('Insufficient pre-event history')
                history=data.iloc[idx-167:idx+1]
                if history.loc[history.flux.notna(),'satellite'].nunique()!=1:raise ValueError('Spacecraft transition')
                beta=diurnal_profile(history.flux)
                timeline=pd.date_range(anchor-pd.Timedelta(hours=48),periods=len(lags),freq='h')
                segment=data.reindex(timeline)
                if segment.loc[segment.flux.notna(),'satellite'].nunique()!=1:raise ValueError('Spacecraft transition')
                residual=np.log1p(segment.flux.to_numpy())-harmonics(timeline)@beta
                baseline=residual[(lags>=-6)&(lags<=0)]
                if np.isfinite(baseline).sum()<5:raise ValueError('Incomplete pre-event flux')
                reference=float(fluence.loc[anchor])
                if not np.isfinite(reference) or reference<=0:raise ValueError('Incomplete pre-event fluence')
                # Wind series in prepare is delayed an hour for model availability.
                # Undo that extra hour only here for descriptive measurement alignment.
                wind=data.speed.reindex(timeline+pd.Timedelta(hours=1)).to_numpy()
                records.append({'event':event,'relativeFlux':np.exp(residual-np.nanmedian(baseline)),
                    'relativeFluence':fluence.reindex(timeline).to_numpy()/reference,'windSpeed':wind})
            except ValueError as exc:skipped[str(exc)]=skipped.get(str(exc),0)+1
        result={'catalogEvents':len(events),'eligibleEvents':len(records),'excluded':skipped,'variables':{}}
        for key in ['relativeFlux','relativeFluence','windSpeed']:
            matrix=np.array([r[key] for r in records]);rows=[]
            for j,lag in enumerate(lags):
                good=matrix[:,j][np.isfinite(matrix[:,j])]
                quant=np.quantile(good,[.25,.5,.75]) if len(good) else [None]*3
                rows.append({'hour':int(lag),'n':len(good),'q25':None if quant[0] is None else float(quant[0]),
                    'median':None if quant[1] is None else float(quant[1]),'q75':None if quant[2] is None else float(quant[2])})
            result['variables'][key]=rows
        report['groups'][name]=result
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--hourly',type=Path,required=True);p.add_argument('--events',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();data=pd.read_csv(a.hourly,index_col=0,parse_dates=True);result=study(data,load_archive(a.events))
    a.output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    for name,g in result['groups'].items():print(name,g['eligibleEvents'],'/',g['catalogEvents'],'eligible',flush=True)
