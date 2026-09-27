"""Four bounded CCMC public model comparisons; no operational writes."""
import json,pathlib,urllib.request,urllib.parse,urllib.error,time,hashlib,math
root=pathlib.Path('model-assets');root.mkdir(exist_ok=True)
base='https://kauai.ccmc.gsfc.nasa.gov'
params={'gridType':'4','groundLat':0,'groundLon':0,'groundAlt':0,'satLat':0,'satLon':0,'satAlt':20000,'satVx':0,'satVy':0,'satVz':0,'latStart':-90,'latStop':90,'latStep':5,'lonStart':-180,'lonStop':180,'lonStep':5,'timeStart':0,'timeStop':23,'timeStep':1,'doyStart':15,'doyStop':350,'doyStep':10,'angStart':5,'angStop':90,'angStep':1,'azStep':2,'doy':269,'hour':22,'ltTime':False,'firstSet':1,'freq':250,'phaseStable':10,'ssn':round(math.sqrt(167273+(140-63.7)*1123.6)-408.99,4),'kp':2,'kpAtSS':2,'percentile':80,'outPar':11}
records=[]
for frequency,kp in [(225,2),(400,2),(225,6),(400,6)]:
 p={**params,'freq':frequency,'kp':kp,'kpAtSS':kp};name=f'wbmod_{frequency}MHz_Kp{kp}'
 (root/(name+'_inputs.json')).write_text(json.dumps(p,indent=2));rec={'name':name,'parameters':p}
 try:
  req=urllib.request.Request(base+'/instantrun/api/wbmod/',data=json.dumps(p).encode(),headers={'Content-Type':'application/json','Accept':'application/json','User-Agent':'SpaceWxOps-Research-Benchmark/1.0'},method='POST')
  with urllib.request.urlopen(req,timeout=90) as response: data=response.read(15000000)
  (root/(name+'_response.json')).write_bytes(data);body=json.loads(data);rec['response']=body
  if body.get('plot'):
   url=urllib.parse.urljoin(base,body['plot'])
   if urllib.parse.urlparse(url).hostname!='kauai.ccmc.gsfc.nasa.gov':raise ValueError('Unexpected plot host')
   with urllib.request.urlopen(url,timeout=35) as response:image=response.read(15000000)
   (root/(name+'.png')).write_bytes(image);rec['plot_sha256']=hashlib.sha256(image).hexdigest()
  rec['status']='success'
 except urllib.error.HTTPError as error:
  rec.update(status='failed',http_status=error.code,error=error.read(5000).decode(errors='replace'))
  records.append(rec);print(json.dumps(rec),flush=True);break
 except Exception as error:
  rec.update(status='failed',error=str(error));records.append(rec);print(json.dumps(rec),flush=True);break
 records.append(rec);print(json.dumps(rec),flush=True);time.sleep(3)
(root/'benchmark_manifest.json').write_text(json.dumps(records,indent=2))
