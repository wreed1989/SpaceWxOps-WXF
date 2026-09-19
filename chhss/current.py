"""Coronal Hole / HSS Outlook: actual numeric AIA/HMI -> registered browser feed.

This module does NOT claim to implement CHIMERA or SPoCA. Its automatic AIA193
candidate segmentation is versioned and explicitly requires detector validation.
The signed-field statistics are measured inside that exact mask, not inferred
from solar wind, colored imagery, an active region or a disk-wide average.
"""
from __future__ import annotations
import argparse,base64,hashlib,io,json,re,sys
from datetime import datetime,timedelta,timezone
from pathlib import Path
import numpy as np
from scipy import ndimage
from acquire import retrieve,info,directory,write,now
UTC=timezone.utc
ENGINE='aia193-radial-contrast-candidates-wcs-v1'
CORES={'E':(-40.,-20.),'M':(-10.,10.),'W':(20.,40.)}

def obs_time(meta):
    from astropy.time import Time
    s=str(meta.get('T_OBS',meta.get('t_obs','')))
    if s.endswith('_TAI'):
        return Time(s[:-4].replace('.','-',2).replace('_','T'),scale='tai').utc.to_datetime(timezone=UTC)
    s=str(meta.get('DATE-OBS',meta.get('date-obs',meta.get('DATE_OBS','')))).replace('Z','')
    if not s:raise ValueError('Actual observation time is absent')
    return Time(s,scale='utc').to_datetime(timezone=UTC)

def quality(meta,instrument):
    raw=meta.get('QUALITY',meta.get('quality'))
    if raw is None:raise ValueError(instrument+': QUALITY missing')
    q=int(raw,0) if isinstance(raw,str) and raw.lower().startswith('0x') else int(raw)
    # The sole HMI warning admitted is documented QUAL_NOCOSMICRAY. All eclipse,
    # limb-fit, missing-frame, ISS and unrecognized bits fail closed.
    allowed=0x400 if instrument=='HMI' else 0x40000000
    if q & ~allowed:raise ValueError(f'{instrument}: unapproved QUALITY bits {q:#010x}')
    return {'value':q,'allowedMask':allowed,'warning':'Some level-1 cosmic-ray lists unavailable; spatial outlier screening applied; NRT provisional' if instrument=='HMI' and q else 'Near-real-time product; definitive calibration may differ' if q else ''}

def native_map(path,metadata=None):
    from astropy.io import fits
    import sunpy.map
    with fits.open(path) as hdus:
        h=next(h for h in hdus if h.data is not None and h.data.ndim==2)
        # Astropy applies the segment BSCALE exactly once. Never copy BSCALE to
        # the physical-value Map or multiply by the API bscales again.
        data=np.asarray(h.data,dtype=np.float32);meta=dict(h.header)
    if metadata:
        for k,v in metadata.items():
            if k in ['BSCALE','BZERO','BLANK','SIMPLE','BITPIX','NAXIS','NAXIS1','NAXIS2'] or v in ['MISSING','',None]:continue
            try:v=float(v) if '.' in str(v) or 'e' in str(v).lower() else int(v)
            except (ValueError,TypeError):pass
            meta[k]=v
    for k in ['BSCALE','BZERO','BLANK']:meta.pop(k,None)
    t=obs_time(meta);meta['DATE-OBS']=t.isoformat().replace('+00:00','Z');meta['DATE_OBS']=meta['DATE-OBS']
    keys=['CTYPE1','CTYPE2','CRPIX1','CRPIX2','CDELT1','CDELT2','DSUN_OBS','RSUN_OBS']
    if any(k not in meta for k in keys):raise ValueError('Incomplete science WCS: '+str([k for k in keys if k not in meta]))
    if not (all(k in meta for k in ['HGLN_OBS','HGLT_OBS']) or all(k in meta for k in ['CRLN_OBS','CRLT_OBS'])):raise ValueError('Observer coordinates absent')
    return sunpy.map.Map(data,meta),t

