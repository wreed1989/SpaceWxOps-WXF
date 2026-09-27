#!/usr/bin/env python3
"""Collect passive provider products. Never publish provider pages or credentials."""
from __future__ import annotations
import base64,hashlib,html,io,json,math,os,re,sys
import xml.etree.ElementTree as ET
from datetime import datetime,timedelta,timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin,urlsplit,urlencode
from PIL import Image
import check_access as auth
TOKEN_SCOPE_KSO='387309144d7b0e6251d9f0c63f7c02e6'
SIDC=auth.SIDC
MCT='https://connect-tool.irap.omp.eu/'
EU='https://www-h-esc-org.content.swe.s2p.esa.int/h101g/'
HAPI='https://swe.ssa.esa.int/hapi/'
ASSET_RE=re.compile(r'^assets/[a-f0-9]{64}\.(png|jpg|gif|mp4|txt)$')
Image.MAX_IMAGE_PIXELS=36000000
ET.register_namespace('','http://www.w3.org/2000/svg')
ET.register_namespace('xlink','http://www.w3.org/1999/xlink')
class Links(HTMLParser):
 def __init__(self):super().__init__();self.links=[]
 def handle_starttag(self,t,a):
  a=dict(a)
  if t in ('a','img','source','iframe'):self.links.append((t,a.get('src') or a.get('href') or '',a))
