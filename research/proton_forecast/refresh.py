"""Publish experimental event outlooks, preserving actual creation and fixed target windows."""
import json,math,re
from pathlib import Path
from datetime import datetime,timedelta,timezone
from concurrent.futures import ThreadPoolExecutor
import requests
from .model import VERSION,FEATURES,TARGETS,feature_values,predict,exceeds
FLARES='https://services.swpc.noaa.gov/json/goes/primary/xray-flares-7-day.json'
PROTONS='https://services.swpc.noaa.gov/json/goes/primary/integral-protons-3-day.json'
EVENTS='https://services.swpc.noaa.gov/json/edited_events.json'
def date(x):return datetime.fromisoformat(x.replace('Z','+00:00')).replace(tzinfo=timezone.utc)
def stamp(t):return t.isoformat().replace('+00:00','Z')

def observations(rows):
    by={}
    for r in rows:
        if r.get('energy') not in ('>=10 MeV','>=50 MeV'):continue
        try:
            time=stamp(date(r['time_tag']));v=float(r['flux'])
            if not math.isfinite(v) or v<0:continue
            key='P50' if r['energy']=='>=50 MeV' else 'P10';by.setdefault(time,{'time':time})[key]=v
        except (ValueError,TypeError,KeyError):continue
    return sorted(by.values(),key=lambda r:r['time'])

def forecast(event,raw_flares,obs,model,now=None):
    now=now or datetime.now(timezone.utc);peak=date(event['peakTime']);start=peak+timedelta(minutes=10);end=start+timedelta(hours=24)
    if now<start or now>end:raise ValueError('Outside the fixed post-flare forecast window')
    if not (1e-6<=event['peakFlux']<=.01):raise ValueError('Outside C1+ calibrated flare domain')
    by={date(r['time']):r for r in obs}
    last=peak.replace(second=0,microsecond=0)-timedelta(minutes=peak.minute%5)
    if last==peak:last-=timedelta(minutes=5)
    prior=[by.get(last-timedelta(minutes=5*i),{'time':stamp(last-timedelta(minutes=5*i))}) for i in reversed(range(288))]
    if not any(r.get('P10') is not None and r.get('P50') is not None for r in prior[-3:]):raise ValueError('Pre-flare GOES particle input is missing')
    if any(sum(r.get(ch) is not None for r in prior)<240 for ch in ('P10','P50')):raise ValueError('Less than 20 hours of valid pre-flare particle measurements')
    count=sum(peak-timedelta(hours=24)<=date(r['max_time'])<peak and (r.get('max_xrlong') or 0)>=1e-6 for r in raw_flares)
    values=feature_values(event,prior,count);probabilities=predict(values,model)
    before=[r for r in obs if start-timedelta(minutes=15)<=date(r['time'])<start]
    active={key:len(before)>=3 and all(exceeds(r.get(ch),key) for r in before) for key,(ch,threshold) in TARGETS.items()}
    eligible={key:not active[key] for key in TARGETS}
    eligible['p10_40']=not active['p10_10']
    return {'eligible':eligible,'event':event,'createdAt':stamp(now),'validStart':stamp(start),'validEnd':stamp(end),'latencyMinutes':(now-start).total_seconds()/60,'probabilities':probabilities,'alreadyActive':active,'features':{k:v if math.isfinite(v) else None for k,v in zip(FEATURES,values)},'missingFeatures':[k for k,v in zip(FEATURES,values) if not math.isfinite(v)]}

def collect(now=None,get=requests.get):
    now=now or datetime.now(timezone.utc)
    def fetch(url):
        r=get(url,timeout=(8,25));r.raise_for_status();return r.json()
    with ThreadPoolExecutor(max_workers=3) as pool:raw,protons,edits=list(pool.map(fetch,[FLARES,PROTONS,EVENTS]))
    obs=observations(protons);model=json.loads(Path(__file__).with_name('model.json').read_text());out=[];rejected=[]
    for r in sorted(raw,key=lambda r:r['max_time'] or ''):
        if not r.get('max_time') or (r.get('max_xrlong') or 0)<1e-6:continue
        peak=date(r['max_time']);start=date(r['begin_time'])
        if not (timedelta(minutes=10)<=now-peak<timedelta(hours=24,minutes=10)):continue
        ev={'peakTime':stamp(peak),'startTime':stamp(start),'flareClass':r['max_class'],'peakFlux':r['max_xrlong'],'riseMinutes':(peak-start).total_seconds()/60,'longitude':None,'latitude':None}
        # Position must be an explicit reported location for the same event, never region centre.
        matches=[x for x in edits if x.get('max_datetime') and abs((date(x['max_datetime'])-peak).total_seconds())<=120 and x.get('type')=='XRA']
        for x in matches:
            m=re.fullmatch(r'([NS])(\d{1,2})([EW])(\d{1,2})',str(x.get('location') or '').strip())
            if m:ev.update(latitude=int(m[2])*(1 if m[1]=='N' else -1),longitude=int(m[4])*(1 if m[3]=='W' else -1))
        try:out.append(forecast(ev,raw,obs,model,now))
        except ValueError as exc:rejected.append({'peakTime':stamp(peak),'reason':str(exc)})
    return {'schemaVersion':VERSION,'generatedAt':stamp(now),'status':'experimental','outlooks':out,'rejected':rejected,'observations':obs,'rawFlares':raw,'sources':[FLARES,PROTONS,EVENTS]}

def publish(root):
    from chhss.publish import read,write
    path=root/'proton-forecast.json';now=datetime.now(timezone.utc)
    try:
        result=collect(now);old=read(root/'proton-forecast-ledger.json',{'outlooks':[]});records={r['event']['peakTime']:r for r in old['outlooks']}
        for r in result['outlooks']:
            # Immutable first-issued forecast is what future prospective scoring will verify.
            key=r['event']['peakTime']
            if key in records:r['firstIssued']=records[key]['createdAt']
            else:records[key]=r;r['firstIssued']=r['createdAt']
        write(root/'proton-forecast-ledger.json',{'schemaVersion':VERSION,'outlooks':[r for r in records.values() if date(r['event']['peakTime'])>=now-timedelta(days=90)]})
    except Exception as exc:result={'schemaVersion':VERSION,'generatedAt':stamp(now),'status':'unavailable','reason':str(exc)[:240],'outlooks':[]}
    write(path,result);return result
if __name__=='__main__':
    print(json.dumps(publish(Path('chhss-data')),default=str)[:200])
