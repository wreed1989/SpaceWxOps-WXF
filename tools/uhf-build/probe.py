import urllib.request, json, pathlib, urllib.parse
root=pathlib.Path('model-assets');root.mkdir(exist_ok=True)
payload=dict(gridType='4',groundLat=0,groundLon=0,groundAlt=0,satLat=0,satLon=0,satAlt=35786,satVx=0,satVy=0,satVz=0,latStart=-90,latStop=90,latStep=5,lonStart=-180,lonStop=180,lonStep=5,timeStart=0,timeStop=24,timeStep=1,doyStart=15,doyStop=350,doyStep=10,angStart=5,angStop=90,angStep=1,azStep=2,doy=80,hour=0,ltTime=False,firstSet=1,freq=225,phaseStable=10,ssn=80,kp=2,kpAtSS=2,percentile=20,outPar=11)
(root/'wbmod-request.json').write_text(json.dumps(payload,indent=2))
url='https://kauai.ccmc.gsfc.nasa.gov/instantrun/api/wbmod/'
req=urllib.request.Request(url,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json','Accept':'application/json'},method='POST')
try:
 with urllib.request.urlopen(req,timeout=120) as r: data=r.read();print('RESPONSE HEADERS',dict(r.headers))
 (root/'wbmod-response.json').write_bytes(data);print('MODEL RESPONSE',data.decode()[:12000])
 result=json.loads(data)
 for key,value in result.items():
  if isinstance(value,str) and (value.startswith('https://') or value.startswith('/')):
   link=urllib.parse.urljoin(url,value)
   if urllib.parse.urlparse(link).hostname!='kauai.ccmc.gsfc.nasa.gov':continue
   try:
    with urllib.request.urlopen(link,timeout=60) as r: blob=r.read();mime=r.headers.get('content-type','')
    name=pathlib.Path(urllib.parse.urlparse(link).path).name or key
    (root/name).write_bytes(blob);print('LINK',key,link,len(blob),mime)
   except Exception as e:print('LINK ERROR',key,str(e))
except urllib.error.HTTPError as e:
 print('HTTP ERROR',e.code,dict(e.headers),e.read().decode()[:5000]);raise
