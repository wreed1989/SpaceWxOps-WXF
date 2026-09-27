#!/usr/bin/env python3
"""Collect provider payloads without exposing credentials, tokens, or cookies.

This first-stage collector writes to an Actions artifact for schema verification.
Only fixed provider hosts are permitted; authentication is scoped per host.
"""
from __future__ import annotations
import base64, hashlib, html, io, json, os, re, sys
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlencode
import check_access as access

ROOT = Path(os.environ.get('ESA_OUTPUT_DIR', 'esa-products'))
ROOT.mkdir(parents=True, exist_ok=True)
access.MAX_BYTES = 24_000_000
KSO_SCOPE = '387309144d7b0e6251d9f0c63f7c02e6'
access.ALLOWED_SCOPES.add(KSO_SCOPE)
access.AUTH_HOSTS['sso.kso.ac.at'] = KSO_SCOPE
# These are service resource identifiers, not the user's client identifier.
PROXY_AE = 'a-effort-academyofathens-gr.content.swe.s2p.esa.int'
access.AUTH_HOSTS[PROXY_AE] = 'swe_contentproxy'
client = access.M2M(os.environ.get('ESAID', ''), os.environ.get('ESASECRET', ''))
NOW = datetime.now(timezone.utc)
report = {'schema_version': 1, 'collected_at': NOW.isoformat(), 'products': {}, 'requests': []}

class Links(HTMLParser):
    def __init__(self):
        super().__init__(); self.items = []
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ('a', 'img', 'source', 'video', 'script', 'iframe', 'link', 'form'):
            self.items.append({'tag':tag, **{k:v for k,v in a.items() if k in ('href','src','action','id','class','type','name')}})

def label(url):
    u=urlsplit(url)
    return u.scheme+'://'+u.netloc+u.path+('?' + u.query if u.query else '')

def fetch(url, *, authenticate=True):
    """Follow at most three redirects; recompute scope, never forward tokens."""
    for _ in range(4):
        host=urlsplit(url).hostname
        scope=access.AUTH_HOSTS.get(host) if authenticate else None
        r=access.exchange(url,bearer=client.token(scope) if scope else None,scope=scope)
        if r.status in (301,302,303,307,308):
            nxt=urljoin(url,html.unescape(r.headers.get('location','')))
            if urlsplit(nxt).hostname=='sso.s2p.esa.int':
                raise access.SafeError('login_redirect')
            if urlsplit(nxt).hostname not in set(access.AUTH_HOSTS)|access.PUBLIC_HOSTS:
                raise access.SafeError('unapproved_redirect')
            url=nxt; continue
        if r.status != 200:
            raise access.SafeError('http_'+str(r.status))
        return r,url
    raise access.SafeError('too_many_redirects')

def classify(data):
    raw=data.lstrip()
    if raw.startswith(b'\x89PNG\r\n\x1a\n'): return 'png'
    if raw.startswith(b'\xff\xd8\xff'): return 'jpg'
    if raw.startswith((b'GIF87a',b'GIF89a')): return 'gif'
    if len(data)>12 and data[4:8]==b'ftyp': return 'mp4'
    if data.startswith(b'\x1aE\xdf\xa3'): return 'webm'
    text=data.decode('utf-8',errors='replace')
    if re.search(r'<(?:!DOCTYPE\s+html|html)\b',text[:2000],re.I): return 'html'
    if '<svg' in text[:2000]: return 'svg'
    if raw.startswith((b'{',b'[')):
        try: json.loads(data); return 'json'
        except ValueError: pass
    if raw.startswith(b'<'): return 'xml'
    if text.strip().startswith('https://'): return 'url'
    return 'txt'

def save(name,url,expected=None,authenticate=True):
    rec={'source':label(url)}
    try:
        r,final=fetch(url,authenticate=authenticate)
        kind=classify(r.body)
        rec.update({'status':'received','kind':kind,'bytes':len(r.body),'source':label(final)})
        if kind=='html' and any(x in r.body.lower() for x in (b'type="password"',b'id="kc-form-login"')):
            raise access.SafeError('login_page')
        if expected and kind not in expected:
            rec['status']='unexpected_format'
        # Provider pages are diagnostic inputs, not working model products.
        if kind=='html':
            parser=Links();parser.feed(r.body.decode('utf-8',errors='replace'))
            rec['links']=parser.items
        if kind in ('png','jpg','gif'):
            from PIL import Image
            im=Image.open(io.BytesIO(r.body)); im.verify()
            im=Image.open(io.BytesIO(r.body));rec['width'],rec['height']=im.size
        data=r.body
        if kind=='svg':
            if re.search(br'<!ENTITY|<!DOCTYPE[^>]*\[',data,re.I):
                raise access.SafeError('unsafe_xml')
            data=re.sub(br'<!DOCTYPE\s+svg\s+(?:PUBLIC|SYSTEM)\s+[^>]*>',b'',data,flags=re.I)
            import xml.etree.ElementTree as ET
            root=ET.fromstring(data)
            if root.tag.split('}')[-1]!='svg':raise access.SafeError('not_svg')
        filename=name+'.'+kind
        (ROOT/filename).write_bytes(data)
        rec['file']=filename
        if r.headers.get('last-modified'): rec['last_modified']=r.headers['last-modified']
        rec['sha256']=hashlib.sha256(data).hexdigest()
        report['products'][name]=rec
        report['requests'].append({'name':name,'status':rec['status'],'kind':kind})
        return data,rec
    except access.SafeError as e:
        rec['status']=str(e)
    except Exception as e:
        rec['status']='validation_'+type(e).__name__
    report['products'][name]=rec
    report['requests'].append({'name':name,'status':rec['status']})
    return None,rec

