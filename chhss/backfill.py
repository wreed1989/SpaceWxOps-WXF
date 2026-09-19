"""Backfill observed CH geometry and numeric solar-wind outcomes, not invented issuances.
ROB SPoCA archive masks have retrospective calibration/lifetime filtering.
Scores from this archive are conditional diagnostics, NOT live detector validation.
"""
from __future__ import annotations
import argparse, calendar, csv, hashlib, json, math
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta,timezone
from pathlib import Path
import numpy as np
from acquire import retrieve,tap,write,now
UTC=timezone.utc
CORES={'E':(-40.,-20.,6),'M':(-10.,10.,4),'W':(20.,40.,2)}
VERSION='rob-spoca3-wcs512-core-area-v1'

def stamp(x):return datetime.fromisoformat(str(x).replace('Z','+00:00')).astimezone(UTC)
def iso(x):return x.isoformat().replace('+00:00','Z')
def jd(x):return x.timestamp()/86400+2440587.5

def omni(cache,years):
    fields={'bt':(9,999.9),'bz_gsm':(17,999.9),'temperature':(23,9999999.),'density':(24,999.9),'speed':(25,9999.),'kp':(39,99),'dst':(41,99999),'ap':(50,999)}
    rows={};sources=[]
    for y in sorted(set(years)):
        url=f'https://spdf.gsfc.nasa.gov/pub/data/omni/low_res_omni/omni2_{y}.dat';path=cache/f'omni2_{y}.dat';body=retrieve(url,path)
        for line in body.decode().splitlines():
            p=line.split()
            if not p:continue
            if len(p)<50:raise ValueError('OMNI schema mismatch')
            yr,day,hour=map(int,p[:3])
            if yr!=y or not 1<=day<=(366 if calendar.isleap(y) else 365) or not 0<=hour<24:raise ValueError('OMNI timestamp invalid')
            t=datetime(y,1,1,tzinfo=UTC)+timedelta(days=day-1,hours=hour);r={'time_tag':iso(t)}
            for key,(col,fill) in fields.items():
                v=float(p[col-1]);r[key]=None if v==fill else v/10 if key=='kp' else v
            if r['speed'] is not None and not 0<r['speed']<5000:raise ValueError('Unfiltered solar-wind speed fill code')
            rows[t]=r
        sources.append({'url':url,'sha256':hashlib.sha256(body).hexdigest()})
    return rows,sources

def daily(rows,day):
    rr=[rows.get(day+timedelta(hours=i),{}) for i in range(24)]
    out={}
    for k in ['speed','bt','bz_gsm','density','temperature','kp','dst','ap']:
        v=[r[k] for r in rr if r.get(k) is not None];out[k+'Hours']=len(v)
        out[k]=float(np.mean(v)) if len(v)>=20 else None
    return out

def mask_geometry(path):
    import astropy.units as u
    from astropy.io import fits
    from astropy.coordinates import SkyCoord
    import sunpy.map
    from sunpy.coordinates import frames
    with fits.open(path) as hdus:
        h=next(h for h in hdus if h.data is not None and h.data.ndim==2)
        data=np.asarray(h.data,dtype=np.int32);meta=dict(h.header)
    m=sunpy.map.Map(data,meta)
    target=m.resample(u.Quantity([512,512],u.pix),method='nearest')
    coords=sunpy.map.all_coordinates_from_map(target).transform_to(frames.HeliographicStonyhurst(obstime=target.date))
    lat=coords.lat.to_value(u.deg);cmd=(coords.lon-target.observer_coordinate.lon).wrap_at(180*u.deg).to_value(u.deg)
    c=target.world_to_pixel(SkyCoord(0*u.arcsec,0*u.arcsec,frame=target.coordinate_frame));cx=float(c.x.value);cy=float(c.y.value)
    radius=target.rsun_obs.to_value(u.arcsec)/target.scale.axis1.to_value(u.arcsec/u.pix)
    yy,xx=np.indices(target.data.shape);valid=np.isfinite(lat)&np.isfinite(cmd)&(np.hypot(xx-cx,yy-cy)<=.97*radius)
    mask=(target.data>0)&valid;windows={}
    for key,(lo,hi,lag) in CORES.items():
        region=valid&(cmd>=lo)&(cmd<=hi);ch=region&mask;n=int(region.sum());count=int(ch.sum())
        if n<100:raise ValueError('Core has insufficient WCS disk coverage')
        windows[key]={'A':count/n,'disk':n,'ch':count,'latitude':float(np.mean(lat[ch])) if count else None,'longitude':float(np.mean(cmd[ch])) if count else None,'ids':sorted(int(v) for v in np.unique(target.data[ch]) if v>0)}
    return {'observationTime':iso(target.date.utc.to_datetime(timezone=UTC)),'window':windows,'b0Deg':float(target.observer_coordinate.lat.to_value(u.deg)),'maskSHA256':hashlib.sha256(np.flipud(mask).astype(np.uint8).tobytes()).hexdigest()}

