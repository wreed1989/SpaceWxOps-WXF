#!/usr/bin/env python3
"""Validate media hashes, schema and safe publication paths before delivery."""
import hashlib,json,re,sys,subprocess
from pathlib import Path
from PIL import Image
from harvest import ASSET_RE,utc,passive_svg

def validate(root):
 root=Path(root);d=json.loads((root/'latest.json').read_text())
 if d.get('schema')!=2 or not utc(d.get('checked_at')):raise ValueError('manifest_schema')
 if not isinstance(d.get('products'),dict) or not isinstance(d.get('assets'),dict):raise ValueError('manifest_collections')
 checks=[];paths=set()
 for v in d['assets'].values():
  path=v.get('path','')
  if not ASSET_RE.fullmatch(path):raise ValueError('asset_path')
  f=root/path
  if not f.is_file() or f.is_symlink():raise ValueError('missing_asset')
  if f.stat().st_size>24000000:raise ValueError('asset_size')
  data=f.read_bytes()
  if hashlib.sha256(data).hexdigest()!=v.get('sha256') or len(data)!=v.get('bytes'):raise ValueError('asset_hash')
  if path in paths:continue
  paths.add(path)
  if f.suffix in ('.png','.jpg','.gif'):
   im=Image.open(f);im.verify();im=Image.open(f)
   if im.size!=(v['width'],v['height']):raise ValueError('image_size')
  elif f.suffix=='.mp4':
   if data[4:8]!=b'ftyp':raise ValueError('invalid_video')
   result=subprocess.run(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=codec_name,width,height','-of','json',str(f)],capture_output=True,text=True,timeout=20,check=True)
   streams=json.loads(result.stdout).get('streams',[])
   if not streams or streams[0].get('codec_name') not in ('h264','vp9','av1'):raise ValueError('unsupported_video')
  elif re.search(br'<(?:script|html|!doctype)',data[:2000],re.I):raise ValueError('active_text')
 checks.append({'check':'All Passive Assets Decode And Match Hashes','count':len(paths),'passed':True})
 for key,p in d['products'].items():
  if p.get('status') not in ('ok','partial','last_good','unavailable'):raise ValueError('product_status')
  if p['status']=='unavailable':continue
  if key=='solarmap':
   v=passive_svg(p['svg'].encode())
   if not v['has_image']:raise ValueError('missing_solarmap_image')
  if key=='connectivity':
   if not p.get('models'):raise ValueError('empty_model_catalog')
   for m in p['models']:
    if not utc(m.get('cycle')) or not m.get('backgrounds') or not m.get('layers',{}).get('connectivity'):raise ValueError('incomplete_model')
    for a in list(m['backgrounds'].values())+list(m['layers'].values()):
     if (a['width'],a['height'])!=(m['width'],m['height']):raise ValueError('unregistered_layers')
  if key=='euhforia':
   if not p.get('rows') or not p.get('video'):raise ValueError('empty_model_output')
   if 'Bclt' not in [x['name'] for x in p['columns']]:raise ValueError('coordinate_frame_changed')
  checks.append({'check':key+' Payload Contract','passed':True})
 def walk(value):
  if isinstance(value,dict):
   if 'path' in value:
    p=value['path']
    if not isinstance(p,str) or not ASSET_RE.fullmatch(p) or not (root/p).is_file():raise ValueError('unresolved_product_asset')
   for x in value.values():walk(x)
  elif isinstance(value,list):
   for x in value:walk(x)
 walk(d['products'])
 for f in root.rglob('*'):
  if f.is_symlink():raise ValueError('symlink_in_publication')
  if f.is_file() and str(f.relative_to(root)) not in ('latest.json','health.json','README.md') and not ASSET_RE.fullmatch(str(f.relative_to(root))):raise ValueError('unapproved_publication_file')
 checks.append({'check':'No Active Code, Login Pages Or Unapproved Files Published','passed':True})
 return {'checked_at':d['checked_at'],'checks':checks,'products':{k:{'status':v['status'],'availability':v.get('availability')} for k,v in d['products'].items()}}
if __name__=='__main__':
 try:
  report=validate(sys.argv[1] if len(sys.argv)>1 else 'esa-live-output')
  Path('esa-validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
 except Exception as e:print('Validation failed:',type(e).__name__,str(e)[:120]);sys.exit(1)