def main():
    sidc=access.SIDC
    save('sidc-holes',sidc+'?component=latest&pc=S126&psc=a&type=ch',{'json'})
    save('sidc-runs',sidc+'?component=latest&pc=S126&psc=a&type=run',{'json'})
    save('sidc-flares',sidc+'?component=latest&pc=S109&psc=b',{'xml'})
    flags={'regions_sidc_sunspot':1,'regions_noaa_region':1,'regions_noaa_returning':1,'flares_solardemon':1,'flares_noaa':1,'cmes_cactus':1,'coronal_holes_sidc':1,'filaments_kso':1,'features_grid':1,'features_legend':1}
    for key,image in [('euv','AIA193'),('white','SIDC/USET_WL')]:
        save('solarmap-'+key,sidc+'?'+urlencode({'component':'latest','pc':'S101','psc':'c','images_sun':image,'features_width':1024,**flags}),{'svg'})
    save('solarmap-page','https://esa-swe-services-sidc-be.content.swe.s2p.esa.int/prod/S101c/',{'html'})
    for key,typ,ft in [('normal','nm','jpeg'),('contrast','hc','jpeg'),('color','nm','jpegc'),('clv','nm','jpegfc')]:
        data,rec=save('kso-index-'+key,'https://sso.kso.ac.at/prod/API/index.php?'+urlencode({'component':'latest','pc':'S107','psc':'a','type':typ,'filetype':ft}),{'url','json'})
        if data and rec['kind']=='url':
            candidate=data.decode().strip().strip('"')
            if urlsplit(candidate).hostname=='sso.kso.ac.at':save('kso-'+key,candidate,{'jpg','png'})
    save('kso-archive','https://sso.kso.ac.at/prod/API/index.php?'+urlencode({'component':'archive','pc':'S107','psc':'a','type':'nm','filetype':'jpeg','dts_start':(NOW-timedelta(hours=3)).strftime('%Y-%m-%dT%H:%M:%SZ'),'dts_end':NOW.strftime('%Y-%m-%dT%H:%M:%SZ')}),{'json'})
    save('aeffort','https://'+PROXY_AE+'/prod/api/index.php?component=latest&pc=S124',{'xml'})
    save('aeffort-direct','https://a-effort.academyofathens.gr/prod/api/index.php?component=latest&pc=S124',{'xml'},False)
    data,rec=save('euhforia-page','https://www-h-esc-org.content.swe.s2p.esa.int/h101g/',{'html'})
    if data:
        for item in rec.get('links',[]):
            href=item.get('src') or item.get('href') or ''
            if href.split('?')[0].endswith('.mp4'):
                candidate=urljoin(rec['source'],href)
                if urlsplit(candidate).hostname=='www-h-esc-org.content.swe.s2p.esa.int':
                    save('euhforia-video',candidate,{'mp4'}); break
    data,rec=save('connectivity-page','https://connect-tool.irap.omp.eu/',{'html'},False)
    if data:
        links=rec.get('links',[])
        # Inspect actual, current provider files, not historical API examples.
        count=0
        for i,item in enumerate(links):
            href=item.get('src') or item.get('href') or ''
            if any(x in href.lower() for x in ('connectivity','background','euv193','frame','hcs','adapt','nso','connectivity')) and not href.endswith('.js'):
                candidate=urljoin(rec['source'],href)
                if urlsplit(candidate).hostname=='connect-tool.irap.omp.eu' and count<12 and item['tag'] in ('a','img'):
                    save('mct-asset-'+str(i),candidate,None,False);count+=1
        for i,item in enumerate(links):
            href=item.get('src','')
            if item['tag']=='script' and href and not any(x in href.lower() for x in ('jquery','bootstrap','popper','d3','moment')):
                candidate=urljoin(rec['source'],href)
                if urlsplit(candidate).hostname=='connect-tool.irap.omp.eu':
                    save('mct-script-'+str(i),candidate,None,False)
    save('hapi-catalog','https://swe.ssa.esa.int/hapi/catalog',{'json'})
    save('hapi-capabilities','https://swe.ssa.esa.int/hapi/capabilities',{'json'})
    (ROOT/'manifest.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({'collected_at':report['collected_at'],'products':report['requests']},indent=2))
    # No success status is fabricated for unavailable individual providers.
    return 0 if any(x.get('status')=='received' for x in report['products'].values()) else 1

if __name__=='__main__':sys.exit(main())
