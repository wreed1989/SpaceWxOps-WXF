"""Acquire complete overlapping GOES flare/particle coverage, with source hashes."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import argparse, hashlib, json, time
import pandas as pd
import requests

FLARES='https://data.ngdc.noaa.gov/platforms/solar-space-observing-satellites/goes/multi/l2/data/xrsf-l2-flrpt_science/csv/'
HAPI='https://iswa.ccmc.gsfc.nasa.gov/hapi/'

def acquire(root, stop='2026-09-01'):
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    edges=pd.date_range('2010-05-01',stop,freq='MS',tz='UTC')
    jobs=[(f'particles-{a:%Y%m}.csv',HAPI+'data',{'id':'goesp_part_flux_P5M','parameters':'P10,P50,satelliteProton','time.min':a.isoformat(),'time.max':b.isoformat(),'format':'csv'}) for a,b in zip(edges,edges[1:])]
    jobs += [(f'flares-{y}.csv',FLARES+f'sci_xrsf-l2-flrpt_geo_y{y}_v1-0-1.csv',None) for y in range(2010,2027)]
    def fetch(job):
        name,url,params=job;p=root/name;m=p.with_suffix('.source.json')
        if p.exists() and m.exists():
            metadata=json.loads(m.read_text())
            if hashlib.sha256(p.read_bytes()).hexdigest()==metadata.get('sha256'):return metadata
        for attempt in range(4):
            try:
                r=requests.get(url,params=params,timeout=(15,100));r.raise_for_status()
                if not r.content or (params and not r.text[:4].isdigit()):raise ValueError(r.text[:180])
                meta={'file':name,'url':r.url,'retrievedAt':datetime.now(timezone.utc).isoformat(),'sha256':hashlib.sha256(r.content).hexdigest(),'bytes':len(r.content)}
                p.write_bytes(r.content);m.write_text(json.dumps(meta,indent=2)+'\n');print(name,meta['bytes'],flush=True);return meta
            except Exception as exc:
                if attempt==3:return {'file':name,'error':str(exc)}
                time.sleep(2**attempt)
    with ThreadPoolExecutor(max_workers=4) as pool:manifest=list(pool.map(fetch,jobs))
    (root/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--cache',type=Path,required=True);a=p.parse_args();acquire(a.cache)
