"""Scientific input acquisition for Coronal Hole / HSS Outlook.
Public data only. HTTP is used only for JSOC's documented legacy API; no secrets.
No image brightness is interpreted as a signed magnetic measurement.
"""
from __future__ import annotations
import argparse, concurrent.futures, hashlib, json, re, time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urlencode, urljoin
import requests
UTC=timezone.utc

def now(): return datetime.now(UTC).isoformat().replace('+00:00','Z')
def write(path,obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(obj,indent=2,allow_nan=False,default=str));tmp.replace(path)

def retrieve(url,path=None,timeout=75,refresh=False):
    path=Path(path) if path else None
    if path and path.is_file() and not refresh:return path.read_bytes()
    error=None
    for attempt in range(3):
        try:
            r=requests.get(url,timeout=(12,timeout),headers={'User-Agent':'CHHSS-Outlook/1.0 (public scientific data; sequential cached processing)'})
            r.raise_for_status();data=r.content
            if len(data)>220*1024*1024:raise ValueError('Source exceeds download size limit')
            if path:
                path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix(path.suffix+'.part');tmp.write_bytes(data);tmp.replace(path)
                write(str(path)+'.source.json',{'url':url,'retrievedAt':now(),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'contentType':r.headers.get('Content-Type'),'transport':url.split(':')[0]})
            return data
        except Exception as exc:
            error=exc
            if isinstance(exc,requests.HTTPError) and exc.response.status_code in (400,401,403,404):break
            if attempt<2:time.sleep(2**attempt)
    raise RuntimeError(f'{url}: {error}')

def tap(query,cache=None):
    url='https://vo-tap.oma.be/tap/sync?'+urlencode(dict(REQUEST='doQuery',LANG='ADQL',FORMAT='json',QUERY=query,MAXREC=20000))
    data=json.loads(retrieve(url,cache));cols=data.get('columns',data.get('metadata',[]));names=[c['name'] for c in cols]
    if not names or 'data' not in data:raise ValueError('TAP did not return a table')
    if len(data['data'])>=20000:raise ValueError('TAP row limit reached: subdivide query')
    return [dict(zip(names,r)) for r in data['data']]

def directory(url):
    text=retrieve(url,timeout=25).decode('utf8','replace')
    return sorted(set(urljoin(url,n) for n in re.findall(r'href=[\"\']([^\"\'?#]+)[\"\']',text) if not n.startswith('../')))

def info(series,when='$',allkeys=False):
    # JSOC supports public GET through its documented legacy endpoint.
    params={'op':'rs_list','ds':series+'['+when+']','key':'**ALL**' if allkeys else 'T_REC,T_OBS,DATE-OBS,QUALITY,INSTRUME,BUNIT','seg':'magnetogram'}
    url='http://jsoc.stanford.edu/cgi-bin/ajax/jsoc_info?'+urlencode(params)
    data=json.loads(retrieve(url,timeout=45))
    if data.get('status',0)!=0:raise ValueError(data.get('error',data))
    return data,url

def discover(out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True);report={}
    def one(series):
        try:
            data,url=info(series,allkeys=True);write(out/(series+'.json'),data)
            return series,{'ok':True,'url':url,'count':data.get('count'),'segments':data.get('segments'),'keywords':{k['name']:k.get('values') for k in data.get('keywords',[]) if k['name'] in ['T_REC','T_OBS','DATE-OBS','QUALITY','BUNIT','INSTRUME','DATASIGN']}}
        except Exception as e:return series,{'ok':False,'error':str(e)}
    report.update(dict(concurrent.futures.ThreadPoolExecutor(3).map(one,['hmi.M_45s','hmi.M_720s','hmi.M_720s_nrt'])))
    for key,url in {'aia-mostrecent':'https://jsoc1.stanford.edu/data/aia/synoptic/mostrecent/','aia-nrt':'https://jsoc1.stanford.edu/data/aia/synoptic/nrt/','hmi-latest':'https://jsoc1.stanford.edu/data/hmi/images/latest/','oma-hmi1':'https://sdo.oma.be/data/hmi_science_level1/magnetogram/'}.items():
        try:
            links=directory(url);report[key]={'url':url,'links':links}
            if key=='aia-mostrecent':
                candidates=[u for u in links if re.search(r'0193.*\.fits(?:\.gz)?$',u)]
                if candidates:retrieve(candidates[-1],out/'current-aia.fits')
        except Exception as e:report[key]={'error':str(e)}
    params=dict(cosec=2,cmd='search',type='column',event_type='ch',event_starttime=(datetime.now(UTC)-timedelta(days=2)).strftime('%Y-%m-%dT%H:%M:%S'),event_endtime=datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%S'),event_coordsys='helioprojective',x1=-1200,x2=1200,y1=-1200,y2=1200,result_limit=100,showtests='hide')
    try:
        u='https://www.lmsal.com/hek/her?'+urlencode(params);d=json.loads(retrieve(u,out/'hek.json'));report['hek']={'rows':len(d.get('result',[])),'overmax':d.get('overmax')}
    except Exception as e:report['hek']={'error':str(e)}
    # Download only a valid public segment, not a latest-image PNG or an arbitrary path.
    for series in ['hmi.M_720s_nrt','hmi.M_45s','hmi.M_720s']:
        if not report.get(series,{}).get('ok'):continue
        try:
            data=json.loads((out/(series+'.json')).read_text());seg=next(s for s in data.get('segments',[]) if s['name']=='magnetogram');path=seg['values'][0]
            if not path.startswith('/') or not path.endswith('.fits'):raise ValueError('No online FITS segment')
            for host in ['https://jsoc1.stanford.edu','http://jsoc.stanford.edu']:
                try:retrieve(host+path,out/'current-hmi.fits');report['hmi-download']={'series':series,'url':host+path};break
                except Exception as e:report['hmi-download']={'error':str(e)}
            if (out/'current-hmi.fits').exists():break
        except Exception as e:report['hmi-download']={'error':str(e)}
    write(out/'discovery.json',report);print(json.dumps(report,default=str),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--discover',type=Path,required=True);a=p.parse_args();discover(a.discover)
