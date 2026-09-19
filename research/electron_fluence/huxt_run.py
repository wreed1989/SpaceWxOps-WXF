"""Run HUXt at Earth with SWPC's actual inner boundary and issued DONKI cones.

Only imports HUXt's numerical core. No notebook, demonstration wind, or inferred
Bz is used. This forward-run series is archived context pending paired hindcasts.
"""
import argparse
import copy
import hashlib
import io
import json
import os
import re
import tarfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin

import numpy as np
import pandas as pd
import requests

NOMADS='https://nomads.ncep.noaa.gov/pub/data/nccf/com/wsa_enlil/prod/'
DONKI='https://kauai.ccmc.gsfc.nasa.gov/DONKI/WS/get/CMEAnalysis'
HUXT_COMMIT='4d5b60bedb4b30ad140a8ea4972c4f5396c687ff'


def fetch_inputs(cache, now):
    cache=Path(cache);cache.mkdir(parents=True,exist_ok=True)
    r=requests.get(NOMADS,timeout=45);r.raise_for_status()
    folders=sorted(set(re.findall(r'href="(wsa_enlil\.\d{8}/)"',r.text)),reverse=True)
    selected=None
    for folder in folders[:3]:
        stamp=pd.Timestamp(folder[10:18],tz='UTC')
        if stamp>now or now-stamp>pd.Timedelta(days=4):continue
        index=requests.get(urljoin(NOMADS,folder),timeout=45);index.raise_for_status()
        # Background run only: CME injections in a boundary would double-count cones.
        links=re.findall(r'href="([^"]+)"',index.text)
        filename='wsa_enlil.mrid00000000.inputs.tar.gz'
        if filename not in links:continue
        url=urljoin(index.url,filename);payload=requests.get(url,timeout=90);payload.raise_for_status()
        path=cache/'swpc-ambient-inputs.tar.gz';path.write_bytes(payload.content)
        selected={'url':url,'sha256':hashlib.sha256(payload.content).hexdigest(),
                  'retrievedAt':datetime.now(timezone.utc).isoformat(),'path':str(path)}
        break
    if selected is None:raise ValueError('No recent SWPC ambient boundary archive')
    params={'startDate':(now-pd.Timedelta(days=8)).strftime('%Y-%m-%d'),
            'endDate':now.strftime('%Y-%m-%d'),'mostAccurateOnly':'true','catalog':'M2M_CATALOG','feature':'LE'}
    r=requests.get(DONKI,params=params,timeout=60);r.raise_for_status()
    path=cache/'donki-cones.json';path.write_bytes(r.content)
    cmes=r.json() or []
    if not isinstance(cmes,list):raise ValueError('Invalid DONKI CME analysis response')
    meta={'url':r.url,'sha256':hashlib.sha256(r.content).hexdigest(),'retrievedAt':datetime.now(timezone.utc).isoformat()}
    return selected,cmes,meta


def boundary(path, latitude, issue):
    from scipy.io import netcdf_file
    from astropy.time import Time
    from astropy import units as u
    from sunpy.coordinates import sun
    with tarfile.open(path) as tar:
        member=tar.getmember('bnd.nc')
        if member.size>20_000_000:raise ValueError('Unexpected boundary file size')
        raw=tar.extractfile(member).read() # Never extract archive-controlled paths.
    with netcdf_file(io.BytesIO(raw),mmap=False) as nc:
        decode=lambda x:x.decode() if isinstance(x,bytes) else str(x)
        if decode(nc.coordinates)!='HEEQ+180' or decode(nc.rotation)!='synodic':
            raise ValueError('Unsupported boundary coordinates')
        speed=np.array(nc.variables['V1'].data,dtype=float)
        if speed.shape[:2]!=(1,1):raise ValueError('Expected a single ambient boundary')
        lon=np.array(nc.variables['X3'].data[0],dtype=float)
        lat=np.pi/2-np.array(nc.variables['X2'].data[0],dtype=float)
        epoch=pd.Timestamp(decode(nc.rundate_cal),tz='UTC')+pd.Timedelta(seconds=float(nc.variables['TIME'].data[0]))
        created=pd.Timestamp(decode(nc.creation),tz='UTC')
        if created>issue or epoch>issue or issue-epoch>pd.Timedelta(hours=72):
            raise ValueError('SWPC boundary is future-dated or older than 72 hours')
        r=float(nc.rbnd)/695700000. # rbnd in metres; solar radius in metres.
        if not 20<r<23:raise ValueError('Unexpected SWPC inner-boundary radius')
        # V1 is SI m/s in Enlil's bnd.nc, rather than the raw WSA terminal-speed map.
        speed=speed[0,0]/1000
        if not np.isfinite(speed).all() or np.min(speed)<100 or np.max(speed)>3000:raise ValueError('Invalid boundary speeds')
        order=np.argsort(lat)
        profile=np.array([np.interp(latitude,lat[order],row[order]) for row in speed])
        cr=float(sun.carrington_rotation_number(Time(epoch.floor('us').to_pydatetime())))
        earth_carr=2*np.pi*(1-(cr%1))
        carr=(lon-np.pi+earth_carr)%(2*np.pi)
        grid=(np.arange(128)+.5)*2*np.pi/128
        v=np.interp(grid,carr,profile,period=2*np.pi)
        return v*u.km/u.s,r*u.solRad,{'boundaryEpoch':epoch.isoformat(),'createdAt':created.isoformat(),
            'radiusSolarRadii':r,'coordinateTransform':'HEEQ+180 to Carrington at boundary TIME + rundate',
            'latitudeDegrees':float(np.degrees(latitude)),'speedMin':float(v.min()),'speedMax':float(v.max()),
            'sha256':hashlib.sha256(raw).hexdigest()}


