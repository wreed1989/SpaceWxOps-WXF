#!/usr/bin/env python3
"""Read-only extended capture; never fits or publishes a live forecast."""
from pathlib import Path
import concurrent.futures as cf
import datetime as dt
import hashlib
import json
import re
import requests
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from history_capture import capture_month, OUT

def main():
    jobs=[]
    for year in range(2012,2023):
        for month in range(1,13):
            if year==2012 and month<10: continue
            start=dt.date(year,month,1)
            end=dt.date(year+1,1,1) if month==12 else dt.date(year,month+1,1)
            jobs.append(('hmi.sharp_cea_720s_nrt',start,end))
    statuses=[capture_month(jobs[0])]
    with cf.ThreadPoolExecutor(max_workers=3) as pool:
        statuses.extend(pool.map(capture_month,jobs[1:]))
    root='https://data.ngdc.noaa.gov/platforms/solar-space-observing-satellites/goes/multi/l2/data/xrsf-l2-flrpt_science/csv/'
    session=requests.Session(); urls=[]
    response=session.get(root,timeout=90);response.raise_for_status()
    for year in range(2012,2023):
        try:
            names=sorted(set(re.findall(r'sci_xrsf-l2-flrpt_geo_y'+str(year)+r'_v[0-9-]+\.csv',response.text)))
            if not names: raise ValueError('No discovered composite file')
            name=names[-1];r=session.get(root+name,timeout=90);r.raise_for_status()
            (OUT/name).write_bytes(r.content)
            urls.append({'year':year,'url':root+name,'file':name,'sha256':hashlib.sha256(r.content).hexdigest(),'bytes':len(r.content)})
        except Exception as exc: urls.append({'year':year,'error':str(exc)[:500]})
    report={'retrieved_at':dt.datetime.now(dt.timezone.utc).isoformat(),'magnetic':statuses,'flares':urls,'purpose':'Raw historical verification archive; no live fit or publication.'}
    (OUT/'expansion-capture.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({'successful_months':sum(x['status']=='ok' for x in statuses),'failed_months':sum(x['status']!='ok' for x in statuses),'flare_files':sum('file' in x for x in urls)}),flush=True)
    if any(x['status']!='ok' for x in statuses) or any('error' in x for x in urls): raise SystemExit(1)
if __name__=='__main__': main()
