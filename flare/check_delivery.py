"""Validate exact output assets and the workspace's live anonymous delivery.
The small integration document is not the complete operational dashboard; the
complete dashboard has a separate captured-response browser regression suite.
"""
from pathlib import Path
import argparse, hashlib, json, mimetypes
from PIL import Image
from playwright.sync_api import sync_playwright

BASE='https://raw.githubusercontent.com/wreed1989/SpaceWxOps-WXF/flare-live/'

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,default=Path('flare-output'));ap.add_argument('--live',action='store_true');args=ap.parse_args()
    output=args.output;checks=[]
    def test(name,ok,detail=None):
        checks.append({'name':name,'passed':bool(ok),'detail':detail})
        (output/'delivery-tests.json').write_text(json.dumps({'mode':'Live anonymous Chromium delivery' if args.live else 'Captured-output Chromium integration','checks':checks},indent=2))
        if not ok:raise AssertionError(name)
    files=json.loads((output/'files.json').read_text());decoded=0
    for f in files:
        p=(output/f['path']).resolve()
        if not p.is_relative_to(output.resolve()):raise ValueError('Unsafe published path')
        if hashlib.sha256(p.read_bytes()).hexdigest()!=f['sha256']:raise ValueError('Asset hash mismatch '+f['path'])
        if p.suffix=='.jpg':
            with Image.open(p) as im:
                im.load(); expected=(1024,1024) if p.name=='disk.jpg' else (896,896)
                if im.size!=expected:raise ValueError('Incorrect native crop '+str(p))
                decoded+=1
    test('All Original Asset Hashes Match',True,len(files));test('All Published Images Decode At Declared Size',True,decoded)
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,args=['--no-sandbox']);page=browser.new_page(viewport={'width':1300,'height':1000});page.set_default_timeout(60000)
        if not args.live:
            def route(r):
                rel=r.request.url.split(BASE,1)[-1].split('?',1)[0]
                p=output/rel
                if r.request.url.startswith(BASE) and p.is_file():r.fulfill(path=str(p),content_type=mimetypes.guess_type(str(p))[0] or 'application/octet-stream',headers={'Access-Control-Allow-Origin':'*'})
                else:r.abort()
            page.route('**/*',route)
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.set_content('<main class="sf-workspace"><select id="flareGuidanceRegion"><option value="full-disk">Full Disk</option></select><div id="fdSunspotBrowser"></div><div id="fdFlareAnalysis"></div></main>')
        payload=page.evaluate('''async base=>{const r=await fetch(base+'latest.json?t='+Date.now(),{credentials:'omit',cache:'no-store'});if(!r.ok)throw Error('Published feed unavailable');return await r.json();}''',BASE)
        test('Browser Reads Published JSON',payload.get('schema')=='solar-flare-evidence-v1')
        test('Completed Outcome Database Updated',payload.get('database',{}).get('status')=='Updated')
        test('No Retraining Claimed',payload['database'].get('retrained') is False)
        test('Model Input Data Present',len(payload.get('model',{}).get('regions',[]))>0)
        guidance=page.evaluate('''async base=>{const r=await fetch(base+'guidance.json?t='+Date.now());if(!r.ok)throw Error('Guidance unavailable');return r.json();}''',BASE)
        # Map the real backend schema to the dashboard's documented snapshot API.
        snap={'issued':guidance['issued'],'validStart':guidance['valid_start'],'validEnd':guidance['valid_end'],'regions':[]}
        for region in guidance['regions']:
            m=region.get('members',{}).get('sharpmag')
            if m is not None:m={**m,'validStart':m.get('valid_start',guidance['valid_start']),'validEnd':m.get('valid_end',guidance['valid_end'])}
            snap['regions'].append({'id':region['id'],'members':{'sharpmag':m} if m else {},'mcintosh':region.get('mcintosh')})
        page.evaluate('(s)=>window.__SPACEWXOPS_FLARE_SNAPSHOT__=s',snap)
        page.add_script_tag(content=Path(__file__).with_name('workspace.js').read_text())
        page.evaluate('()=>SpaceWxFlareWorkspace.load(true)');page.wait_for_function('!!SpaceWxFlareWorkspace.data')
        test('Workspace Receives Current Published Feed',page.evaluate('()=>SpaceWxFlareWorkspace.api.fresh(SpaceWxFlareWorkspace.data.checked_at)'))
        ids=page.evaluate('()=>SpaceWxFlareWorkspace.api.currentRegions().map(r=>r.id)');test('Current Numbered Regions Render',len(ids)>0,len(ids))
        target=next((i for i in ids if any(r.get('NOAA_REGION')==int(i[2:]) for r in payload['model']['regions'])),ids[0])
        page.evaluate('(ids)=>{const s=document.getElementById("flareGuidanceRegion");for(const id of ids){const o=document.createElement("option");o.value=id;o.textContent=id;s.appendChild(o);}}',ids)
        page.select_option('#flareGuidanceRegion',target);page.evaluate('()=>SpaceWxFlareWorkspace.renderAnalysis()')
        page.wait_for_function('(()=>{const a=[...document.querySelectorAll("[data-sf-images] img")];return a.length===2&&a.every(i=>i.naturalWidth===896);})()')
        test('Anonymous HMI Continuum And Magnetogram Images Decode',True,target)
        test('Actual Multi-Frame Slider Populated',int(page.locator('[data-sf-frame]').get_attribute('max'))>0)
        page.locator('[data-sf-frame]').fill('0');page.locator('[data-sf-frame]').dispatch_event('input');page.wait_for_timeout(200)
        test('First Actual Frame Selectable',page.locator('[data-sf-frame]').input_value()=='0')
        page.locator('[data-sf-play]').click();page.wait_for_timeout(1100);test('Playback Advances Real Frames',page.locator('[data-sf-frame]').input_value()!='0');page.locator('[data-sf-play]').click()
        page.locator('[data-sf-channel]').select_option('aia171');page.wait_for_function('document.querySelector("[data-sf-images] img")?.naturalWidth===896');test('AIA Native Crop Decodes',True)
        for width in [1300,700,390]:
            page.set_viewport_size({'width':width,'height':1000});page.wait_for_timeout(100)
            test('Responsive Width '+str(width),page.locator('.sf-workspace').evaluate('e=>e.scrollWidth<=e.clientWidth+2'))
        # Explicit fixture tests of missing, genuine zero, stale, and failed-cycle states.
        checks_js=page.evaluate('''()=>{const s=__SPACEWXOPS_FLARE_SNAPSHOT__,api=SpaceWxFlareWorkspace.api,old=JSON.parse(JSON.stringify(s));
          const id=document.getElementById('flareGuidanceRegion').value,r=s.regions.find(r=>r.id===id);r.members.sharpmag={m1:0,x1:0,issued:new Date(Date.now()-3600000).toISOString(),validEnd:new Date(Date.now()+3600000).toISOString()};
          const zero=api.modelMember(id)?.m1===0;r.members.sharpmag.validEnd='2020-01-01T00:00:00Z';const expired=api.modelMember(id)===null;
          r.members.sharpmag.validEnd=new Date(Date.now()+3600000).toISOString();s.model={generationStatus:{used_previous_forecast:true}};const retained=api.modelMember(id)===null;
          window.__SPACEWXOPS_FLARE_SNAPSHOT__=old;return {zero,expired,retained,path:api.safeAsset('../secret')==='',future:!api.fresh('2100-01-01')};}''')
        for key,ok in checks_js.items():test('Controlled Guard '+key,ok)
        test('No Unhandled Workspace Errors',not errors,errors)
        page.screenshot(path=str(output/'workspace-delivery.png'),full_page=True);browser.close()
    print(json.dumps({'checks':len(checks),'passed':sum(x['passed'] for x in checks),'decoded_images':decoded},indent=2))

if __name__=='__main__':main()