def nearest_aia(t,cache,channel='0193'):
    # The JSOC README specifies year/month/day/hour hierarchy. List the actual
    # directory; never synthesize a filename and treat its request time as truth.
    candidates=[]
    for hour in [t.replace(minute=0,second=0,microsecond=0),t.replace(minute=0,second=0,microsecond=0)-timedelta(hours=1),t.replace(minute=0,second=0,microsecond=0)+timedelta(hours=1)]:
        url='https://jsoc1.stanford.edu/data/aia/synoptic/nrt/'+hour.strftime('%Y/%m/%d/H%H00/')
        try:links=directory(url)
        except Exception:
            # Older/newer servers can expose HH instead of HHH00; discover the
            # hour path from the dated parent rather than guessing file content.
            parent='https://jsoc1.stanford.edu/data/aia/synoptic/nrt/'+hour.strftime('%Y/%m/%d/')
            dirs=directory(parent);wanted=[u for u in dirs if re.search(r'(?:H)?'+hour.strftime('%H')+r'(?:00)?/$',u)]
            links=directory(wanted[0]) if wanted else []
        for url in links:
            name=url.rsplit('/',1)[-1]
            if channel not in name or not name.endswith('.fits'):continue
            m=re.search(r'(\d{8})[_T](\d{6})',name)
            if not m:continue
            dt=datetime.strptime(''.join(m.groups()),'%Y%m%d%H%M%S').replace(tzinfo=UTC)
            if abs((dt-t).total_seconds())<=1800:candidates.append((abs((dt-t).total_seconds()),url))
        if candidates and min(c[0] for c in candidates)<240:break
    if not candidates:raise ValueError('No co-timed AIA FITS within 30 minutes of signed HMI observation')
    for _,url in sorted(candidates)[:3]:
        try:
            path=cache/url.rsplit('/',1)[-1];retrieve(url,path);m,at=native_map(path)
            if abs((at-t).total_seconds())>1800:continue
            return m,at,json.loads(Path(str(path)+'.source.json').read_text()),path
        except Exception:continue
    raise ValueError('AIA candidates failed timestamp/FITS checks')

def acquire(cache):
    cache.mkdir(parents=True,exist_ok=True);failures=[]
    for series in ['hmi.M_720s_nrt','hmi.M_45s','hmi.M_720s']:
        try:
            data,url=info(series,allkeys=True);meta={k['name']:k['values'][0] for k in data['keywords']};ht=obs_time(meta)
            if not -300<=(datetime.now(UTC)-ht).total_seconds()<=21600:raise ValueError('HMI observation is stale or future-dated')
            q=quality(meta,'HMI');seg=next(s for s in data['segments'] if s['name']=='magnetogram');part=seg['values'][0]
            if not part.startswith('/SUM') or not part.endswith('.fits'):raise ValueError('HMI numeric segment is not online')
            path=cache/('hmi_'+ht.strftime('%Y%m%dT%H%M%S')+'.fits')
            source=None
            for host in ['https://jsoc1.stanford.edu','http://jsoc.stanford.edu']:
                try:retrieve(host+part,path);source=host+part;break
                except Exception as e:failures.append(str(e))
            if not source:raise ValueError('Unable to download signed HMI segment')
            hm,ht=native_map(path,meta);write(cache/'hmi_metadata.json',{'series':series,'api':url,'keywords':meta})
            am,at,ap,af=nearest_aia(ht,cache)
            aq=quality(dict(am.meta),'AIA');hp=json.loads(Path(str(path)+'.source.json').read_text())
            return am,hm,at,ht,{'euv':ap,'hmi':{**hp,'series':series,'metadataUrl':url,'metadataSHA256':hashlib.sha256(json.dumps(meta,sort_keys=True).encode()).hexdigest()},'inputQuality':{'aia':aq,'hmi':q},'priorSourceFailures':failures}
        except Exception as e:failures.append(series+': '+str(e))
    raise RuntimeError('; '.join(failures))

