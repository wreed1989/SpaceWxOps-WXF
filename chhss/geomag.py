"""Dated GFZ hourly Hp60/ap60 relay for local-file dashboards (GFZ has no CORS)."""
from datetime import datetime, timedelta, timezone
import math
from .pipeline import session
URL='https://kp.gfz.de/fileadmin/files_for_gfz_cms/Hp60_ap60_nowcast.txt'

def parse(text, now=None):
    now=now or datetime.now(timezone.utc);rows={}
    for line in text.splitlines():
        f=line.split()
        if not f or f[0].startswith('#') or len(f)<10:continue
        try:
            hour,hp,ap=float(f[3]),float(f[7]),float(f[8])
            start=datetime(int(f[0]),int(f[1]),int(f[2]),tzinfo=timezone.utc)+timedelta(hours=hour)
            if not (0<=hour<24 and all(math.isfinite(x) and x>=0 for x in (hp,ap))):continue
            if start>now:continue
            stamp=start.isoformat().replace('+00:00','Z')
            rows[stamp]={'start':stamp,'hp60':hp,'ap60':ap}
        except (ValueError,OverflowError):continue
    history=sorted(rows.values(),key=lambda x:x['start'])
    if not history:raise ValueError('GFZ returned no valid hourly observations')
    return history

def publish(root):
    from .publish import read,write
    path=root/'hourly-geomag.json';previous=read(path,{})
    now=datetime.now(timezone.utc)
    try:
        r=session().get(URL,timeout=(8,25));r.raise_for_status();history=parse(r.text,now)
        result={'schemaVersion':'gfz-hourly-1','sourceURL':URL,'attribution':'GFZ Helmholtz Centre for Geosciences, Hp60/ap60; CC BY 4.0','retrievedAt':now.isoformat(),'history':history,'latest':history[-1],'error':None}
    except Exception as exc:result={**previous,'error':str(exc)[:240]}
    result['attemptedAt']=now.isoformat();write(path,result);return result
