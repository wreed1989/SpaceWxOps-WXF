"""Collect registered Solar Flare evidence without refitting the frozen WXF model.

Image crops are visual context, not quantitative magnetic measurements. Separate
forecast-cutoff inputs, later observations, and completed outcome labels.
"""
from __future__ import annotations
import argparse, concurrent.futures, datetime as dt, hashlib, io, json, math, re, sys
from pathlib import Path
import urllib.parse
import requests
import numpy as np
import pandas as pd
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import sharp_mag_pipeline as model
UTC=dt.timezone.utc
HV='https://api.helioviewer.org/v2/'
BASE='https://raw.githubusercontent.com/wreed1989/SpaceWxOps-WXF/flare-live/'
CHANNELS={'continuum':18,'magnetogram':19,'aia171':10}

def stamp(v):
    t=pd.Timestamp(v)
    if pd.isna(t): raise ValueError('Missing timestamp')
    return (t.tz_localize('UTC') if t.tzinfo is None else t.tz_convert('UTC')).isoformat().replace('+00:00','Z')

def finite(v):
    try:
        x=float(v)
        return x if math.isfinite(x) else None
    except (ValueError,TypeError): return None

def clean(v):
    if isinstance(v,dict): return {str(k):clean(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)): return [clean(x) for x in v]
    if isinstance(v,(dt.datetime,dt.date,pd.Timestamp)): return stamp(v)
    if isinstance(v,np.generic): return clean(v.item())
    if isinstance(v,float) and not math.isfinite(v): return None
    return v

def save(path,v):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(clean(v),indent=2,allow_nan=False)+'\n')

def fetch(url,limit=24000000):
    with requests.get(url,timeout=(12,75),headers={'User-Agent':'SpaceWxOps-WXF/solar-evidence-1'},stream=True) as r:
        r.raise_for_status(); parts=[]; size=0
        for b in r.iter_content(131072):
            size+=len(b)
            if size>limit: raise ValueError('Response exceeds size limit')
            parts.append(b)
        return b''.join(parts)

def jget(url): return json.loads(fetch(url))
def hv(method,**params): return HV+method+'/?'+urllib.parse.urlencode(params)

def header_value(header,key):
    m=re.search(r'<'+re.escape(key)+r'\b[^>]*>\s*([^<]+)',header,re.I)
    return m[1].strip() if m else None

def dedup_events(records):
    """Prefer NOAA's report; group by bin/day or a uniquely attributed near peak.
    Conflicting region assignments remain ambiguous. EUV never supplies GOES class.
    """
    groups=[]
    for r in records:
        if str(r.get('type','')).upper()!='XRA': continue
        cl=str(r.get('particulars1') or '').strip().upper()
        if not re.fullmatch(r'[ABCMX]\d+(?:\.\d+)?',cl): continue
        t=pd.to_datetime(r.get('max_datetime') or r.get('begin_datetime'),utc=True,errors='coerce')
        if pd.isna(t): continue
        reg=model.canonical_noaa_region(r.get('region'))
        event={'peak':stamp(t),'begin':stamp(r.get('begin_datetime') or t),'end':stamp(r.get('end_datetime') or t),
               'region':reg,'class':cl,'bin':r.get('bin'),'observers':[r.get('observatory')],
               'preferred':r.get('status_text')=='+','reports':1,'association':'Reported'}
        same=[]
        for old in groups:
            gap=abs((pd.Timestamp(old['peak'])-t).total_seconds())
            shared_bin=event['bin'] not in (None,'',0) and old['bin']==event['bin'] and old['peak'][:10]==event['peak'][:10]
            if (shared_bin or (reg is not None and old['region']==reg and gap<=120)) and gap<=600: same.append(old)
        if len(same)==1:
            old=same[0]; observers=list(dict.fromkeys(old['observers']+event['observers'])); count=old['reports']+1
            ambiguous=old['region']!=reg or old['association']=='Ambiguous'
            if event['preferred'] and not old['preferred']: old.update(event)
            old['observers']=observers;old['reports']=count
            if ambiguous: old['association']='Ambiguous';old['region']=None
        else: groups.append(event)
    return sorted(groups,key=lambda e:e['peak'],reverse=True)