def candidates(intensity,valid,rho,pixel_arcsec):
    """Conservative versioned dark-region candidates, not a validated CH classifier.
    Correct a radial median profile, retain <0.55 of the interior median,
    open/close at one output pixel and discard <3000 projected arcsec^2.
    Magnetic sign is independently calculated; ambiguous regions are retained
    as candidates rather than silently reclassified as quiet Sun.
    """
    d=np.asarray(intensity,dtype=float);smooth=ndimage.median_filter(np.nan_to_num(d,nan=0.),size=3)
    qs=np.median(smooth[valid&(rho<.7)])
    if not np.isfinite(qs) or qs<=0:raise ValueError('No positive quiet-Sun reference intensity')
    edges=np.linspace(0,1,41);centers=(edges[:-1]+edges[1:])/2
    med=np.array([np.median(smooth[valid&(rho>=a)&(rho<b)]) if np.sum(valid&(rho>=a)&(rho<b))>=100 else qs for a,b in zip(edges[:-1],edges[1:])])
    trend=ndimage.median_filter(med,size=5);correction=np.clip(np.interp(rho,centers,trend)/qs,.7,2.5)
    contrast=smooth/np.maximum(correction*qs,1e-6)
    seed=valid&(contrast<.55)&(smooth>0)
    seed=ndimage.binary_closing(ndimage.binary_opening(seed,iterations=1),iterations=1)&valid
    labels,n=ndimage.label(seed);sizes=np.bincount(labels.ravel());cut=max(16,int(np.ceil(3000/(pixel_arcsec*pixel_arcsec))));keep=np.flatnonzero(sizes>=cut);keep=keep[keep!=0]
    mask=np.isin(labels,keep)&valid
    if mask.sum()/max(1,valid.sum())>.45:raise ValueError('Candidate mask exceeds 45% of valid disk; segmentation withheld')
    return mask,{'method':ENGINE,'quietSunReferenceDN':float(qs),'contrastThreshold':.55,'minimumAreaArcsec2':3000,'candidateRegions':len(keep),'scope':'Automatic EUV candidates; not reviewed, not CHIMERA/SPoCA; detector validation pending'}