def metrics(rows):
    p=[r for r in rows if r.get('observedSpeed') is not None and r.get('recurrenceSpeed') is not None]
    if not p:return {'n':0,'mae':None,'rmse':None,'bias':None,'recurrenceMae':None,'maeSkillVsRecurrence':None}
    e=np.array([r['forecastSpeed']-r['observedSpeed'] for r in p]);b=np.array([r['recurrenceSpeed']-r['observedSpeed'] for r in p]);mae=float(np.abs(e).mean());bm=float(np.abs(b).mean())
    return {'n':len(p),'mae':mae,'rmse':float(np.sqrt((e*e).mean())),'bias':float(e.mean()),'recurrenceMae':bm,'maeSkillVsRecurrence':1-mae/bm if bm else None}

def backfill(start,end,out,cache,limit=400,workers=2):
    out.mkdir(parents=True,exist_ok=True);cache.mkdir(parents=True,exist_ok=True)
    # Monthly queries are bounded and cacheable; no assumption of an empty day being quiet.
    all_rows=[];month=start.replace(day=1)
    columns='granule_uid,obs_id,time_min,access_url,release_date,ch_stat_hmi_image,ch_stat_hmi_sample_size,ch_stat_hmi_mean,ch_stat_hmi_median,ch_area_pixels'
    while month<end:
        nxt=(month.replace(day=28)+timedelta(days=4)).replace(day=1)
        q=f'SELECT {columns} FROM rob_spoca_ch.epn_core WHERE time_min >= {jd(max(start,month)):.8f} AND time_min < {jd(min(end,nxt)):.8f} ORDER BY time_min'
        all_rows.extend(tap(q,cache/f'tap_{month:%Y%m}.json'));month=nxt
    by_observation={}
    for row in all_rows:by_observation.setdefault(row['access_url'],[]).append(row)
    days={}
    for url,rows in by_observation.items():
        t=datetime.fromtimestamp((rows[0]['time_min']-2440587.5)*86400,UTC);key=t.date().isoformat()
        # Fixed daily sampling rule: closest archive observation to 12Z, never selected by eventual speed.
        distance=abs((t-t.replace(hour=12,minute=0,second=0,microsecond=0)).total_seconds())
        if key not in days or distance<days[key]['distance']:days[key]={'url':url,'rows':rows,'distance':distance,'time':iso(t)}
    path=out/'history.json';old=json.loads(path.read_text()) if path.exists() else {};records={r['day']:r for r in old.get('records',[]) if r.get('measurementVersion')==VERSION}
    tasks=[(d,r) for d,r in sorted(days.items()) if d not in records][:limit]
    errors=[]
    def process(item):
        day,source=item;url=source['url'];f=cache/'masks'/url.rsplit('/',1)[-1]
        try:
            body=retrieve(url,f);g=mask_geometry(f)
            return day,{'day':day,**g,'measurementVersion':VERSION,'sourceUrl':url,'sourceFileSHA256':hashlib.sha256(body).hexdigest(),'downloadedAt':now(),'releaseDates':sorted(set(str(r.get('release_date')) for r in source['rows'])),'catalogMagneticStatistics':[{'id':r['granule_uid'],'source':r['ch_stat_hmi_image'],'n':r['ch_stat_hmi_sample_size'],'meanBlosG':r['ch_stat_hmi_mean'],'medianBlosG':r['ch_stat_hmi_median'],'scope':'whole tracked coronal hole; not per-core signed-field QA'} for r in source['rows']],'availability':'retrospective release; not available at a historical issue time','icme':'unknown'},None
        except Exception as e:return day,None,str(e)
    for day,r,error in ThreadPoolExecutor(max_workers=workers).map(process,tasks):
        if r:records[day]=r
        else:errors.append({'day':day,'error':error})
        print(day,'OK' if r else error,flush=True)
        write(path,{'schemaVersion':'chhss-history-1','generatedAt':now(),'records':list(records.values()),'status':'building','requestedStart':iso(start),'requestedEndExclusive':iso(end)})
    truth,sources=omni(cache/'omni',range((start-timedelta(days=27)).year,end.year+1));pairs=[]
    for r in records.values():
        base=stamp(r['observationTime']).replace(hour=0,minute=0,second=0,microsecond=0)
        for core,(lo,hi,lag) in CORES.items():
            target=base+timedelta(days=lag);o=daily(truth,target);rec=daily(truth,target-timedelta(days=27));window=r['window'][core]
            pairs.append({'id':r['day']+'-'+core,'day':r['day'],'core':core,'validDay':target.date().isoformat(),'forecastSpeed':350+900*window['A'],'observedSpeed':o['speed'],'observedHours':o['speedHours'],'recurrenceSpeed':rec['speed'],'recurrenceHours':rec['speedHours'],'trackedIDs':window['ids'],'icme':'unknown'})
    pairs.sort(key=lambda r:r['day']);cut=sorted(records)[int(.7*len(records))] if records else end.date().isoformat();held=[r for r in pairs if r['day']>=cut]
    missing=[];d=start
    while d<end:
        day=d.date().isoformat()
        if day not in records:missing.append({'day':day,'reason':'No catalogue observation found; not a quiet-day label' if day not in days else 'Pending or failed mask processing'})
        d+=timedelta(days=1)
    history={'schemaVersion':'chhss-history-1','generatedAt':now(),'status':'complete-for-available-catalogue' if all(d in records for d in days) else 'partial','requestedStart':iso(start),'requestedEndExclusive':iso(end),'measurementVersion':VERSION,'catalogueRows':len(all_rows),'availableDays':len(days),'processedDays':len(records),'records':sorted(records.values(),key=lambda r:r['day']),'gaps':missing,'errors':errors,'limitations':['Archive catalogue omits short-lived candidates and can omit no-hole days. It is not an unbiased event-occurrence sample.','Whole-hole HMI catalogue summaries are not per-core polarity QA and are never copied into live forcing.']}
    write(path,history)
    report={'schemaVersion':'chhss-validation-1','generatedAt':now(),'operationallyValidated':False,'target':'fixed daily mean solar-wind speed on E+6 / M+4 / W+2 UTC day; >=20 valid hourly samples','provenance':{'archive':'ROB SPoCA3 published retrospective tracked masks','measurementVersion':VERSION,'omniSources':sources,'availability':'Idealized retrospective reconstruction; NOT an issue-time forecast archive','icmeScreening':'Unknown: no reviewed Earth ICME intervals ingested'},'metrics':{'allCompleteCaseIssuances':metrics(pairs),'temporalHoldout':metrics(held),'byCore':{k:metrics([r for r in held if r['core']==k]) for k in CORES}},'partition':{'cutoff':cut,'method':'last 30% of observation dates; no coefficients fit; no independent-family confidence interval asserted'},'pairs':pairs,'limitations':['This diagnoses the scalar area relation on archived SPoCA masks, not the different live image detector.','Recurring sources and overlapping forecasts are correlated. Sample counts are not independent event counts.','No HSS detection, onset, duration, Dst or Kp calibration is claimed.','No operational promotion or coefficient changes occur automatically.']}
    write(out/'validation.json',report)
    with (out/'omni_hourly.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['time_tag','bt','bz_gsm','temperature','density','speed','kp','dst','ap']);w.writeheader();w.writerows(r for t,r in sorted(truth.items()) if start-timedelta(days=27)<=t<end+timedelta(days=7))
    write(out/'backfill_status.json',{'schemaVersion':'chhss-backfill-status-1','generatedAt':now(),'processedDays':len(records),'availableDays':len(days),'catalogueRows':len(all_rows),'gaps':len(missing),'completePairs':report['metrics']['allCompleteCaseIssuances']['n'],'status':history['status'],'errorCount':len(errors),'omniHours':sum(start-timedelta(days=27)<=t<end+timedelta(days=7) for t in truth),'operationallyValidated':False})
    return history,report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--start',default='2025-01-01');p.add_argument('--end',default='2026-01-01');p.add_argument('--out',type=Path,default=Path('chhss-data'));p.add_argument('--cache',type=Path,default=Path('.cache/chhss'));p.add_argument('--limit',type=int,default=400);p.add_argument('--workers',type=int,default=2);a=p.parse_args()
    start=stamp(a.start+'T00:00:00Z');end=stamp(a.end+'T00:00:00Z')
    if not start<end or (end-start).days>366 or not 1<=a.workers<=4:raise ValueError('Use bounded yearly chunks and 1–4 workers')
    backfill(start,end,a.out,a.cache,a.limit,a.workers)
