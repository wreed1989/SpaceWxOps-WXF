#!/usr/bin/env python3
"""Read-only archive capture. Never changes model coefficients or live guidance."""
from pathlib import Path
import concurrent.futures as cf
import datetime as dt
import hashlib
import json
import sys
import time
import pandas as pd
import requests
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import sharp_mag_pipeline as core

OUT = Path('history-capture')
OUT.mkdir(exist_ok=True)

def capture_month(item):
    series, start, end = item
    rs = core.historical_record_set(series, start, end, 18)
    name = series.replace('.', '_') + '_' + start.strftime('%Y%m')
    status = {'series':series, 'record_set':rs, 'start':str(start), 'end_exclusive':str(end)}
    try:
        frame = core.query_drms(rs, core.SHARP_QUERY_KEYS)
        path = OUT / (name + '.csv.gz')
        frame.to_csv(path, index=False, compression='gzip')
        status.update(status='ok', rows=len(frame), file=path.name, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        print(json.dumps(status), flush=True)
    except Exception as exc:
        status.update(status='failed', error=str(exc)[:500])
        print(json.dumps(status), flush=True)
    return status

def main():
    jobs=[]
    # NRT reproduces the existing model's instrument product. Definitive samples
    # are a registration/mapping cross-check, not silently pooled into training.
    for year in (2023,2024,2025):
        for month in range(1,13):
            start=dt.date(year,month,1)
            end=dt.date(year+1,1,1) if month==12 else dt.date(year,month+1,1)
            jobs.append(('hmi.sharp_cea_720s_nrt',start,end))
    jobs += [('hmi.sharp_cea_720s',dt.date(2024,5,1),dt.date(2024,6,1))]
    # Warm the metadata cache before bounded concurrency.
    statuses=[capture_month(jobs[0])]
    with cf.ThreadPoolExecutor(max_workers=3) as pool:
        statuses.extend(pool.map(capture_month,jobs[1:]))
    root='https://data.ngdc.noaa.gov/platforms/solar-space-observing-satellites/goes/multi/l2/data/xrsf-l2-flrpt_science/csv/'
    session=requests.Session()
    urls=[]
    try:
        import re
        response=session.get(root,timeout=90);response.raise_for_status()
        for year in (2023,2024,2025):
            names=sorted(set(re.findall(r'sci_xrsf-l2-flrpt_geo_y'+str(year)+r'_v[0-9-]+\.csv',response.text)))
            if not names: raise ValueError('No discovered composite flare file for '+str(year))
            name=names[-1];r=session.get(root+name,timeout=90);r.raise_for_status()
            p=OUT/name;p.write_bytes(r.content)
            urls.append({'url':root+name,'file':name,'sha256':hashlib.sha256(r.content).hexdigest(),'bytes':len(r.content)})
    except Exception as exc:
        urls.append({'error':str(exc)[:500]})
    report={'retrieved_at':dt.datetime.now(dt.timezone.utc).isoformat(), 'magnetic':statuses,'flares':urls,'purpose':'Raw archive completeness audit; not a model training or live publication run.'}
    (OUT/'capture.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({'successful_months':sum(x['status']=='ok' for x in statuses),'failed_months':sum(x['status']!='ok' for x in statuses),'flare_files':len([x for x in urls if 'file' in x])}),flush=True)
    if any(x['status']!='ok' for x in statuses): raise SystemExit(1)

if __name__=='__main__': main()