def build(am,hm,at,ht,provenance,size=512,mask_map=None,historical=False):
    import astropy.units as u
    from astropy.coordinates import SkyCoord
    import sunpy.map
    from sunpy.coordinates import frames,propagate_with_solar_surface
    from PIL import Image
    if abs((at-ht).total_seconds())>1800:raise ValueError('AIA/HMI pairing exceeds 30 minutes')
    if 'AIA' not in str(am.instrument).upper() or abs(am.wavelength.to_value(u.angstrom)-193)>1:raise ValueError('Input is not numeric AIA 193')
    if 'HMI' not in str(hm.instrument).upper() or not hm.unit or not hm.unit.is_equivalent(u.G):raise ValueError('Input is not signed HMI magnetic flux density')
    target=am.rotate(recenter=True).resample(u.Quantity([size,size],u.pix))
    if not np.allclose(target.rotation_matrix,np.eye(2),atol=1e-5):raise ValueError('Target must be solar-north-up')
    coordinates=sunpy.map.all_coordinates_from_map(target);hgs=coordinates.transform_to(frames.HeliographicStonyhurst(obstime=target.date))
    lat=hgs.lat.to_value(u.deg);cmd=(hgs.lon-target.observer_coordinate.lon).wrap_at(180*u.deg).to_value(u.deg)
    center=target.world_to_pixel(SkyCoord(0*u.arcsec,0*u.arcsec,frame=target.coordinate_frame));cx=float(center.x.value);cy=float(center.y.value)
    ps=target.scale.axis1.to_value(u.arcsec/u.pix);radius=float(target.rsun_obs.to_value(u.arcsec)/ps)
    yy,xx=np.indices(target.data.shape);rho=np.hypot(xx-cx,yy-cy)/radius
    geometrical=np.isfinite(lat)&np.isfinite(cmd)&(rho<=.97);valid=geometrical&np.isfinite(target.data)
    if valid.sum()/max(1,geometrical.sum())<.98:raise ValueError('Insufficient AIA science-disk coverage')
    if mask_map is None:mask,segqa=candidates(target.data,valid,rho,ps)
    else:
        with propagate_with_solar_surface():mm,fp=mask_map.reproject_to(target.wcs,order='nearest-neighbor',return_footprint=True)
        mask=(mm.data>0)&valid&(fp>=.99);segqa={'method':'ROB published SPoCA mask','scope':'Retrospective catalogue mask; independent of live candidate detector'}
    core=np.zeros(mask.shape,np.uint8);windows={}
    for i,(k,(lo,hi)) in enumerate(CORES.items(),1):
        reg=valid&(cmd>=lo)&(cmd<=hi);core[reg]=i;sel=mask&reg;n=int(reg.sum());count=int(sel.sum())
        if n<100:raise ValueError('Insufficient valid core coverage')
        windows[k]={'A':count/n,'disk':n,'ch':count,'centroidLat':float(np.mean(lat[sel])) if count else None,'centroidCmd':float(np.mean(cmd[sel])) if count else None}
    # Reproject from the NATIVE signed HMI grid, including its ~180 degree
    # roll, observer and differential-rotation/time transform. Equal image sizes
    # or sampled JPEG luminance are never used for registration or sign.
    raw=np.asarray(hm.data,dtype=float)*hm.unit.to(u.G)
    bad=~np.isfinite(raw)|(np.abs(raw)>5000)
    clipped=np.where(bad,np.nan,raw)
    hmap=sunpy.map.Map(clipped,hm.meta)
    with propagate_with_solar_surface():registered,footprint=hmap.reproject_to(target.wcs,order='bilinear',return_footprint=True)
    field=np.asarray(registered.data,dtype=float)
    # Median filter only gross isolated outliers. Preserve the physical gauss
    # scale and sign; record the number excluded rather than hiding clipping.
    local=ndimage.median_filter(np.nan_to_num(field,nan=0),size=3)
    outlier=np.isfinite(field)&(np.abs(field-local)>300)&(np.abs(field)>500)
    field[outlier]=np.nan
    b0=target.observer_coordinate.lat.to_value(u.rad);la=np.radians(lat);lo=np.radians(cmd)
    cosc=np.sin(la)*np.sin(b0)+np.cos(la)*np.cos(b0)*np.cos(lo);ds=target.dsun.to_value(u.m);rs=target.rsun_meters.to_value(u.m)
    mu=(ds*cosc-rs)/np.sqrt(ds*ds+rs*rs-2*ds*rs*cosc)
    sectors={}
    for i,k in enumerate(CORES,1):
        reg=mask&(core==i);total=int(reg.sum());ok=reg&np.isfinite(field)&(mu>=.4)&(footprint>=.99);n=int(ok.sum());cov=n/total if total else 0
        if n:
            br=field[ok]/mu[ok];weights=1/mu[ok];signed=float(np.sum(br*weights));unsigned=float(np.sum(np.abs(br)*weights));imb=signed/unsigned if unsigned else 0;mean=float(np.average(br,weights=weights));median=float(np.median(br))
        else:imb=0.;mean=median=None
        accept=n>=100 and cov>=.8 and abs(imb)>=.15 and mean is not None and abs(mean)>=1 and np.sign(mean)==np.sign(imb)
        sectors[k]={'coreDefinition':'20deg-hgs','polarity':int(np.sign(imb)) if accept else None,'fluxImbalance':imb,'meanBr':mean,'medianBr':median,'nValid':n,'nMasked':total,'validMaskedPixelFraction':cov,'quality':'signed-field QA; detector unvalidated' if accept else 'mixed/weak/insufficient','thresholds':{'minPixels':100,'minCoverage':.8,'minImbalance':.15,'minMeanBrG':1,'minMu':.4}}
    raster=np.flipud(mask).astype(np.uint8);maskid=hashlib.sha256(raster.tobytes()).hexdigest();labels=np.flipud(core)
    data=np.maximum(np.asarray(target.data),0);pool=data[valid];low,high=np.percentile(pool,[1,99.7]);norm=np.clip((np.log1p(data)-np.log1p(low))/max(1e-6,np.log1p(high)-np.log1p(low)),0,1);norm=np.nan_to_num(norm)
    rgb=np.stack([norm**.55,norm**1.1*.80,norm**2*.28],axis=-1);rgb=np.flipud((rgb*255).astype(np.uint8));bio=io.BytesIO();Image.fromarray(rgb).save(bio,format='PNG')
    atiso=at.isoformat().replace('+00:00','Z');htiso=ht.isoformat().replace('+00:00','Z');generated=now()
    polarity={'schemaVersion':'chhss-polarity-1','source':'JSOC HMI signed LOS FITS; registered to AIA mask','quantity':'B_R','units':'G','radialApproximation':'B_LOS/mu, area-weighted; not a measured vector field','registrationQuality':'wcs-reprojected','maskId':maskid,'observationTime':htiso,'euvObservationTime':atiso,'muMin':.4,'sector':sectors,'screenedOutlierPixels':int(outlier.sum())}
    pack={'schemaVersion':'chhss-science-1','observationTime':atiso,'availableAt':generated,'generatedAt':generated,'historical':historical,'measurementEngine':ENGINE if mask_map is None else 'spoca-mask-native-hmi-wcs-v1','maskId':maskid,'source':{'instrument':'AIA193',**provenance,'mask':segqa},'preview':{'url':'data:image/png;base64,'+base64.b64encode(bio.getvalue()).decode(),'role':'Exact unannotated measurement raster; display stretch never changes analysis'},'measured':{'ok':True,'width':size,'height':size,'cx':cx,'cy':size-1-cy,'radius':radius,'scienceRadius':.97*radius,'imageProduct':'aia193','geometry':{'registration':'wcs','northUp':True,'b0Deg':float(np.degrees(b0)),'sourceWCSHeader':target.wcs.to_header_string(),'limbRadiusPx':radius},'mask':raster.ravel().tolist(),'coreLabels':labels.ravel().tolist(),'window':windows,'sector':{},'contours':[]},'polarity':polarity,'qualification':{'operationallyValidated':False,'detector':'Automatic candidates; manual interpretation required','magneticField':'Measured signed HMI; quantitative per-core QA; NRT warning retained','forecast':'Core-area relation not promoted by successful ingestion'},'notes':['Positive denotes outward radial-field approximation; negative inward. No polarity-to-Bz forecast is made.','The historical SPoCA archive and this live candidate detector are different measurement populations; archive skill is not live-detector certification.','Weak/mixed/no-hole cores remain unknown, not zero or inherited from another core.']}
    return pack