def selected_cones(rows, issue, start):
    latest={}
    for r in rows:
        try:
            submitted=pd.Timestamp(r['submissionTime']);launch=pd.Timestamp(r['time21_5']);ident=r['associatedCMEID']
            if submitted.tzinfo is None or launch.tzinfo is None or submitted>issue or not start<=launch<=issue+pd.Timedelta(days=2):continue
            speed=float(r['speed']);width=float(r['halfAngle']);lat=float(r['latitude']);lon=float(r['longitude'])
            if not (100<=speed<=3500 and 0<width<90 and -90<=lat<=90 and -360<=lon<=360):continue
            v={'id':ident,'submittedAt':submitted.isoformat(),'launchAt21_5':launch.isoformat(),
                'speed':speed,'halfAngle':width,'latitude':lat,'longitude':lon,'source':r.get('link')}
            if ident not in latest or submitted>pd.Timestamp(latest[ident]['submittedAt']):latest[ident]=v
        except (ValueError,KeyError,TypeError):continue
    return sorted(latest.values(),key=lambda r:r['launchAt21_5'])


def run(cache, output, issue=None):
    cache=Path(cache).resolve();cache.mkdir(parents=True,exist_ok=True)
    os.environ.setdefault('SUNPY_CONFIGDIR',str(cache/'sunpy-config'))
    os.environ.setdefault('SUNPY_DOWNLOADDIR',str(cache/'sunpy-download'))
    (cache/'cache').mkdir(exist_ok=True)
    os.environ.setdefault('XDG_CACHE_HOME',str(cache/'cache'))
    if __package__:
        from .vendor.huxt import huxt as H
    else:
        from vendor.huxt import huxt as H
    from astropy.time import Time
    from astropy import units as u
    from sunpy.coordinates import sun
    cache=Path(cache).resolve();cache.mkdir(parents=True,exist_ok=True)
    # Use the task/run cache rather than creating an application-support directory.
    H.user_data_dir=lambda **kwargs:str(cache/'runtime')
    now=pd.Timestamp.now(tz='UTC') if issue is None else pd.Timestamp(issue)
    source,rows,cme_source=fetch_inputs(cache,now)
    start=now.floor('h')-pd.Timedelta(days=7)
    earth=H.Observer('Earth',Time([now.to_pydatetime()]))
    latitude=float(earth.lat.to_value(u.rad)[0])
    v,rmin,meta=boundary(source['path'],latitude,now)
    selected=selected_cones(rows,now,start)
    cr=float(sun.carrington_rotation_number(Time(start.to_pydatetime())))
    kwargs={'v_boundary':v,'cr_num':int(np.floor(cr)),'cr_lon_init':(360*(1-(cr%1)))*u.deg,
        'latitude':latitude*u.rad,'r_min':rmin,'r_max':240*u.solRad,'lon_out':0*u.rad,
        'simtime':12*u.day,'dt_scale':4,'frame':'synodic'}
    ambient=H.HUXt(**kwargs);ambient.solve([])
    model=H.HUXt(**kwargs)
    cones=[H.ConeCME(t_launch=((pd.Timestamp(c['launchAt21_5'])-start).total_seconds()+(rmin.to_value(u.solRad)-21.5)*695700/c['speed'])*u.s,
        longitude=c['longitude']*u.deg,latitude=c['latitude']*u.deg,width=2*c['halfAngle']*u.deg,
        v=c['speed']*u.km/u.s,initial_height=rmin,thickness=0*u.solRad,
        label=c['id']) for c in selected]
    model.solve(cones)
    observer=model.get_observer('Earth');times=model.time_init+model.time_out
    radius=observer.r.to_value(u.solRad)
    all_rows=[]
    for i,t in enumerate(times):
        ts=pd.Timestamp(t.to_datetime(timezone=timezone.utc))
        # Past output is a current-input reconstruction, never relabelled observation.
        if ts<now-pd.Timedelta(hours=24):continue
        all_rows.append({'time':ts.isoformat(),'ambientSpeed':float(np.interp(radius[i],model.r.value,ambient.v_grid[i,:,0].value)),
            'cmeSpeed':float(np.interp(radius[i],model.r.value,model.v_grid[i,:,0].value)),
            'phase':'forecast' if ts>now else 'reconstruction'})
    if len(all_rows)<100 or not all(0<r['ambientSpeed']<3500 and 0<r['cmeSpeed']<3500 for r in all_rows):
        raise ValueError('HUXt produced invalid/incomplete Earth time series')
    result={'schemaVersion':'wxf-huxt-1','issuedAt':now.isoformat(),'status':'experimental',
        'model':'HUXt 5.0.3','upstreamCommit':HUXT_COMMIT,'source':source,'boundary':meta,
        'cmeSource':cme_source,'cmeInputs':selected,'simulationStart':start.isoformat(),
        'forecastHours':120,'units':'km/s','rows':all_rows,'usedAsElectronModelInput':False,
        'qualification':'Locally run SWPC-boundary/DONKI HUXt. Reduced-physics speed forecast; no Bz, density, or electron response is inferred. Historical paired runs are needed before training it as an electron predictor.',
        'assumptions':['Single Earth-directed longitude at the issue-time Earth heliographic latitude.',
            'Static, recent SWPC ambient inner boundary; no time-dependent CH evolution.',
            'HUXt standard cone implementation: zero added thickness and default fixed 8.5-hour duration.',
            'Pre-issue model output is reconstruction using current inputs, not as-issued historical guidance.']}
    Path(output).parent.mkdir(parents=True,exist_ok=True)
    Path(output).write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    (cache/'issued-run.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--cache',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();r=run(a.cache,a.output);print('HUXt',len(r['rows']),'Earth values,',len(r['cmeInputs']),'DONKI cones')
