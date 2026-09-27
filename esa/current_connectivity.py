"""Preserve the Magnetic Connectivity Tool's published CSS image registration."""
import hashlib,io,re
from datetime import datetime,timezone
from urllib.parse import urljoin,urlsplit
from PIL import Image
from harvest import MCT,Links,auth
CSS_URL=MCT+'static/css/connect2.css'

def registration(css):
 css=re.sub(r'/\*.*?\*/','',css,flags=re.S)
 def properties(name):
  m=re.search(r'(?m)^\.'+name+r'\s*\{([^}]+)\}',css)
  if not m:raise auth.SafeError('missing_registration_css')
  return {k:int(v) for k,v in re.findall(r'(width|height|left|bottom)\s*:\s*(\d+)px\s*;',m[1])}
 frame=properties('map_frame_popup');inner=properties('map_img_popup')
 if set(frame)!={'width','height'} or set(inner)!={'width','height','left','bottom'}:raise auth.SafeError('unsupported_registration_css')
 x=inner['left'];y=frame['height']-inner['bottom']-inner['height']
 if min(frame.values())<100 or max(frame.values())>6000 or min(x,y)<0 or x+inner['width']>frame['width'] or y+inner['height']>frame['height']:raise auth.SafeError('invalid_registration_geometry')
 return {'frame_width':frame['width'],'frame_height':frame['height'],'map_width':inner['width'],'map_height':inner['height'],'left':x,'top':y,'source':CSS_URL,'css_sha256':hashlib.sha256(css.encode()).hexdigest()}

def registered(self,url,original,reg,background):
 outer=(reg['frame_width'],reg['frame_height']);inner=(reg['map_width'],reg['map_height'])
 size=(original.get('width'),original.get('height'))
 if size==outer:return original
 if size!=inner:raise auth.SafeError('unrecognized_map_dimensions')
 image=Image.open(self.root/original['path']).convert('RGBA')
 canvas=Image.new('RGBA',outer,(255,255,255,255) if background else (0,0,0,0))
 canvas.paste(image,(reg['left'],reg['top']))
 # Placement only: the registered map pixels remain byte-identical.
 if canvas.crop((reg['left'],reg['top'],reg['left']+inner[0],reg['top']+inner[1])).tobytes()!=image.tobytes():raise auth.SafeError('registration_changed_pixels')
 out=io.BytesIO();canvas.save(out,format='PNG');raw=out.getvalue();digest=hashlib.sha256(raw).hexdigest();path='assets/'+digest+'.png';(self.root/path).write_bytes(raw)
 value={'path':path,'sha256':digest,'bytes':len(raw),'width':outer[0],'height':outer[1],'fetched_at':original['fetched_at'],'last_referenced_at':self.stamp,'original_path':original['path'],'registration':reg}
 self.asset_index['registered:'+url]=value
 return value

def current_connectivity(self):
 raw,_=self.request(MCT,False);css,_=self.request(CSS_URL,False);reg=registration(css.decode('utf-8'))
 parser=Links();parser.feed(raw.decode('utf-8',errors='replace'));models={}
 pat=re.compile(r'^(EARTH|PSP|STA|SOLO|BEPI|ALL)_PARKER_PFSS_(SCTIMEBW|SUNTIMEBW|SCTIME|SUNTIME)_(NSO|WSO|ADAPT)_EXTENDED_(\d{8}T\d{6})_(background\w+|layer\w+|fileconnectivity)\.(png|ascii)$')
 for _,href,_ in parser.links:
  u=urljoin(MCT,href);parts=urlsplit(u);m=pat.fullmatch(parts.path.rsplit('/',1)[-1])
  if not m or parts.hostname!='connect-tool.irap.omp.eu' or not parts.path.startswith('/static/data/connect_tool/'):continue
  body,mode,field,stamp,layer,ext=m.groups();key='-'.join((body,mode,field,stamp))
  if key not in models and len(models)>=12:continue
  model=models.setdefault(key,{'id':key,'body':body,'mode':mode,'field':field,'cycle':datetime.strptime(stamp,'%Y%m%dT%H%M%S').replace(tzinfo=timezone.utc).isoformat().replace('+00:00','Z'),'backgrounds':{},'layers':{},'registration':reg})
  if (layer.startswith('background') and layer[10:] in model['backgrounds']) or (layer.startswith('layer') and layer[5:] in model['layers']) or (layer=='fileconnectivity' and model.get('parameters')):continue
  if layer.startswith('background') and layer not in ('backgroundmag','backgroundeuv193','backgroundeuv171','backgroundeuv304','backgroundwl','backgroundeui174','backgroundeui304'):continue
  try:
   a=self.asset(u,kind='txt' if ext=='ascii' else None,cache_hours=1)
   if ext=='png':a=registered(self,u,a,reg,layer.startswith('background'))
   if layer.startswith('background'):model['backgrounds'][layer[10:]]=a
   elif layer.startswith('layer'):model['layers'][layer[5:]]=a
   else:model['parameters']={**a,'source':u}
  except Exception:continue
 ready=[]
 for model in models.values():
  if not model['backgrounds'] or not all(k in model['layers'] for k in ('frame','connectivity')):continue
  sizes={(v['width'],v['height']) for v in list(model['backgrounds'].values())+list(model['layers'].values())}
  if len(sizes)!=1:continue
  model['width'],model['height']=next(iter(sizes));ready.append(model)
 if not ready:raise auth.SafeError('no_complete_connectivity_maps')
 return {'source':MCT,'models':ready,'registration':reg,'note':'Provider map layers are placed at the exact CSS-defined offset inside the original legend frame. No interpolation, stretching, invented field lines or reconstructed PFSS. Controls expose actual published runs; arbitrary archive/model requests remain at the provider.'}
