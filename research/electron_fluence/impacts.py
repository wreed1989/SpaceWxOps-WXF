"""Versioned DONKI IPS/HSS observations and causal post-impact state features."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests

try:
    from .arrivals import timestamp
except ImportError:
    from arrivals import timestamp

BASE = 'https://kauai.ccmc.gsfc.nasa.gov/DONKI/WS/get/'


def acquire(cache, start, stop):
    cache=Path(cache);cache.mkdir(parents=True,exist_ok=True)
    products={};metadata=[]
    for kind in ['IPS','HSS']:
        params={'startDate':start,'endDate':stop,'version':'ALL','catalog':'M2M_CATALOG'}
        if kind=='IPS':params['location']='Earth'
        r=requests.get(BASE+kind,params=params,timeout=90);r.raise_for_status()
        rows=r.json()
        if rows is None: rows=[]
        if not isinstance(rows,list):raise ValueError('Invalid DONKI '+kind)
        path=cache/f'{kind}-{start}-{stop}.json';path.write_bytes(r.content)
        meta={'path':path.name,'url':r.url,'sha256':hashlib.sha256(r.content).hexdigest(),
              'retrievedAt':datetime.now(timezone.utc).isoformat(),'rows':len(rows)}
        path.with_suffix('.meta.json').write_text(json.dumps(meta,indent=2)+'\n')
        products[kind]=rows;metadata.append(meta)
    return ImpactArchive(products),metadata


class ImpactArchive:
    def __init__(self, products, available=True):
        self.available=available;self.rows=[]
        for kind,events in products.items():
            for event in events:
                if kind=='IPS' and event.get('location')!='Earth':continue
                t=timestamp(event.get('eventTime'));submitted=timestamp(event.get('submissionTime'))
                if t is None or submitted is None or submitted<t:continue
                ident=event.get('activityID' if kind=='IPS' else 'hssID')
                if not ident:continue
                self.rows.append({'kind':kind,'id':ident,'time':t,'submitted':submitted,
                    'version':event.get('versionId'),
                    'cmes':[r['activityID'] for r in event.get('linkedEvents') or [] if '-CME-' in str(r.get('activityID'))],
                    'link':event.get('link')})
        self.rows.sort(key=lambda r:r['submitted'])
        self.submitted=np.array([r['submitted'].value for r in self.rows],dtype=np.int64)

    def at(self, origin, max_age=168):
        origin=pd.Timestamp(origin);end=np.searchsorted(self.submitted,origin.value,side='right')
        start=np.searchsorted(self.submitted,(origin-pd.Timedelta(days=35)).value)
        latest={}
        for r in self.rows[start:end]:latest[(r['kind'],r['id'])]=r
        return [r for r in latest.values() if 0<=(origin-r['time']).total_seconds()/3600<=max_age]

    def features(self, origin, residual):
        rows=self.at(origin)
        f={'impact_feed_available':float(self.available)}
        for kind in ['IPS','HSS']:
            group=[r for r in rows if r['kind']==kind]
            r=max(group,key=lambda q:q['time']) if group else None
            prefix=kind.lower()
            f[prefix+'_reported_count7d']=float(len(group))
            f[prefix+'_age_hours']=(origin-r['time']).total_seconds()/3600 if r else 192.
            f[prefix+'_report_delay_hours']=(r['submitted']-r['time']).total_seconds()/3600 if r else 0.
            f[prefix+'_cme_linked']=float(bool(r and r['cmes']))
            f[prefix+'_flux_response_available']=0.;f[prefix+'_flux_log_response']=0.
            if r:
                before=residual.loc[(residual.index>r['time']-pd.Timedelta(hours=6))&(residual.index<=r['time'])].dropna()
                if len(before)>=4 and residual.index[-1]>=r['time']+pd.Timedelta(hours=3):
                    f[prefix+'_flux_response_available']=1.
                    f[prefix+'_flux_log_response']=float(residual.iloc[-3:].mean()-before.median())
        return f

    def context(self, origin):
        return {'available':self.available,'source':BASE,'events':[
            {**r,'time':r['time'].isoformat(),'submitted':r['submitted'].isoformat()} for r in self.at(origin)],
            'meaning':'Reported Earth/L1 shocks and HSS onsets, gated by each version submission time. A shock is called CME-associated only when the available version links a CME.'}


def load_archive(cache):
    products={}
    for kind in ['IPS','HSS']:
        rows=[]
        for path in sorted(Path(cache).glob(kind+'-*.json')):
            if not path.name.endswith('.meta.json'):rows.extend(json.loads(path.read_text()) or [])
        products[kind]=rows
    return ImpactArchive(products)