def run(out,cache,size=512):
    out.mkdir(parents=True,exist_ok=True)
    try:
        am,hm,at,ht,p=acquire(cache);pack=build(am,hm,at,ht,p,size)
        write(out/'current.json',pack)
        short={'schemaVersion':'chhss-health-1','checkedAt':now(),'status':'current','observationTime':pack['observationTime'],'hmiTime':pack['polarity']['observationTime'],'maskId':pack['maskId'],'polarity':{k:v['polarity'] for k,v in pack['polarity']['sector'].items()},'inputQuality':p['inputQuality'],'operationallyValidated':False,'message':'Numeric AIA/HMI processing succeeded; automatic CH candidates and forecasts still require validation'}
        write(out/'health.json',short)
        # Immutable forward snapshots are real issue-time records, unlike a
        # reconstructed historical issue. No user identity or internal data.
        key=pack['observationTime'].replace('-','').replace(':','').replace('.','_')
        f=out/'forward'/('obs_'+key+'.json')
        if not f.exists():write(f,{'observationTime':pack['observationTime'],'issuedAt':pack['availableAt'],'maskId':pack['maskId'],'measurementVersion':ENGINE,'windows':pack['measured']['window'],'polarity':pack['polarity']['sector'],'qualification':pack['qualification']})
        print(json.dumps(short),flush=True);return pack
    except Exception as e:
        # Never overwrite a last good measurement with made-up or empty data.
        # Browser uses actual observation-time TTL even if last good stays here.
        write(out/'health.json',{'schemaVersion':'chhss-health-1','checkedAt':now(),'status':'failed','error':str(e),'lastGoodRetained':(out/'current.json').exists(),'operationallyValidated':False});raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=Path('chhss-data'));p.add_argument('--cache',type=Path,default=Path('.cache/chhss-current'));p.add_argument('--size',type=int,default=512);a=p.parse_args()
    if not 128<=a.size<=1024:raise ValueError('Size outside permitted bounds')
    try:run(a.out,a.cache,a.size)
    except Exception as e:print('ERROR: '+str(e),file=sys.stderr);sys.exit(1)