def image_geometry(meta,header,region):
    """Project NOAA Carrington centers on each registered native image.
    B0 is HGLT_OBS or CRLT_OBS; both are used by the actual provider headers.
    Images with unknown registration are rejected, not given guessed coordinates.
    """
    def keyword(key): return finite(header_value(header,key))
    b0=keyword('HGLT_OBS')
    if b0 is None: b0=keyword('CRLT_OBS')
    if b0 is None: b0=keyword('SOLAR_B0')
    l0=keyword('CRLN_OBS')
    if b0 is None or l0 is None: raise ValueError('Missing observer B0/L0 registration')
    lat=finite(region.get('latitude')); carr=finite(region.get('carrington_longitude'))
    if lat is None or carr is None or abs(lat)>90: raise ValueError('Missing NOAA heliographic center')
    lon=(carr-l0+180)%360-180
    la,lo,b=map(math.radians,[lat,lon,b0])
    x=math.cos(la)*math.sin(lo);y=math.sin(la)*math.cos(b)-math.cos(la)*math.cos(lo)*math.sin(b)
    z=math.sin(la)*math.sin(b)+math.cos(la)*math.cos(lo)*math.cos(b)
    if z<=0: return None
    dsun=finite(meta.get('dsun'));rs=finite(meta.get('rsun'))
    if dsun is None or dsun<1e10 or rs is None or not 1000<rs<2000: raise ValueError('Invalid solar disk geometry')
    solar_radius=keyword('RSUN_REF') or 695700000
    q=solar_radius/dsun; factor=math.sqrt(1-q*q)/(1-q*z)
    cx=float(meta['refPixelX'])-.5+float(meta.get('offsetX',0));cy=float(meta['refPixelY'])-.5+float(meta.get('offsetY',0))
    if abs(float(meta.get('rotation',0)))>.001: raise ValueError('Unsupported image rotation')
    return {'x':cx+rs*x*factor,'y':cy-rs*y*factor,'b0':b0,'l0':l0,'longitude':lon,'latitude':lat,'mu':z,
            'registration':'Helioviewer FITS B0/L0 + native disk geometry; NOAA Carrington center',
            'position_epoch':region['observed_date'],'position_source':'NOAA/SWPC SRS; rigid Carrington tracking'}