def utc(v):
 if not isinstance(v,str):return None
 v=v.strip()
 if not re.fullmatch(r'\d{4}-\d\d-\d\d[T ]\d\d:\d\d(?::\d\d(?:\.\d+)?)?(?:Z|[+-]\d\d:\d\d)?',v):return None
 try:
  d=datetime.fromisoformat(v.replace('Z','+00:00'))
  if d.tzinfo is None:d=d.replace(tzinfo=timezone.utc)
  return d.astimezone(timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z')
 except ValueError:return None
def tag(e):return e.tag.split('}')[-1] if isinstance(e.tag,str) else ''
def xml_root(data):
 if re.search(br'<!ENTITY|<!DOCTYPE[^>]*\[',data,re.I):raise auth.SafeError('unsafe_xml')
 data=re.sub(br'<!DOCTYPE\s+svg\s+(?:PUBLIC|SYSTEM)\s+[^>]*>',b'',data,flags=re.I)
 if b'<!DOCTYPE' in data.upper():raise auth.SafeError('unsafe_xml')
 try:return ET.fromstring(data)
 except ET.ParseError:raise auth.SafeError('invalid_xml') from None
def passive_svg(data):
 root=xml_root(data)
 if tag(root)!='svg':raise auth.SafeError('not_svg')
 allowed={'svg','g','path','rect','circle','ellipse','line','polyline','polygon','text','tspan','image','defs','clipPath','mask','linearGradient','radialGradient','stop','title','desc','use'}
 for p in list(root.iter()):
  for e in list(p):
   if tag(e) not in allowed:p.remove(e)
 for e in root.iter():
  for name,v in list(e.attrib.items()):
   k=name.split('}')[-1].lower()
   if k.startswith('on') or k.startswith('data-'):del e.attrib[name];continue
   if k=='href':
    if v.startswith('#'):continue
    if tag(e)=='image' and re.fullmatch(r'data:image/(?:png|jpeg|jpg|gif|jp2);base64,[A-Za-z0-9+/=\s]+',v):
     try:
      b=base64.b64decode(re.sub(r'\s+','',v.split(',',1)[1]),validate=True)
      im=Image.open(io.BytesIO(b));im.verify()
      if b.startswith(b'\xff\xd8\xff'):mime='image/jpeg'
      elif b.startswith(b'\x89PNG\r\n\x1a\n'):mime='image/png'
      elif b.startswith((b'GIF87a',b'GIF89a')):mime='image/gif'
      else:raise ValueError()
      e.attrib[name]='data:'+mime+';base64,'+base64.b64encode(b).decode();continue
     except Exception:pass
    del e.attrib[name]
   elif re.search(r'javascript:|expression\s*\(|@import|url\s*\(\s*(?!#[\w.-]+\))',v,re.I):del e.attrib[name]
 legends={}
 for e in root.iter():
  cls=e.get('class','')
  if cls.startswith('legend_'):legends.setdefault(cls[7:],[]).append(''.join(e.itertext()))
 times={k:utc(v[-1].replace(' UTC','')) for k,v in legends.items() if v}
 layers={e.get('id')[14:]:sum(1 for _ in e.iter())-1 for e in root.iter() if e.get('id','').startswith('group_current_')}
 has_image=any(tag(e)=='image' and any(k.split('}')[-1]=='href' for k in e.attrib) for e in root.iter())
 return {'svg':ET.tostring(root,encoding='unicode'),'has_image':has_image,'layers':layers,'layer_times':times,'observed_at':times.get('images_sun') if has_image else None}
def parse_dsv(text):
 meta={}
 for key in ('DATE','SIM_START_DATE','GRID','MAGNETOGRAM'):
  m=re.search(r'^#\s+'+key+r'\s*=\s*(.+)$',text,re.M)
  if m:meta[key]=m[1].strip()[:180]
 lines=[s.strip() for s in text.splitlines() if s.strip() and not s.startswith('#')]
 if not lines or not lines[0].startswith('date[UTC] '):raise auth.SafeError('unrecognized_dsv_columns')
 columns=[]
 for v in lines[0].split():
  m=re.fullmatch(r'([\w]+)\[([^\]]+)\]',v)
  if not m:raise auth.SafeError('unrecognized_dsv_columns')
  columns.append({'name':m[1],'unit':m[2]})
 rows=[]
 for line in lines[1:]:
  v=line.split()
  if len(v)!=len(columns):raise auth.SafeError('dsv_row_length')
  stamp=utc(v[0])
  if not stamp:raise auth.SafeError('dsv_time')
  try:nums=[float(x) for x in v[1:]]
  except ValueError:raise auth.SafeError('dsv_number') from None
  if any(not math.isfinite(x) for x in nums):raise auth.SafeError('dsv_nonfinite')
  rows.append([stamp,*nums])
 if not rows or len(rows)>10000:raise auth.SafeError('dsv_size')
 if any(b[0]<=a[0] for a,b in zip(rows,rows[1:])):raise auth.SafeError('dsv_time_order')
 return {'columns':columns,'rows':rows,'metadata':meta,'run_at':utc(meta.get('DATE')),'simulation_start':utc(meta.get('SIM_START_DATE')),'start':rows[0][0],'stop':rows[-1][0],'frame_note':'Provider spherical components retained; Bclt is not labeled GSM Bz.'}
class Harvester:
 def __init__(self,root):
  self.root=root;root.mkdir(parents=True,exist_ok=True);(root/'assets').mkdir(exist_ok=True)
  self.now=datetime.now(timezone.utc);self.stamp=self.now.isoformat(timespec='seconds').replace('+00:00','Z')
  auth.AUTH_HOSTS['sso.kso.ac.at']=TOKEN_SCOPE_KSO;auth.ALLOWED_SCOPES.add(TOKEN_SCOPE_KSO);auth.MAX_BYTES=24000000
  self.client=auth.M2M(os.environ.get('ESAID',''),os.environ.get('ESASECRET',''))
  self.old={};self.requests=[];self.asset_index={}
  try:self.old=json.loads((root/'latest.json').read_text())
  except (OSError,ValueError):pass
  self.doc={'schema':2,'checked_at':self.stamp,'products':{},'assets':{},'attribution':'ESA Space Safety Programme; ROB/SIDC, KSO/University of Graz, NOA/IAASARS, IRAP and KU Leuven/RAL Space/UK Met Office. Provider data and imagery retain their original rights.','terms':'https://swe.ssa.esa.int/terms-conditions'}
 def request(self,url,authenticate=True):
  for _ in range(4):
   host=urlsplit(url).hostname;scope=auth.AUTH_HOSTS.get(host) if authenticate else None
   r=auth.exchange(url,bearer=self.client.token(scope) if scope else None,scope=scope)
   if r.status in (301,302,303,307,308):
    nxt=urljoin(url,html.unescape(r.headers.get('location','')))
    if urlsplit(nxt).hostname=='sso.s2p.esa.int':raise auth.SafeError('login_redirect')
    if urlsplit(nxt).hostname not in set(auth.AUTH_HOSTS)|auth.PUBLIC_HOSTS:raise auth.SafeError('unapproved_redirect')
    url=nxt;continue
   if r.status!=200:raise auth.SafeError('http_'+str(r.status))
   return r.body,r.headers
  raise auth.SafeError('redirect_limit')
 def json(self,url):
  raw,_=self.request(url)
  try:v=json.loads(raw)
  except (ValueError,UnicodeError):raise auth.SafeError('invalid_json') from None
  if not isinstance(v,(dict,list)):raise auth.SafeError('invalid_json_root')
  if isinstance(v,dict) and (v.get('error') or v.get('errors')):raise auth.SafeError('provider_error')
  return v
 def asset(self,url,kind=None,cache_hours=0):
  prior=self.asset_index.get(url) or self.old.get('assets',{}).get(url,{})
  path=prior.get('path','')
  if cache_hours and ASSET_RE.fullmatch(path) and (self.root/path).is_file():
   d=utc(prior.get('fetched_at'))
   if d and timedelta(0)<=self.now-datetime.fromisoformat(d.replace('Z','+00:00'))<timedelta(hours=cache_hours) and hashlib.sha256((self.root/path).read_bytes()).hexdigest()==prior.get('sha256'):
    self.asset_index[url]=prior;return prior
  data,headers=self.request(url)
  if data.startswith(b'\x89PNG\r\n\x1a\n'):ext='png'
  elif data.startswith(b'\xff\xd8\xff'):ext='jpg'
  elif data.startswith((b'GIF87a',b'GIF89a')):ext='gif'
  elif len(data)>12 and data[4:8]==b'ftyp':ext='mp4'
  elif kind=='txt' and not re.search(br'<(?:!doctype|html|script)\b',data[:2000],re.I):ext='txt'
  else:raise auth.SafeError('not_passive_media')
  info={}
  if ext in ('png','jpg','gif'):
   im=Image.open(io.BytesIO(data));im.verify();im=Image.open(io.BytesIO(data));w,h=im.size
   if min(w,h)<50 or max(w,h)>6000:raise auth.SafeError('image_dimensions')
   info={'width':w,'height':h}
  digest=hashlib.sha256(data).hexdigest();path='assets/'+digest+'.'+ext
  (self.root/path).write_bytes(data)
  a={'path':path,'sha256':digest,'bytes':len(data),'fetched_at':self.stamp,**info}
  if headers.get('last-modified'):a['last_modified']=headers['last-modified']
  self.asset_index[url]=a;return a
 def product(self,name,fn):
  try:
   p=fn();p.setdefault('status','ok');p['fetched_at']=self.stamp;self.doc['products'][name]=p
   self.requests.append({'product':name,'status':p['status'],**({'availability':p['availability']} if 'availability' in p else {})})
  except Exception as e:
   code=str(e) if isinstance(e,auth.SafeError) else 'validation_'+type(e).__name__;old=self.old.get('products',{}).get(name)
   if isinstance(old,dict) and old.get('status') in ('ok','partial','last_good'):
    self.doc['products'][name]={**old,'status':'last_good','latest_error':code,'checked_at':self.stamp}
    for u,a in self.old.get('assets',{}).items():
     if ASSET_RE.fullmatch(a.get('path','')) and (self.root/a['path']).is_file():self.asset_index.setdefault(u,a)
   else:self.doc['products'][name]={'status':'unavailable','error':code,'checked_at':self.stamp}
   self.requests.append({'product':name,'status':code})
 def flare(self,provider):
  if provider=='sidc':source=SIDC+'?component=latest&pc=S109&psc=b'
  else:
   data,_=self.request('https://swe.ssa.esa.int/iaasars_s-federated',False)
   links=Links();links.feed(data.decode('utf-8',errors='replace'));source=None
   for t,u,_ in links.links:
    host=urlsplit(u).hostname or ''
    if t=='iframe' and host.endswith('.content.swe.s2p.esa.int') and ('effort' in host or 'noa' in host):
     auth.AUTH_HOSTS[host]='swe_contentproxy';source=urljoin(u,'/prod/api/index.php')+'?component=latest&pc=S124';break
   if not source:raise auth.SafeError('aeffort_provider_not_resolved')
  raw,_=self.request(source);root=xml_root(raw)
  if not any(tag(e)=='probability' for e in root.iter()):raise auth.SafeError('no_forecast_records')
  stamps=[utc(e.text or '') for e in root.iter() if tag(e)=='issuetime'];stamps=[x for x in stamps if x]
  ends=[utc(e.text or '') for e in root.iter() if tag(e)=='end'];ends=[x for x in ends if x]
  return {'source':source,'xml':ET.tostring(root,encoding='unicode'),'provider':provider,'issued_at':max(stamps) if stamps else None,'valid_until':max(ends) if ends else None,'availability':'current' if ends and max(ends)>self.stamp else 'expired'}
 def holes(self):
  source=SIDC+'?component=latest&pc=S126&psc=a&type=ch';tracks=self.json(source);run=self.json(SIDC+'?component=latest&pc=S126&psc=a&type=run')
  if not isinstance(tracks,list) or not isinstance(run,dict) or not isinstance(run.get('Detections'),list):raise auth.SafeError('unrecognized_coronal_holes')
  return {'source':source,'tracks':tracks,'run':run,'observed_at':utc(run.get('ImageTime')),'run_at':utc(run.get('RunTime')),'area_unit':None,'note':'Provider Area units are not declared. Null polarity is unknown, not zero. Centers are not boundary polygons.'}
 def solarmap(self):
  flags={k:1 for k in ('regions_sidc_sunspot','regions_inaf_sunspot','regions_noaa_region','regions_noaa_returning','regions_noaa_plages','regions_ukmo_sunspot','flares_solardemon','flares_noaa','flares_kso','cmes_cactus','coronal_holes_sidc','filaments_kso','features_grid','features_legend')}
  source=SIDC+'?'+urlencode({'pc':'S101','psc':'c','component':'latest','images_sun':'SWAP','features_width':1024,'timenavbar.carrington_planet_body':'EARTH',**flags})
  raw,_=self.request(source);r=passive_svg(raw)
  if not r['has_image']:raise auth.SafeError('solarmap_background_unavailable')
  return {**r,'source':source,'image':'SWAP','viewpoint':'EARTH','note':'Registered provider SWAP image. Empty feature layers are unavailable; S126 detections are separate, not invented polygons.'}
 def kso(self):
  result={'source':'https://sso.kso.ac.at/prod/API/index.php','variants':{}}
  start=(self.now-timedelta(hours=18)).strftime('%Y-%m-%dT%H:%M:%SZ');stop=self.now.strftime('%Y-%m-%dT%H:%M:%SZ')
  for key,ft in [('normal','jpeg'),('color','jpegc'),('clv','jpegfc')]:
   source=result['source']+'?'+urlencode({'pc':'S107','psc':'a','component':'archive','type':'nm','filetype':ft,'dts_start':start,'dts_end':stop})
   try:
    data=self.json(source);frames=[]
    if not isinstance(data,list):raise auth.SafeError('kso_archive_schema')
    records=[x.get('data',{}) for x in data if isinstance(x,dict)]
    records=[x for x in records if isinstance(x.get('File'),str) and urlsplit(x['File']).hostname=='sso.kso.ac.at' and utc(x.get('modify'))]
    records.sort(key=lambda x:utc(x['modify']))
    for rec in records[-50:]:
     try:frames.append({**self.asset(rec['File'],cache_hours=48),'time':utc(rec['modify']),'source':rec['File']})
     except Exception:continue
    if not frames:raise auth.SafeError('no_valid_images')
    result['variants'][key]={'frames':frames,'observed_at':frames[-1]['time'],'source':source}
   except Exception as e:result['variants'][key]={'frames':[],'status':str(e) if isinstance(e,auth.SafeError) else 'unavailable'}
  try:
   source=result['source']+'?component=latest&pc=S107&psc=a&type=hc';raw,_=self.request(source);target=raw.decode().strip().strip('"')
   if urlsplit(target).hostname!='sso.kso.ac.at':raise auth.SafeError('kso_latest_url')
   result['variants']['contrast']={'frames':[{**self.asset(target),'time':None,'source':target}],'observed_at':None,'source':source,'note':'Latest high-contrast image. Read observation time printed on the image; modification time is not observation time.'}
  except Exception:result['variants']['contrast']={'frames':[],'status':'unavailable'}
  if not any(x['frames'] for x in result['variants'].values()):raise auth.SafeError('no_valid_images')
  result['status']='ok' if all(x['frames'] for x in result['variants'].values()) else 'partial';return result
 def connectivity(self):
  raw,_=self.request(MCT,False);parser=Links();parser.feed(raw.decode('utf-8',errors='replace'));models={}
  pat=re.compile(r'^(EARTH|PSP|STA|SOLO|BEPI|ALL)_PARKER_PFSS_(SCTIMEBW|SUNTIMEBW|SCTIME|SUNTIME)_(NSO|WSO|ADAPT)_EXTENDED_(\d{8}T\d{6})_(background\w+|layer\w+|fileconnectivity)\.(png|ascii)$')
  for _,href,_ in parser.links:
   u=urljoin(MCT,href);parts=urlsplit(u);m=pat.fullmatch(parts.path.rsplit('/',1)[-1])
   if not m or parts.hostname!='connect-tool.irap.omp.eu' or not parts.path.startswith('/static/data/connect_tool/'):continue
   body,mode,field,stamp,layer,ext=m.groups();key='-'.join((body,mode,field,stamp))
   model=models.setdefault(key,{'id':key,'body':body,'mode':mode,'field':field,'cycle':datetime.strptime(stamp,'%Y%m%dT%H%M%S').replace(tzinfo=timezone.utc).isoformat().replace('+00:00','Z'),'backgrounds':{},'layers':{}})
   if (layer.startswith('background') and layer[10:] in model['backgrounds']) or (layer.startswith('layer') and layer[5:] in model['layers']) or (layer=='fileconnectivity' and model.get('parameters')):continue
   if layer.startswith('background') and layer not in ('backgroundmag','backgroundeuv193','backgroundeuv171','backgroundeuv304','backgroundwl','backgroundeui174','backgroundeui304'):continue
   try:
    a=self.asset(u,kind='txt' if ext=='ascii' else None,cache_hours=1)
    if layer.startswith('background'):model['backgrounds'][layer[10:]]=a
    elif layer.startswith('layer'):model['layers'][layer[5:]]=a
    else:model['parameters']={**a,'source':u}
   except Exception:continue
  ready=[]
  for m in models.values():
   if not m['backgrounds'] or not all(k in m['layers'] for k in ('frame','connectivity')):continue
   sizes={(v['width'],v['height']) for v in list(m['backgrounds'].values())+list(m['layers'].values())}
   if len(sizes)!=1:continue
   m['width'],m['height']=next(iter(sizes));ready.append(m)
  if not ready:raise auth.SafeError('no_complete_connectivity_maps')
  return {'source':MCT,'models':ready,'note':'Original co-registered provider layers. No locally synthesized PFSS or Parker field lines. Controls show actual published runs; other requests remain in the provider tool.'}
 def euhforia(self):
  video=self.asset(EU+'data/euhforia_Earth.mp4',cache_hours=1);raw,_=self.request(EU+'data/euhforia_Earth.dsv');series=parse_dsv(raw.decode('utf-8'))
  return {'source':EU,**series,'video':video,'attribution':'KU Leuven, RAL Space, UK Met Office and ESA Space Safety Programme','note':'Provider EUHFORIA model guidance, not observations or a local run. Native spherical components and units preserved.'}
 def hapi(self):
  catalog=self.json(HAPI+'catalog')
  if catalog.get('status',{}).get('code')!=1200 or not isinstance(catalog.get('catalog'),list):raise auth.SafeError('hapi_catalog_error')
  prior=self.old.get('products',{}).get('hapi',{});info={};samples={};stop=(self.now-timedelta(minutes=10)).replace(second=0,microsecond=0);start=stop-timedelta(minutes=10)
  for item in catalog['catalog'][:40]:
   ident=item['id']
   try:
    d=utc(prior.get('fetched_at'));metadata=prior.get('info',{}).get(ident) if d and self.now-datetime.fromisoformat(d.replace('Z','+00:00'))<timedelta(hours=24) else None
    if not metadata:metadata=self.json(HAPI+'info?'+urlencode({'dataset':ident}))
    if metadata.get('status',{}).get('code')!=1200:continue
    info[ident]=metadata;names=[p['name'] for p in metadata.get('parameters',[]) if p.get('type') in ('double','integer') and not p.get('size')][:3]
    if not names:continue
    query={'dataset':ident,'start':start.strftime('%Y-%m-%dT%H:%M:%SZ'),'stop':stop.strftime('%Y-%m-%dT%H:%M:%SZ'),'parameters':','.join(names),'format':'json','include':'header'}
    sample=self.json(HAPI+'data?'+urlencode(query))
    if len(sample.get('data',[]))>5000:raise auth.SafeError('hapi_sample_size')
    json.dumps(sample,allow_nan=False)
    samples[ident]={'request':query,'response':sample}
   except Exception as e:samples[ident]={'error':str(e) if isinstance(e,auth.SafeError) else 'unavailable'}
  return {'source':HAPI,'catalog':catalog['catalog'],'info':info,'samples':samples,'sample_note':'Bounded ten-minute samples of up to three scalar parameters. Coverage stopDate is not proof of current observations. No-data codes and fill values are retained.'}
 def run(self):
  for name,fn in [('sidc',lambda:self.flare('sidc')),('aeffort',lambda:self.flare('aeffort')),('holes',self.holes),('solarmap',self.solarmap),('kso',self.kso),('connectivity',self.connectivity),('euhforia',self.euhforia),('hapi',self.hapi)]:self.product(name,fn)
  self.doc['assets']=self.asset_index;payload=json.dumps(self.doc,separators=(',',':'),ensure_ascii=True,allow_nan=False)
  if len(payload)>12000000:raise auth.SafeError('manifest_too_large')
  values=[self.client.client,self.client.secret]+[x[0] for x in self.client.tokens.values()]
  if any(v and v in payload for v in values):raise auth.SafeError('sensitive_output_rejected')
  (self.root/'latest.json').write_text(payload);keep={a['path'] for a in self.asset_index.values()}
  for f in (self.root/'assets').iterdir():
   if f.is_file() and str(f.relative_to(self.root)) not in keep:f.unlink()
  (self.root/'README.md').write_text('# SpaceWxOps Solar Product Cache\n\nPassive provider media and normalized data. No authentication material.\n\n'+self.doc['attribution']+'\n\nUse remains subject to provider terms and ESA SWE terms: https://swe.ssa.esa.int/terms-conditions . Rolling cache, not an independent model or complete archive.\n')
  health={'checked_at':self.stamp,'products':self.requests,'asset_count':len(self.asset_index)};(self.root/'health.json').write_text(json.dumps(health,indent=2));print(json.dumps(health,indent=2))
  return 0 if any(p.get('status') in ('ok','partial') for p in self.doc['products'].values()) else 1
if __name__=='__main__':
 try:sys.exit(Harvester(Path(os.environ.get('ESA_OUTPUT_DIR','esa-live-output'))).run())
 except Exception as e:print('Collector stopped:',str(e) if isinstance(e,auth.SafeError) else type(e).__name__);sys.exit(1)
