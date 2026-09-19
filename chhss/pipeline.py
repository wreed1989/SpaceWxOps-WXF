#!/usr/bin/env python3
"""Coronal Hole / HSS Outlook: real AIA/HMI acquisition and backfill worker.
No scripts or science calculations need to run on the operational workstation.
"""
import argparse,base64,calendar,gzip,hashlib,io,json,re,sys,time,traceback,warnings
from datetime import datetime,timedelta
from pathlib import Path
from urllib.parse import urljoin
import numpy as np
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from .core import VERSION,CORES,LAGS,UTC,iso,date,encode_runs,decode_runs,segment,polarity,windows,issue_case,daily_truth,verify
AIA='https://jsoc1.stanford.edu/data/aia/synoptic/'
JSOC='http://jsoc.stanford.edu'
OMNI='https://spdf.gsfc.nasa.gov/pub/data/omni/low_res_omni/'
FIELDS={'bt':(9,999.9),'bz_gsm':(17,999.9),'temperature':(23,9999999.),'density':(24,999.9),'speed':(25,9999.),'kp':(39,99),'dst':(41,99999),'ap':(50,999)}
def dump(path,obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);raw=json.dumps(obj,separators=(',',':'),allow_nan=False).encode();tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_bytes(raw);tmp.replace(path)
def digest(raw):return hashlib.sha256(raw).hexdigest()
def session():
    s=requests.Session();s.headers['User-Agent']='WXF-CHHSS-research/20260919 repository: wreed1989/SpaceWxOps-WXF'
    retry=Retry(total=2,backoff_factor=1,status_forcelist=[429,500,502,503,504])
    for scheme in ['https://','http://']:s.mount(scheme,HTTPAdapter(max_retries=retry))
    return s