def collect_images(out,regions,now):
    latest={}; errors=[]
    for key,sid in CHANNELS.items():
        try: latest[key]=jget(hv('getClosestImage',date=stamp(now),sourceId=sid))
        except Exception as e: errors.append({'channel':key,'error':str(e)[:160]})
    targets=[]
    for key,meta in latest.items():
        end=pd.Timestamp(stamp(meta['date']))
        if abs((pd.Timestamp(now)-end).total_seconds())>36*3600:
            errors.append({'channel':key,'error':'Latest source image is stale'});continue
        for hours in range(24,-1,-4): targets.append((key,end-pd.Timedelta(hours=hours)))
    result={'channels':{},'errors':errors};seen=set()
    def obtain(item):
        key,target=item
        try:
            meta=jget(hv('getClosestImage',date=stamp(target),sourceId=CHANNELS[key]));at=pd.Timestamp(stamp(meta['date']))
            if abs((at-target).total_seconds())>3600: raise ValueError('No image within one hour of requested frame')
            if not str(meta.get('id','')).isdigit(): raise ValueError('Invalid image identifier')
            if int(meta.get('width',0))!=4096: raise ValueError('Native 4096-pixel product not available')
            url=hv('downloadImage',id=meta['id'],width=4096,type='jpg');im=Image.open(io.BytesIO(fetch(url)));im.load()
            if im.size!=(4096,4096): raise ValueError('Unexpected decoded source dimensions')
            header=fetch(hv('getJP2Header',id=meta['id']),2000000).decode('utf-8')
            return key,meta,im.convert('RGB'),header,url,None
        except Exception as e:return key,None,None,None,None,str(e)[:200]
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        for key,meta,im,header,url,error in pool.map(obtain,targets):
            if error:errors.append({'channel':key,'error':error});continue
            ident=(key,str(meta['id']))
            if ident in seen:continue
            seen.add(ident);folder=out/'images'/key/str(meta['id']);folder.mkdir(parents=True,exist_ok=True)
            observed=header_value(header,'DATE-OBS') or header_value(header,'DATE_OBS')
            if observed is None or abs((pd.Timestamp(stamp(observed))-pd.Timestamp(stamp(meta['date']))).total_seconds())>120:
                errors.append({'channel':key,'error':'Observation time cannot be reconciled with image metadata'});continue
            save(folder/'metadata.json',meta);(folder/'header.xml').write_text(header)
            thumb=im.copy();thumb.thumbnail((1024,1024));thumb.save(folder/'disk.jpg',quality=92)
            frame={'id':str(meta['id']),'observed_at':stamp(observed),'index_time':stamp(meta['date']),'native_width':4096,'pixel_scale_arcsec':meta['scale'],
                   'source_url':url,'disk':str((folder/'disk.jpg').relative_to(out)),'regions':{}}
            for reg in regions:
                try:
                    geom=image_geometry(meta,header,reg)
                    if geom is None:continue
                    size=896;x=round(geom['x']);y=round(geom['y']);bounds=(x-size//2,y-size//2,x+size//2,y+size//2)
                    crop=im.crop(bounds);name='AR'+str(model.canonical_noaa_region(reg['region']))+'.jpg';crop.save(folder/name,quality=94)
                    frame['regions'][name[:-4]]={**geom,'image':str((folder/name).relative_to(out)),'native_crop_pixels':size,
                       'clipped':bounds[0]<0 or bounds[1]<0 or bounds[2]>4096 or bounds[3]>4096}
                except Exception as e:errors.append({'channel':key,'region':reg['region'],'error':str(e)[:120]})
            if frame['regions']:result['channels'].setdefault(key,[]).append(frame)
    for frames in result['channels'].values():frames.sort(key=lambda f:f['observed_at'])
    return result

def collect_model(out,guidance):
    issue=pd.Timestamp(guidance['issued']).to_pydatetime();manifest=json.loads(Path('sharp_mag_manifest.json').read_text());q=manifest['quality_filters']
    rows,stats=model.latest_live_rows(series=manifest['live_series'],issue_time=issue,input_lag_hours=manifest['input_lag_hours'],query_hours=40,
        include_multi_region_harps=True,max_longitude=q['max_abs_longitude_deg'],max_obs_vr=q['max_abs_observer_velocity_m_s'],
        max_quality=q['max_quality_integer'],max_input_age_hours=q['max_live_input_age_hours'])
    history,hs=model.fetch_swpc_flare_history();rows=model.add_causal_flare_history(rows,history)
    rows.to_csv(out/'inputs.csv.gz',index=False,compression='gzip')
    columns=['HARPNUM','NOAA_REGION','NOAA_ARS','HARP_REGION_COUNT','T_REC_UTC','LON_FWT','LAT_FWT','QUALITY','SHARP_FINITE_PARAMETER_COUNT']+list(model.SHARP_PARAMETERS)+['PREV_'+s for s in model.SHARP_PARAMETERS]+list(model.HISTORY_RAW_COLUMNS)
    return {'model_version':manifest['model_version'],'issued':guidance['issued'],'valid_start':guidance['valid_start'],'valid_end':guidance['valid_end'],
            'stats':stats,'history':hs,'regions':clean(rows[[s for s in columns if s in rows.columns]].to_dict('records')),'manifest':manifest,
            'full_disk':guidance.get('wxf_full_disk',{}),'training_report':json.loads(Path('sharp_mag_training_report.json').read_text())}

def update_database(out,now,cache):
    """Refresh completed post-training cases, retaining the original fit and test.
    Query the preceding 30 days of events for causal history. Final archive edits
    are retrospective evidence, not a reconstruction of what was known at issue.
    """
    baseline=Path('datasets/sharp_mag_training_table_v2.csv.gz');frozen=pd.read_csv(baseline,low_memory=False)
    start=pd.to_datetime(frozen['ISSUE_DATE']).max().date()-dt.timedelta(days=1);end=now.date()-dt.timedelta(days=1)
    if end<=start:return {'status':'No completed new cases','fitted_through':str(pd.to_datetime(frozen['ISSUE_DATE']).max().date())}
    raw,rs=model.historical_sharp_rows(start=start,end=end,issue_hour=21,input_lag_hours=3,series='hmi.sharp_cea_720s_nrt',cache_dir=cache,
        refresh_cache=True,chunk_days=7,include_multi_region_harps=False,max_longitude=50,max_obs_vr=3500,max_quality=model.DEFAULT_MAX_QUALITY)
    events_path,coverage_path,source=model.obtain_ncei_region_flare_catalog(cache_dir=cache,valid_start=start-dt.timedelta(days=30),
        valid_end_exclusive=end+dt.timedelta(days=1),refresh=True,workers=4)
    events=model.normalize_flare_catalog(events_path);raw=model.add_causal_flare_history(raw,events)
    coverage=model.read_flare_coverage(coverage_path,fallback_start=start-dt.timedelta(days=30),fallback_end_exclusive=end+dt.timedelta(days=1))
    labeled,ls=model.attach_flare_labels(raw,events,coverage,keep_ambiguous_days=False)
    cutoff=pd.to_datetime(frozen['ISSUE_DATE']).max().date();labeled=labeled[pd.to_datetime(labeled['ISSUE_DATE']).dt.date>cutoff].copy()
    if labeled.empty:raise ValueError('No new completed, coverage-verified training cases')
    engineered=model.engineer_features(labeled);extended=pd.concat([labeled.reset_index(drop=True),engineered.reset_index(drop=True)],axis=1);extended=extended.loc[:,~extended.columns.duplicated()]
    merged=pd.concat([frozen,extended],ignore_index=True).drop_duplicates(['NOAA_REGION','ISSUE_DATE'],keep='first')
    path=out/'database.csv.gz';merged.to_csv(path,index=False,compression='gzip');pd.read_csv(coverage_path).to_csv(out/'label_coverage.csv',index=False)
    b1,bx,_,_=model.load_models(Path('.'));features=model.engineer_features(labeled);p1=model.calibrated_predict(b1,features);px=model.x1_predict(p1,bx,features)
    metrics={}
    for name,prob,target in [('M1+',p1,'LABEL_M1'),('X1+',px,'LABEL_X1')]:
        y=labeled[target].to_numpy(dtype=float);metrics[name]={'cases':len(y),'events':int(y.sum()),'brier':float(np.mean((prob-y)**2)),
                    'mean_probability':float(np.mean(prob)),'observed_frequency':float(np.mean(y))}
    return {'status':'Updated','checked_at':stamp(now),'fitted_through':str(cutoff),'database_through':str(pd.to_datetime(merged['ISSUE_DATE']).max().date()),
            'labels_through':str(pd.to_datetime(labeled['VALID_DATE']).max().date()),'frozen_cases':len(frozen),'new_cases':len(labeled),'total_cases':len(merged),
            'frozen_sha256':hashlib.sha256(baseline.read_bytes()).hexdigest(),'database_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'quality':rs,'labels':ls,'forward_check':metrics,'retrained':False,'note':'Retrospective post-training update. Final NRT/archive revisions and report publication delays are not reconstructed. Not an as-issued operational backtest.'}

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=Path('flare-output'));p.add_argument('--database',action='store_true');p.add_argument('--cache',type=Path,default=Path('flare-cache'));args=p.parse_args()
    now=dt.datetime.now(UTC);out=args.output;out.mkdir(parents=True,exist_ok=True)
    data={'schema':'solar-flare-evidence-v1','checked_at':stamp(now),'asset_base':BASE,'errors':[]}
    raw=jget('https://services.swpc.noaa.gov/json/solar_regions.json');events=jget('https://services.swpc.noaa.gov/json/edited_events.json')
    latest=max(r['observed_date'] for r in raw);regions=[r for r in raw if r['observed_date']==latest and finite(r.get('longitude')) is not None and abs(float(r['longitude']))<=90]
    data['regions']=regions;data['region_history']=raw;data['events']=dedup_events(events)
    save(out/'source_regions.json',raw);save(out/'source_events.json',events)
    guidance=json.loads(Path('flare_guidance.json').read_text());save(out/'guidance.json',guidance)
    try:data['model']=collect_model(out,guidance)
    except Exception as e:data['errors'].append({'component':'model_inputs','error':str(e)[:240]})
    data['imagery']=collect_images(out,regions,now)
    if args.database:
        try:data['database']=update_database(out,now,args.cache)
        except Exception as e:data['database']={'status':'Unavailable','checked_at':stamp(now),'error':str(e)[:300],'retrained':False}
    else:
        try:data['database']=jget(BASE+'database-status.json')
        except Exception:data['database']={'status':'Not Yet Checked','retrained':False}
    save(out/'database-status.json',data['database']);save(out/'latest.json',data)
    assets=[]
    for path in sorted(out.rglob('*')):
        if path.is_file():assets.append({'path':str(path.relative_to(out)),'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    save(out/'files.json',assets)
    print(json.dumps({'regions':len(regions),'events':len(data['events']),'channels':{k:len(v) for k,v in data['imagery']['channels'].items()},'database':data['database'],'errors':data['errors'],'image_error_count':len(data['imagery']['errors']),'first_image_errors':data['imagery']['errors'][:8]},indent=2))
    if not all(data['imagery']['channels'].get(k) for k in ('continuum','magnetogram')) or 'model' not in data:
        raise SystemExit('Incomplete registered collection; published feed must remain unchanged')
if __name__=='__main__':main()
