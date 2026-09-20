"""Publish experimental event outlooks, preserving actual creation and fixed target windows."""
import json,math
from pathlib import Path
from datetime import datetime,timedelta,timezone
from concurrent.futures import ThreadPoolExecutor
import requests
from .model import VERSION,FEATURES,TARGETS,feature_values,predict,exceeds
from .inputs import event_inputs, solar_demon_rows, SOLAR_DEMON
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
    active={key:(all(exceeds(r.get(ch),key) for r in before) if len(before)>=3 and all(r.get(ch) is not None for r in before) else None) for key,(ch,threshold) in TARGETS.items()}
    eligible={key:None if active[key] is None else not active[key] for key in TARGETS}
    eligible['p10_40']=eligible['p10_10']
    return {'eligible':eligible,'event':event,'createdAt':stamp(now),'validStart':stamp(start),'validEnd':stamp(end),'latencyMinutes':(now-start).total_seconds()/60,'probabilities':probabilities,'alreadyActive':active,'features':{k:v if math.isfinite(v) else None for k,v in zip(FEATURES,values)},'missingFeatures':[k for k,v in zip(FEATURES,values) if not math.isfinite(v)]}

def collect(now=None,get=requests.get):
    now=now or datetime.now(timezone.utc);warnings=[]
    def fetch(url):
        r=get(url,timeout=(8,25));r.raise_for_status();return r.json()
    def optional(url, text=False):
        try:
            r=get(url,timeout=(8,25));r.raise_for_status()
            return solar_demon_rows(r.text) if text else r.json()
        except Exception as exc:
            warnings.append({'source':url,'reason':str(exc)[:180]});return []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures=[pool.submit(fetch,FLARES),pool.submit(fetch,PROTONS),pool.submit(optional,EVENTS),pool.submit(optional,SOLAR_DEMON,True)]
        raw,protons,edits,demon=[f.result() for f in futures]
    raw=[r for r in raw if r.get('max_time') and date(r['max_time'])<=now]
    obs=[r for r in observations(protons) if date(r['time'])<=now]
    model=json.loads(Path(__file__).with_name('model.json').read_text());out=[];rejected=[];events=[]
    for r in sorted(raw,key=lambda r:r['max_time']):
        if (r.get('max_xrlong') or 0)<1e-6:continue
        peak=date(r['max_time'])
        if not (timedelta(0)<=now-peak<timedelta(hours=48)):continue
        try:ev=event_inputs(r,edits,now,demon)
        except ValueError as exc:
            rejected.append({'peakTime':stamp(peak),'reason':str(exc)});continue
        events.append(ev)
        if not (timedelta(minutes=10)<=now-peak<timedelta(hours=24,minutes=10)):continue
        try:out.append(forecast(ev,raw,obs,model,now))
        except ValueError as exc:rejected.append({'peakTime':stamp(peak),'reason':str(exc)})
    return {'schemaVersion':VERSION,'inputVersion':2,'generatedAt':stamp(now),'status':'experimental','events':events,
            'outlooks':out,'rejected':rejected,'observations':obs,'rawFlares':raw,'inputWarnings':warnings,
            'flareHistoryStart':stamp(now-timedelta(days=7)),'sources':[FLARES,PROTONS,EVENTS,SOLAR_DEMON]}

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
