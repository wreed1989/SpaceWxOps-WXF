#!/usr/bin/env python3
"""Browser smoke test of published products, with no ESA credentials in browser."""
import functools,http.server,json,os,re,shutil,threading,time
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parent
RESULT=Path('esa-browser-report.json')
results=[]
def check(name,condition,detail=None):
 results.append({'check':name,'passed':bool(condition),**({'detail':detail} if detail is not None else {})})
 if not condition:raise AssertionError(name)

def main():
 html=Path('SpaceWxOps_Coronal_Hole_HSS_Outlook.html').read_text()
 scripts=re.findall(r'<script\b[^>]*>(.*?)</script\s*>',html,re.S|re.I)
 plotly=next(x for x in scripts if 'plotly.js v' in x[:200])
 with sync_playwright() as p:
  executable=os.environ.get('CHROME_PATH') or shutil.which('google-chrome') or shutil.which('chromium')
  browser=p.chromium.launch(executable_path=executable,headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
  context=browser.new_context(viewport={'width':1440,'height':1000})
  page=context.new_page();errors=[];requests=[]
  page.on('pageerror',lambda e:errors.append(str(e)))
  page.on('request',lambda r:requests.append({'url':r.url,'authorization':bool(r.headers.get('authorization'))}))
  # A small HTTP origin is needed to exercise real cross-origin delivery.
  handler=functools.partial(http.server.SimpleHTTPRequestHandler,directory=str(ROOT))
  server=http.server.ThreadingHTTPServer(('127.0.0.1',0),handler)
  thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
  page.goto('http://127.0.0.1:'+str(server.server_port)+'/dashboard-services.js',wait_until='domcontentloaded')
  page.set_content('<html><head><style>body{background:#101a28;color:#dce4ef;font-family:Arial}#target{max-width:1200px;margin:auto}</style></head><body><div id="target"></div></body></html>')
  page.add_script_tag(content=plotly)
  page.add_script_tag(content=(ROOT/'dashboard-services.js').read_text())
  page.add_script_tag(content=(ROOT/'dashboard-guidance.js').read_text())
  page.set_default_timeout(30000)
  manifest=page.evaluate('async()=>await SpaceWxSolarFeed.feed(true)')
  check('Published Feed Schema',manifest.get('schema')==2)
  check('Published Feed Contains No Credentials',all(x not in json.dumps(manifest).lower() for x in ('client_secret','access_token','refresh_token')))
  checks=page.evaluate('''async()=>{
   const f=SpaceWxSolarFeed,d=await f.feed();
   const s=f.parseFlareXML((await f.readText('https://example.invalid/?pc=S109&component=latest')).text,'sidc');
   const a=f.parseFlareXML((await f.readText('https://example.invalid/?pc=S124&component=latest')).text,'aeffort');
   return {sidc:s.records.length,aeffort:a.records.length,aeffortWeb:a.records[0]?.webGuidance||false,noInventedWindow:a.records.filter(x=>x.webGuidance).every(x=>x.validStart===null&&x.validEnd===null),zeroValid:a.records.some(x=>x.probabilities['X5+']===0),kso:await Promise.all(['ksoHalpha','ksoHalphaHC','ksoHalphaColor','ksoHalphaFlat'].map(async k=>({key:k,count:(await f.ksoFrames(k)).length}))),samples:Object.values(d.products.hapi.samples||{}).filter(x=>x.response?.data?.length).length};
  }''')
  check('SIDC Actual Forecast Records Parse',checks['sidc']>0,checks['sidc'])
  check('A-EFFort Actual Forecast Or Web Records Parse',checks['aeffort']>0,checks['aeffort'])
  check('Web Guidance Does Not Invent Validity',checks['noInventedWindow'])
  check('Valid Zero Remains Zero',checks['zeroValid'])
  check('All Four KSO Options Have Real Images',all(x['count']>0 for x in checks['kso']),checks['kso'])
  check('HAPI Contains Real Recent Samples',checks['samples']>0,checks['samples'])
  for name,mount in [('Solarmap','mountSolarmap'),('Coronal Holes','mountHoles'),('Magnetic Connectivity','mountConnectivity'),('EUHFORIA','mountEUHFORIA'),('HAPI','mountHapi')]:
   page.evaluate('mount=>{window.cleanup?.();document.getElementById("target").replaceChildren();window.cleanup=SpaceWxSolarFeed[mount](document.getElementById("target"));}',mount)
   page.wait_for_function('document.querySelector("[data-status]")?.textContent!=="Loading…"')
   status=page.locator('[data-status]').inner_text()
   check(name+' Mounts With Provider Content',status!='Unavailable',status)
   if name in ('Solarmap','Magnetic Connectivity'):
    page.wait_for_function('Array.from(document.querySelectorAll("[data-view] img")).length>0&&Array.from(document.querySelectorAll("[data-view] img")).every(x=>x.complete&&x.naturalWidth>0)')
    check(name+' Images Decode',True)
   if name=='Magnetic Connectivity':
    options=page.locator('[data-model] option').count();check('Published Spacecraft Maps Available',options>0,options)
    page.select_option('[data-background]','mag')
    page.wait_for_function('Array.from(document.querySelectorAll("[data-view] img")).every(x=>x.complete&&x.naturalWidth===1250)')
    check('Background Switch Preserves Native Registration',True)
    if options>1:page.select_option('[data-model]',index=1);page.wait_for_timeout(300)
   if name=='EUHFORIA':
    page.wait_for_function('document.querySelector("video")?.readyState>=1')
    metadata=page.evaluate('()=>{const v=document.querySelector("video");return {w:v.videoWidth,h:v.videoHeight,duration:v.duration};}')
    check('EUHFORIA Actual Video Metadata',metadata['w']>0 and metadata['duration']>0,metadata)
    page.evaluate('()=>document.querySelector("video").play()');page.wait_for_timeout(500)
    check('EUHFORIA Video Plays',page.evaluate('document.querySelector("video").currentTime>0'))
    page.select_option('[data-mode]','series');page.wait_for_function('document.querySelector(".esa-plot")?.data?.[0]?.y?.length>0')
    check('EUHFORIA Time Series Renders',True)
    page.select_option('[data-field]','Bclt');check('Native Magnetic Coordinate Label Preserved','Colatitudinal' in page.locator('[data-field] option:checked').inner_text())
   if name=='HAPI':
    check('HAPI Dataset Catalog Is Populated',page.locator('[data-dataset] option').count()>0)
    check('HAPI Sample Table Is Populated',page.locator('[data-view] tbody tr').count()>0)
    page.select_option('[data-mode]','metadata');check('HAPI Metadata Toggle Works','parameters' in page.locator('[data-view]').inner_text())
   Path('esa-browser-images').mkdir(exist_ok=True)
   page.screenshot(path='esa-browser-images/'+mount+'.png',full_page=True)
  image=page.evaluate('async()=>{const a=(await SpaceWxSolarFeed.ksoFrames("ksoHalpha"))[0];return await new Promise((resolve,reject)=>{const i=new Image();i.onload=()=>resolve({width:i.naturalWidth,height:i.naturalHeight});i.onerror=()=>reject(Error("KSO image failed"));i.src=a.url;});}')
  check('KSO Published Raster Loads In Browser',image['width']>0,image)
  check('No Browser Authentication Header',not any(r['authorization'] for r in requests))
  check('No Embedded Provider Login Request',not any('sso.s2p.esa.int' in r['url'] or '.content.swe.s2p.esa.int' in r['url'] for r in requests))
  check('No JavaScript Runtime Errors',not errors,errors)
  page.evaluate('window.cleanup?.()');browser.close();server.shutdown()
  return {'published_checked_at':manifest['checked_at'],'checks':results,'request_count':len(requests)}
if __name__=='__main__':
 try:
  report=main();RESULT.write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
 except Exception as e:
  RESULT.write_text(json.dumps({'checks':results,'error':type(e).__name__+': '+str(e)},indent=2));raise
