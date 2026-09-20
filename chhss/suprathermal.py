"""NOAA SOLAR-1 STIS relay, using the same HAPI source as SWPC Solar Wind.

Operational quality==0 is required. Unavailable detailed quality_flags (-9999)
are retained as missing, never treated as a known-clean instrument bit mask.
The HAPI info 'eV' units are erroneous for flux; the SWPC plot configuration
and STIS data documentation specify differential flux per cm2 s sr MeV.
"""
import csv,io,math
from datetime import datetime,timedelta,timezone
from .pipeline import session
BASE='https://tlv-swpc.woc.noaa.gov/hapi/'
CHANNELS=[f'p{i}' for i in range(1,9)]

def parse(text,now=None):
    now=now or datetime.now(timezone.utc);rows={}
    for row in csv.DictReader(io.StringIO(text)):
        try:
            t=datetime.fromisoformat(row['time_tag'].replace('Z','+00:00'))
            if t>now or t<now-timedelta(days=8):continue
            quality=float(row['quality']);source=float(row['source'])
            if source!=4 or not math.isfinite(quality):continue
            out={'time_tag':t.isoformat().replace('+00:00','Z'),'quality':quality,'source':'SOLAR-1 STIS'}
            for key in CHANNELS:
                v=float(row[key]);out[key]=v if quality==0 and math.isfinite(v) and v>=0 else None
            rows[out['time_tag']]=out
        except (KeyError,ValueError,OverflowError):continue
    result=sorted(rows.values(),key=lambda x:x['time_tag'])
    if not any(any(r[k] is not None for k in CHANNELS) for r in result):raise ValueError('No quality-accepted STIS ion flux')
    return result

def publish(root):
    from .publish import read,write
    path=root/'suprathermal.json';now=datetime.now(timezone.utc);previous=read(path,{})
    params={'id':'solar1-ions-pt1m','time.min':(now-timedelta(days=3)).strftime('%Y-%m-%dT%H:%M:%SZ'),'time.max':now.strftime('%Y-%m-%dT%H:%M:%SZ'),'format':'csv'}
    try:
        r=session().get(BASE+'data',params=params,timeout=(8,35));r.raise_for_status();rows=parse(r.text,now)
        result={'schemaVersion':'wxf-suprathermal-1','instrument':'SOLAR-1 STIS','unit':'ions/(cm² s sr MeV)','retrievedAt':now.isoformat(),'sourceURL':r.url,'channelDefinitionURL':'https://www.swpc.noaa.gov/products/instruments.json','rows':rows,'error':None}
    except Exception as exc:result={**previous,'error':str(exc)[:240]}
    result['attemptedAt']=now.isoformat();write(path,result);return result