class Acquire:
    def __init__(self,cache):self.cache=Path(cache);self.cache.mkdir(parents=True,exist_ok=True);self.http=session()
    def download(self,url,name,params=None,ttl=None):
        path=self.cache/name;side=path.with_suffix(path.suffix+'.source.json')
        if path.exists() and side.exists() and (ttl is None or time.time()-path.stat().st_mtime<ttl):
            raw=path.read_bytes();meta=json.loads(side.read_text())
            if digest(raw)==meta.get('sha256'):return path,meta
        r=self.http.get(url,params=params,timeout=(15,100));r.raise_for_status();raw=r.content
        if name.endswith('.fits') and not raw[:80].startswith(b'SIMPLE'):raise ValueError('Not a FITS response: '+r.url)
        if name.endswith('.json'):r.json()
        meta={'url':r.url,'retrievedAt':iso(datetime.now(UTC)),'sha256':digest(raw),'bytes':len(raw),'transport':'HTTPS' if r.url.startswith('https') else 'HTTP public observations'}
        path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_bytes(raw);tmp.replace(path);dump(side,meta);return path,meta
    def jsoc(self,ds,latest=False):
        params={'op':'rs_list','ds':ds,'key':'**ALL**','seg':'magnetogram','n':100 if not latest else 1}
        p,meta=self.download(JSOC+'/cgi-bin/ajax/jsoc_info','metadata/'+digest(ds.encode())[:24]+'.json',params,ttl=120 if latest else 86400)
        j=json.loads(p.read_text())
        if j.get('status') or not j.get('count'):raise ValueError('JSOC returned no records: '+str(j)[:150])
        out=[]
        for i in range(j['count']):
            h={v['name']:v['values'][i] for v in j['keywords']};h['_segment']=j['segments'][0]['values'][i];h['_metadata']=meta;out.append(h)
        return out
    def hmi(self,when=None):
        from astropy.time import Time
        if when is None:
            last=self.jsoc('hmi.M_720s_nrt[$]',latest=True)[0];target=hmi_time(last);series='hmi.M_720s_nrt'
            t0=Time(target-timedelta(hours=2)).tai.strftime('%Y.%m.%d_%H:%M:%S_TAI');rows=self.jsoc(f'{series}[{t0}/3h]')
        else:
            target=date(when);series='hmi.M_720s';t0=Time(target-timedelta(minutes=18)).tai.strftime('%Y.%m.%d_%H:%M:%S_TAI');rows=self.jsoc(f'{series}[{t0}/36m]')
        ok=[]
        for row in rows:
            try:
                t=hmi_time(row);q=int(str(row.get('QUALITY')),0)
                # Observable 0x400 is NOCOSMICRAY (missing cosmic-ray lists),
                # NOT an NRT identity bit. Accepted only as DEGRADED,
                # with independent temporal sign agreement required below.
                good=q==0 or (series.endswith('_nrt') and q==0x400 and int(str(row.get('QUALLEV1','0')),0)&0x40000000)
                if good and (when is None or abs((t-target).total_seconds())<=1200):ok.append((abs((t-target).total_seconds()),t,row))
            except (ValueError,TypeError):continue
        if not ok:raise ValueError('No quality-accepted signed HMI observation in requested window')
        ok.sort(key=(lambda x:x[1]) if when is None else (lambda x:x[0]),reverse=when is None)
        _,t,row=ok[0];seg=row['_segment']
        self.reference=next((x[2] for x in ok[1:] if 600<=(t-x[1]).total_seconds()<=1800),None) if when is None else None
        if not seg.startswith('/SUM'):raise ValueError('HMI segment offline/missing; staged export required: '+seg)
        p,src=self.download(urljoin(JSOC,seg),'hmi/'+digest((series+row['T_REC']).encode())[:24]+'.fits')
        m=raw_hmi_map(p,row);src={**src,'series':series,'record':row['T_REC'],'metadata':row['_metadata'],'quality':row['QUALITY'],'observationTime':iso(t)}
        src['degraded']=int(str(row['QUALITY']),0)==0x400
        src['qualityFlags']=['NOCOSMICRAY'] if src['degraded'] else []
        return m,src,t
    def aia(self,when,wavelength):
        import sunpy.map
        when=date(when);stamp=when.replace(minute=(when.minute//2)*2,second=0,microsecond=0);errors=[]
        for delta in [0,-2,2,-4,4,-6,6]:
            t=stamp+timedelta(minutes=delta);relative=f'{t:%Y/%m/%d}/H{t:%H}00/AIA{t:%Y%m%d_%H%M}_{wavelength:04d}.fits'
            try:
                p,src=self.download(AIA+relative,'aia/'+relative);m=sunpy.map.Map(p);check_map(m,'AIA',expected_wave=wavelength)
                if abs((map_time(m)-when).total_seconds())>900:raise ValueError('AIA observation is not co-timed')
                src['observationTime']=iso(map_time(m));return m,src
            except Exception as e:errors.append(str(e))
        raise ValueError(f'AIA{wavelength} acquisition failed: '+errors[-1])
def hmi_time(row):
    from astropy.time import Time
    s=str(row.get('T_OBS',''))
    if s.endswith('_TAI'):
        v=s[:-4].replace('_','T',1);v=v[:10].replace('.','-')+v[10:];return Time(v,scale='tai').utc.to_datetime(timezone=UTC)
    return date(row.get('DATE-OBS') or row['DATE__OBS'])
def map_time(m):return m.date.utc.to_datetime(timezone=UTC)
def raw_hmi_map(path,row):
    from astropy.io import fits
    import sunpy.map
    with fits.open(path) as hdus:
        h=next(h for h in hdus if h.data is not None and h.data.ndim==2);data=np.array(h.data,dtype=np.float32);header=h.header.copy()
    # Raw JSOC segments omit metadata. Use the actual matched record, never
    # invented coordinates or an AIA header copied onto magnetic-field pixels.
    for k,v in row.items():
        if k.startswith('_') or k in ['SIMPLE','BITPIX','NAXIS','NAXIS1','NAXIS2','BSCALE','BZERO','BLANK','EXTEND']:continue
        if v is None or str(v) in ['MISSING','NaN','nan']:continue
        if re.fullmatch(r'[+-]?\d+',str(v)):v=int(v)
        elif re.fullmatch(r'[+-]?(?:\d*\.\d+|\d+\.?)(?:[eE][+-]?\d+)?',str(v)):v=float(v)
        try:header[k]=v
        except (ValueError,TypeError):pass
    header['DATE-OBS']=iso(hmi_time(row));header['BUNIT']='G' if str(row.get('BUNIT')).lower()=='gauss' else row.get('BUNIT')
    m=sunpy.map.Map(data,header);check_map(m,'HMI',quality=False);return m

def check_map(m,label,quality=True,expected_wave=None):
    import astropy.units as u
    keys=['ctype1','ctype2','crpix1','crpix2','cdelt1','cdelt2','dsun_obs','rsun_obs']
    if any(k not in m.meta for k in keys):raise ValueError(label+': missing WCS '+str([k for k in keys if k not in m.meta]))
    if not (all(k in m.meta for k in ['hgln_obs','hglt_obs']) or all(k in m.meta for k in ['crln_obs','crlt_obs'])):raise ValueError(label+': observer longitude/latitude missing')
    if label not in str(m.instrument).upper():raise ValueError(label+': wrong instrument')
    if quality and int(str(m.meta.get('quality','-1')),0)!=0:raise ValueError(label+': nonzero or missing QUALITY')
    if expected_wave and abs(m.wavelength.to_value(u.angstrom)-expected_wave)>1:raise ValueError('Wrong AIA wavelength')
    if label=='HMI' and (not m.unit or not m.unit.is_equivalent(u.G)):raise ValueError('HMI must contain signed gauss')

def make_pack(acq,when=None,size=512):
    import astropy.units as u
    from astropy.coordinates import SkyCoord
    import sunpy.map
    from sunpy.coordinates import frames,transform_with_sun_center,propagate_with_solar_surface
    from PIL import Image
    from skimage.measure import find_contours
    warnings.filterwarnings('ignore',category=Warning,module='astropy.io.fits')
    hmi,hsrc,ht=acq.hmi(when);maps={};sources={}
    for wave in [193,171,211]:maps[wave],sources[str(wave)]=acq.aia(ht,wave)
    m=maps[193];target=m.rotate(recenter=True).resample(u.Quantity([size,size],u.pix))
    if not np.allclose(target.rotation_matrix,np.eye(2),atol=1e-5):raise ValueError('Solar north-up transform failed')
    et=map_time(target)
    if abs((ht-et).total_seconds())>1800:raise ValueError('HMI/EUV >30 min apart')
    if when is None and (datetime.now(UTC)-min(et,ht)).total_seconds()>21600:raise ValueError('Latest complete pair is stale')
    coords=sunpy.map.all_coordinates_from_map(target);hgs=coords.transform_to(frames.HeliographicStonyhurst(obstime=target.date))
    lat=hgs.lat.to_value(u.deg);cmd=(hgs.lon-target.observer_coordinate.lon).wrap_at(180*u.deg).to_value(u.deg)
    cen=target.world_to_pixel(SkyCoord(0*u.arcsec,0*u.arcsec,frame=target.coordinate_frame));cx=float(cen.x.value);cy=float(cen.y.value)
    R=float(target.rsun_obs.to_value(u.arcsec)/target.scale.axis1.to_value(u.arcsec/u.pix));yy,xx=np.indices(target.data.shape);rho=np.hypot(xx-cx,yy-cy)/R
    valid=np.isfinite(target.data)&np.isfinite(cmd)&np.isfinite(lat)&(rho<=.97);channels={193:np.asarray(target.data,dtype=float)}
    with transform_with_sun_center():
        for wave in [171,211]:
            if abs((map_time(maps[wave])-et).total_seconds())>300:raise ValueError('AIA channels >5 min apart')
            registered,foot=maps[wave].reproject_to(target.wcs,return_footprint=True,order='bilinear');channels[wave]=np.asarray(registered.data,dtype=float);valid&=(foot>=.99)&np.isfinite(registered.data)
        # Average before resampling to avoid selecting sparse high-res pixels.
        reduced=hmi.superpixel(u.Quantity([4,4],u.pix),func=np.mean);hm,hfoot=reduced.reproject_to(target.wcs,return_footprint=True,order='bilinear')
    blos=np.asarray(hm.data,dtype=float)*hmi.unit.to(u.G)
    prior=None;prior_foot=None;prior_src=None
    if hsrc['degraded'] and acq.reference:
        row=acq.reference;pp,prior_src=acq.download(urljoin(JSOC,row['_segment']),'hmi/'+digest(('reference'+row['T_REC']).encode())[:24]+'.fits')
        ref=raw_hmi_map(pp,row).superpixel(u.Quantity([4,4],u.pix),func=np.mean)
        with propagate_with_solar_surface():
            oldmap,prior_foot=ref.reproject_to(target.wcs,return_footprint=True,order='bilinear')
        prior=np.asarray(oldmap.data,dtype=float)*ref.unit.to(u.G);prior_src={**prior_src,'observationTime':iso(hmi_time(row)),'record':row['T_REC'],'quality':row['QUALITY']}
    b0=float(target.observer_coordinate.lat.to_value(u.rad));latr=np.radians(lat);lonr=np.radians(cmd)
    cosc=np.sin(latr)*np.sin(b0)+np.cos(latr)*np.cos(b0)*np.cos(lonr);ds=target.dsun.to_value(u.m);rs=target.rsun_meters.to_value(u.m);mu=(ds*cosc-rs)/np.sqrt(ds*ds+rs*rs-2*ds*rs*cosc)
    mask,components,detector=segment(channels,valid,rho);labels,win=windows(mask,valid,cmd,lat)
    def diagnose(region):
        result=polarity(region,blos,mu,hfoot)
        if hsrc['degraded']:
            comparison=polarity(region,prior,mu,prior_foot) if prior is not None else None
            agree=bool(result['polarity'] is not None and comparison and comparison['polarity']==result['polarity'])
            result['temporalAgreement']=agree;result['referenceEvidence']=comparison
            if not agree:result['polarity']=None;result['quality']='degraded HMI: temporal sign not established'
            else:result['quality']='degraded HMI: sign consistent in two observations'
        return result
    sectors={k:diagnose(mask&(labels==i)) for i,k in enumerate(CORES,1)}
    raster=np.flipud(mask).astype(np.uint8);cl=np.flipud(labels).astype(np.uint8);mask_id=digest(raster.tobytes());holes=[];contours=[]
    for i in range(1,int(components.max())+1):
        reg=components==i;n=int(reg.sum())
        if not n:continue
        ph=diagnose(reg);lat0=float(np.mean(lat[reg]));lon0=float(np.mean(cmd[reg]));key='E' if lon0<-10 else 'W' if lon0>10 else 'M';hid=f'CH-{et:%Y%m%d}-{i:02d}'
        holes.append({'id':hid,'name':hid,'type':'coronal-hole candidate','latitude':lat0,'longitude':lon0,'lat':lat0,'lon':lon0,'cmd':lon0,'areaDisk':float(n/(np.pi*R*R)),'areaFraction':float(n/(np.pi*R*R)),'areaPct':float(100*n/(np.pi*R*R)),'width':float(np.max(cmd[reg])-np.min(cmd[reg])),'polarity':ph['polarity'],'polarityEvidence':ph,'source':VERSION,'sectorKey':key,'quantitative':True,'time':iso(et),'coordinateFrame':'HGS'})
        for line in find_contours(np.flipud(reg).astype(float),.5):
            points=line[::max(1,len(line)//160)]
            ring=[{'lat':float(lat[int(np.clip(round(size-1-y),0,size-1)),int(np.clip(round(x),0,size-1))]),'lon':float(cmd[int(np.clip(round(size-1-y),0,size-1)),int(np.clip(round(x),0,size-1))])} for y,x in points]
            ring=[v for v in ring if np.isfinite(v['lat']) and np.isfinite(v['lon'])]
            contours.append({'id':hid,'lat':lat0,'lon':lon0,'nPix':n,'areaPct':float(100*n/(np.pi*R*R)),'ring':ring,'points':[[float(x/size*100),float(y/size*100)] for y,x in points]})
            if not holes[-1].get('ring'):holes[-1]['ring']=ring
    reviews=[]
    for entry in detector.get('componentEvidence',[]):
        if entry['accepted']:
            h=holes[entry['component']-1]
            h['thermalEvidence']=entry
            h['identification']='magnetically-supported candidate' if h['polarity'] in [-1,1] else 'provisional EUV candidate; magnetic sign unresolved'
        else:
            y=int(round(entry['centroidYPx']));x=int(round(entry['centroidXPx']))
            if np.isfinite(lat[y,x]) and np.isfinite(cmd[y,x]):
                reviews.append({'id':f'PATCH-{entry["candidate"]:02d}','lat':float(lat[y,x]),'lon':float(cmd[y,x]),
                                'areaDisk':float(entry['pixels']/(np.pi*R*R)),'quantitative':False,
                                'identification':'excluded dark patch','thermalEvidence':entry,'reason':entry['reason']})
    data=np.maximum(channels[193],0);lo,hi=np.percentile(data[valid],[1,99.7]);norm=np.nan_to_num(np.clip((np.log1p(data)-np.log1p(lo))/max(1e-9,np.log1p(hi)-np.log1p(lo)),0,1));rgb=np.stack([norm**.55,norm**1.1*.8,norm**2*.28],axis=-1);rgb[rho>1.06]=0
    out=io.BytesIO();Image.fromarray(np.flipud((rgb*255).astype(np.uint8))).save(out,format='PNG')
    pol={'schemaVersion':'chhss-polarity-1','source':'HMI LOS FITS + matched AIA mask','units':'G','quantity':'B_R','radialApproximation':'B_LOS/mu; no vector information','registrationQuality':'wcs-reprojected','observationTime':iso(ht),'euvObservationTime':iso(et),'muMin':.4,'maskId':mask_id,'sector':sectors,'hmiQuality':hsrc['quality'],'degraded':hsrc['degraded'],'qualityFlags':hsrc['qualityFlags'],'temporalReference':prior_src,'hmiSource':hsrc,'hmiPrebin':'4x4 arithmetic mean; then WCS bilinear to 512 grid'}
    pack={'schemaVersion':'chhss-science-1','product':'Coronal Hole / HSS Outlook','measurementEngine':VERSION,'observationTime':iso(et),'availableAt':iso(datetime.now(UTC)),'generatedAt':iso(datetime.now(UTC)),'historical':when is not None,'maskId':mask_id,'source':{'instrument':'AIA193','euv':sources,'hmi':hsrc},'preview':{'url':'data:image/png;base64,'+base64.b64encode(out.getvalue()).decode(),'role':'Unannotated numerical AIA193 raster; display stretch never drives segmentation'},'measured':{'ok':True,'width':size,'height':size,'cx':cx,'cy':size-1-cy,'radius':R,'scienceRadius':.97*R,'imageProduct':'aia193','maskId':mask_id,'rasterEncoding':'runs-u8-v1','maskRuns':encode_runs(raster),'coreLabelRuns':encode_runs(cl),'geometry':{'registration':'wcs','northUp':True,'b0Deg':float(np.degrees(b0)),'limbRadiusPx':R,'scienceRadiusPx':.97*R,'cx':cx,'cy':size-1-cy,'sourceWCSHeader':target.wcs.to_header_string()},'window':win,'sector':{},'contours':contours},'holes':holes,'polarity':pol,'detector':detector,'notes':['Automatic multi-passband low-intensity candidate mask, not CHIMERA or a manually validated CH catalogue.','AIA and HMI use observed WCS, observer position and actual timestamps, including TAI conversion.','Polarity is independent per core and component; unknown is not quiet or neutral.','No trained forecast coefficients, local Bz prediction, source-to-Earth connectivity certification or Dst-to-G conversion.']}
    pack['reviewCandidates']=reviews
    pack['notes'][0]='Multi-passband dark regions require cool-corona contrast before entering the mask; excluded patches remain available for review. This is not CHIMERA or a validated catalogue.'
    assert digest(decode_runs(pack['measured']['maskRuns'],(size,size)).tobytes())==mask_id
    return pack

def omni_line(line):
    p=line.split()
    if len(p)<50:raise ValueError('OMNI schema changed')
    y,d,h=map(int,p[:3]);t=datetime(y,1,1,tzinfo=UTC)+timedelta(days=d-1,hours=h)
    if not 1<=d<=(366 if calendar.isleap(y) else 365) or not 0<=h<24:raise ValueError('OMNI timestamp')
    out={'time_tag':iso(t)}
    for name,(column,fill) in FIELDS.items():
        v=float(p[column-1]);out[name]=None if v==fill else v/10 if name=='kp' else v
    return out

def get_truth(acq,start,end,output):
    rows=[];sources=[]
    for year in range(start.year,end.year+1):
        p,src=acq.download(OMNI+f'omni2_{year}.dat',f'omni/omni2_{year}.dat',ttl=86400 if year==datetime.now(UTC).year else None)
        selected=[omni_line(line) for line in p.read_text().splitlines() if line.strip()];selected=[r for r in selected if start<=date(r['time_tag'])<end];rows+=selected;sources.append({**src,'selectedRows':len(selected)})
    dump(output/'omni-manifest.json',{'sources':sources,'hourlyRecords':len(rows),'speedValidHours':sum(r['speed'] is not None for r in rows),'start':iso(start),'endExclusive':iso(end),'kind':'retrospective OMNI2 truth'})
    with gzip.open(output/'omni_hourly.jsonl.gz','wt') as f:
        for row in rows:f.write(json.dumps(row,separators=(',',':'))+'\n')
    return rows

def backfill(acq,start,end,output,max_days=None):
    cases=[];failures=[];log=[];day=start;attempts=0;out=output/'history';out.mkdir(parents=True,exist_ok=True)
    while day<end and (max_days is None or attempts<max_days):
        attempts+=1;key=f'{day:%Y%m%d}';path=out/(key+'.json')
        try:
            if path.exists():pack=json.loads(path.read_text());assert pack['measurementEngine']==VERSION
            else:pack=make_pack(acq,iso(day.replace(hour=12)));dump(path,pack)
            c=issue_case(pack);cases.append(c);log.append({'date':str(day.date()),'ok':True,'maskId':pack['maskId'],'polarity':{k:v['polarity'] for k,v in pack['polarity']['sector'].items()}});print('BACKFILL',key,'OK',log[-1]['polarity'],flush=True)
        except Exception as e:
            fail={'date':str(day.date()),'ok':False,'error':str(e),'trace':traceback.format_exc()};failures.append(fail);log.append(fail);print('BACKFILL',key,'FAILED',str(e),flush=True)
        dump(output/'backfill-progress.json',{'methodVersion':VERSION,'start':iso(start),'endExclusive':iso(end),'attempted':attempts,'succeeded':len(cases),'failed':len(failures),'days':log,'updatedAt':iso(datetime.now(UTC))});day+=timedelta(days=1)
    truth=get_truth(acq,start-timedelta(days=28),min(end,day)+timedelta(days=8),output);report=verify(cases,daily_truth(truth),len(failures));dump(output/'validation.json',report);dump(output/'cases.json',cases)
    with gzip.open(output/'cases.jsonl.gz','wt') as f:
        for row in cases:f.write(json.dumps(row,separators=(',',':'))+'\n')
    return report

def live(acq,output):
    now=datetime.now(UTC)
    status={'startedAt':iso(now),'product':'Coronal Hole / HSS Outlook','methodVersion':VERSION,
            'measurement':{'ok':False,'state':'pending'},'recurrence':{'ok':False,'state':'pending'}}
    dump(output/'status.json',status)
    # Recurrence has its own source and failure boundary. An AIA/HMI outage must
    # not prevent the rolling OMNI window from refreshing (or vice versa).
    try:
        recent=output/'recurrence-source';recent.mkdir(parents=True,exist_ok=True)
        rows=get_truth(acq,now-timedelta(days=75),now,recent)
        valid=[r for r in rows if r.get('speed') is not None and 0<r['speed']<5000]
        if not valid:raise ValueError('OMNI window contains no valid speed hours')
        daily=daily_truth(rows)
        coverage=[]
        for offset in range(7):
            target=now.date()+timedelta(days=offset);analog=target-timedelta(days=27)
            day=daily.get(str(analog),{})
            coverage.append({'validDate':str(target),'analogDate':str(analog),
                             'validHours':day.get('hours',0),'speed':day.get('speed')})
        health={'ok':True,'state':'complete','generatedAt':iso(now),'rows':len(rows),
                'validSpeedHours':len(valid),'firstValidHour':valid[0]['time_tag'],
                'lastValidHour':valid[-1]['time_tag'],'minimumDailyHours':18,'forecastDays':coverage}
        manifest=json.loads((recent/'omni-manifest.json').read_text())
        dump(output/'recurrence.json',{'schemaVersion':'chhss-recurrence-1','generatedAt':iso(now),
             'source':'NASA OMNI2 retrospective hourly','coverage':health,'provenance':manifest,'rows':rows})
        status.update(recurrence=health,recurrenceRows=len(rows))
    except Exception as e:
        status.update(recurrence={'ok':False,'state':'failed','error':str(e)},recurrenceError=str(e))
    dump(output/'status.json',status)
    try:
        pack=make_pack(acq);dump(output/'current.json',pack);stamp=pack['observationTime'].replace(':','').replace('-','')
        dump(output/'live-ledger'/f'{stamp}.json',{'observationTime':pack['observationTime'],'availableAt':pack['availableAt'],'maskId':pack['maskId'],'windows':pack['measured']['window'],'polarity':pack['polarity']['sector'],'methodVersion':VERSION,'kind':'forward-collected measurement, not an issued human forecast'})
        status.update(measurement={'ok':True,'state':'complete'},observationTime=pack['observationTime'],maskId=pack['maskId'],degraded=pack['polarity']['degraded'],qualityFlags=pack['polarity']['qualityFlags'],perCore={k:v['polarity'] for k,v in pack['polarity']['sector'].items()})
    except Exception as e:status.update(measurement={'ok':False,'state':'failed','error':str(e)},error=str(e),trace=traceback.format_exc())
    status['ok']=status['measurement']['ok'] and status['recurrence']['ok']
    status['finishedAt']=iso(datetime.now(UTC));dump(output/'status.json',status);print(json.dumps(status),flush=True);return status['ok']

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['backfill']);p.add_argument('--output',type=Path,default=Path('chhss-data'));p.add_argument('--cache',type=Path,default=Path('.chhss-cache'));p.add_argument('--start',default='2026-09-01');p.add_argument('--end',default='2026-09-08');p.add_argument('--max-days',type=int);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True);acq=Acquire(a.cache)
    start,end=date(a.start),date(a.end)
    if not date('2010-05-01') <= start < end <= datetime.now(UTC):
        p.error('Invalid archive range; end is exclusive and cannot be in the future')
    backfill(acq,start,end,a.output,a.max_days)
if __name__=='__main__':main()

# CHHSS_QA_UPGRADE_1
