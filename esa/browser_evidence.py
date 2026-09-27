#!/usr/bin/env python3
"""Live public-feed smoke checks for responsive solar views and model evidence.
No browser credentials. Synthetic matching cases belong in separate unit tests.
"""
import functools,http.server,json,os,shutil,threading
from pathlib import Path
from playwright.sync_api import sync_playwright
from build_evidence_dashboard import patch_solar
ROOT=Path(__file__).resolve().parent
OUT=Path('esa-evidence-browser.json');checks=[]
def check(name,ok,detail=None):
 checks.append(dict(check=name,passed=bool(ok),detail=detail))
 OUT.write_text(json.dumps({'checks':checks},indent=2))
 if not ok:raise AssertionError(name)
def main():
 with sync_playwright() as p:
  b=p.chromium.launch(executable_path=os.environ.get('CHROME_PATH') or shutil.which('google-chrome') or shutil.which('chromium'),args=['--no-sandbox','--disable-dev-shm-usage','--js-flags=--max-old-space-size=512'])
  ctx=b.new_context(viewport={'width':1100,'height':850});pg=ctx.new_page();errors=[];requests=[]
  pg.on('pageerror',lambda e:errors.append(str(e)))
  pg.on('request',lambda r:requests.append({'url':r.url,'authorization':bool(r.headers.get('authorization'))}))
  server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(http.server.SimpleHTTPRequestHandler,directory=str(ROOT)))
  threading.Thread(target=server.serve_forever,daemon=True).start()
  try:
   pg.goto('http://127.0.0.1:'+str(server.server_port)+'/dashboard-services.js',wait_until='domcontentloaded')
   pg.set_content('<style>body{background:#102333;color:#dce9ef;font-family:Arial}.fd-wall-tile-body{width:640px;height:360px;overflow:hidden}.fd-product-frame{height:100%;min-height:0}#model{width:960px}</style><div class="fd-wall-tile-body"><div id="target" class="fd-product-frame"></div></div><div id="model"></div>')
   pg.evaluate('window.SpaceWxSolarServices={handles:()=>false,mount:()=>{},mergeFlareRegions:r=>r,mountIdentification:()=>{}}')
   pg.add_script_tag(content=patch_solar((ROOT/'dashboard-services.js').read_text()))
   pg.add_script_tag(content=(ROOT/'solar-model-evidence.js').read_text())
   pg.wait_for_function('SpaceWxSolarEvidence.data!==null',timeout=30000)
   d=pg.evaluate('SpaceWxSolarEvidence.data')
   for key in ['cactus','solardemon']:
    x=d['products'].get(key,{})
    check(key+' Live Collection Is Valid',x.get('status')=='ok',{'count':len(x.get('events',[])),'observed_at':x.get('observed_at'),'table_rows_parsed':x.get('table_rows_parsed'),'major_rows_recognized':x.get('major_rows_recognized')})
   check('Solar Demon M1+ Filter',all(e['estimated_class'][0] in ('M','X') for e in d['products']['solardemon']['events']))
   counts={m['body']:len(m.get('footpoints',{}).get('points',[])) for m in d['products']['connectivity']['models']}
   check('Numeric Earth Footpoints Published',counts.get('EARTH',0)>0,counts)
   for mount in ['mountSolarmap','mountHoles','mountConnectivity','mountHapi']:
    pg.evaluate('(m)=>{window.stop?.();document.getElementById("target").replaceChildren();window.stop=SpaceWxSolarFeed[m](document.getElementById("target"));}',mount)
    pg.wait_for_function('document.querySelector("#target [data-status]")?.textContent!=="Loading…"')
    check(mount+' Live Data Visible',pg.locator('#target [data-status]').inner_text()!='Unavailable')
    if mount in ('mountSolarmap','mountConnectivity'):
     pg.wait_for_function('Array.from(document.querySelectorAll("#target [data-view] img")).length>0&&Array.from(document.querySelectorAll("#target [data-view] img")).every(x=>x.complete&&x.naturalWidth>0)')
     check(mount+' Live Images Decode',True)
    for w,h in [(320,260),(640,360),(960,480)]:
     pg.evaluate('([w,h])=>{const p=document.querySelector(".fd-wall-tile-body");p.style.width=w+"px";p.style.height=h+"px"}',[w,h]);pg.wait_for_timeout(150)
     sizes=pg.evaluate('''()=>{const p=document.querySelector('.fd-wall-tile-body').getBoundingClientRect(),r=document.querySelector('#target .wx-esa').getBoundingClientRect(),v=document.querySelector('#target [data-view]').getBoundingClientRect();return {viewWidth:v.width,viewHeight:v.height,bottomOverflow:r.bottom-p.bottom};}''')
     check(mount+f' Fits {w}x{h}',sizes['viewWidth']>100 and sizes['viewHeight']>60 and sizes['bottomOverflow']<=1.5,sizes)
    if mount=='mountSolarmap':
     check('Unfiltered Solar Demon SVG Layer Removed',pg.locator('#target input[value="flares_solardemon"]').count()==0)
     pg.locator('#target .esa-layer-menu summary').click();pg.mouse.click(1090,820)
     check('Layer Menu Closes Outside',pg.locator('#target .esa-layer-menu[open]').count()==0)
   for kind in ['holes','flares','cme']:
    pg.evaluate('(kind)=>{window.ms?.();document.getElementById("model").replaceChildren();window.ms=SpaceWxSolarEvidence.mount(document.getElementById("model"),kind)}',kind)
    pg.wait_for_function('document.querySelector("#model [data-content]")?.textContent!=="Loading…"')
    check(kind+' Live Source Panel Renders',not pg.locator('#model [data-error]').count() and pg.locator('#model [data-content]').inner_text()!='Unavailable')
    if kind=='holes':check('SIDC Centers Display Without Invented Boundaries',pg.locator('#model svg [data-hole]').count()==len(d['products']['holes']['run']['Detections']))
   check('No New Runtime Errors',not errors,errors)
   check('No Browser Authentication Headers',not any(x['authorization'] for x in requests))
   check('No Browser Login Or Token Request',not any('sso.s2p.esa.int' in x['url'] for x in requests))
   OUT.write_text(json.dumps({'checked_at':d['checked_at'],'checks':checks,'source_mode':'actual published current data; isolated provider/model evidence modules'},indent=2))
  finally:
   b.close();server.shutdown()
if __name__=='__main__':main()
