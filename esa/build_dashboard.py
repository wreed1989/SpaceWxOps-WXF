#!/usr/bin/env python3
"""Patch the latest complete Solar Integrated HTML without reserializing it.
Usage: python esa/build_dashboard.py source.html destination.html
The older repository dashboard is deliberately rejected to avoid regression.
"""
from pathlib import Path
import sys,re,hashlib,json

def build(source,destination):
 source=Path(source);destination=Path(destination);html=source.read_text()
 if 'id="esaSolarDelivery"' in html:raise ValueError('Input already patched')
 match=re.search(r'(<script\b[^>]*\bid=[\"\']solarProviderServices[\"\'][^>]*>)(.*?)(</script\s*>)',html,re.S|re.I)
 if not match:raise ValueError('Use the complete Solar Integrated baseline, not the older repository dashboard')
 module=match[2]
 def replace(old,new):
  nonlocal module
  if module.count(old)!=1:raise ValueError('Patch anchor missing or ambiguous: '+old[:85])
  module=module.replace(old,new,1)
 hooks={
  'async function readText(original,{ttl=300000,force=false,signal}={}){':'if(window.SpaceWxSolarFeed&&new URL(original).searchParams.get("component")!=="archive")return window.SpaceWxSolarFeed.readText(original,{force});',
  "function mountSolarmap(parent,{kind='all'}={}){":'if(window.SpaceWxSolarFeed)return window.SpaceWxSolarFeed.mountSolarmap(parent,{kind});',
  'function mountHoles(parent){':'if(window.SpaceWxSolarFeed)return window.SpaceWxSolarFeed.mountHoles(parent);',
  'function parseFlareXML(text,provider){':'if(window.SpaceWxSolarFeed)return window.SpaceWxSolarFeed.parseFlareXML(text,provider);',
  'async function loadKsoFrames(source){':'if(window.SpaceWxSolarFeed)return window.SpaceWxSolarFeed.ksoFrames(source);',
  'function mountConnectivity(parent){':'if(window.SpaceWxSolarFeed)return window.SpaceWxSolarFeed.mountConnectivity(parent);',
  'function mountEUHFORIA(parent){':'if(window.SpaceWxSolarFeed)return window.SpaceWxSolarFeed.mountEUHFORIA(parent);',
  'function mountDataAccess(parent){':'if(window.SpaceWxSolarFeed)return window.SpaceWxSolarFeed.mountHapi(parent);',
 }
 for anchor,extra in hooks.items():replace(anchor,anchor+extra)
 replace('function currentForecast(r,now=Date.now()){','function currentForecast(r,now=Date.now()){if(r.webGuidance)return window.SpaceWxSolarFeed.recentGuidance(r,now);')
 replace('x.region===ar&&currentForecast(x,now)','(window.SpaceWxSolarFeed?window.SpaceWxSolarFeed.matchRegion(x.region,ar):x.region===ar)&&currentForecast(x,now)')
 replace('flareStore[provider]={...parsed,source,at:r.at,status:','flareStore[provider]={...parsed,source:r.source||source,at:r.at,status:')
 replace("const AEFFORT='https://a-effort.academyofathens.gr/prod/api/index.php';","const AEFFORT='https://a-effort-astro-noa-gr.content.swe.s2p.esa.int/prod/api/index.php';")
 replace("source:provider==='sidc'?'SIDC S109b Direct XML':'A-EFFort S124 Direct XML',note:","source:provider==='sidc'?'SIDC S109b Provider XML':r.webGuidance?'A-EFFort Published Web Guidance':'A-EFFort S124 Provider XML',note:r.webGuidance?`Published probabilities from input magnetogram ${r.referenceTime}. Explicit issue and validity times are not supplied by this web feed. Shown as recent guidance, not a formally window-matched forecast. No probabilities or dates were synthesized. Not added to ensemble training or verification.`:")
 replace("quality:'Published Provider Forecast'","quality:r.webGuidance?'Published Web Guidance · Window Not Supplied':'Published Provider Forecast'")
 replace("parsed.records.some(x=>currentForecast(x))?'Current 24-Hour Forecast'","parsed.records.some(x=>currentForecast(x))?(parsed.records.some(x=>x.webGuidance)?'Recent Published Web Guidance':'Current 24-Hour Forecast')")
 replace("s.records.some(x=>currentForecast(x))?'Current 24-Hour Forecast'","s.records.some(x=>currentForecast(x))?(s.records.some(x=>x.webGuidance)?'Recent Published Web Guidance':'Current 24-Hour Forecast')")
 replace("${currentForecast(r)?'Current 24-Hour Forecast':'Archive / Outside Current 24-Hour Window'}","${window.SpaceWxSolarFeed.forecastLabel(r,currentForecast(r))}")
 replace('${esc(r.issued)}</td><td>${esc(r.validStart)}<small>to ${esc(r.validEnd)}</small>',"${esc(r.referenceTime||r.issued)}${r.webGuidance?'<small>Input Magnetogram</small>':''}</td><td>${r.webGuidance?'Not Published':esc(r.validStart)}${r.webGuidance?'':'<small>to '+esc(r.validEnd)+'</small>'}")
 module=module.replace('<th>Issued · UTC</th>','<th>Issue / Reference · UTC</th>').replace("'Source XML'","'Source Data'")
 module=module.replace('Only explicit current 24-hour M1+/X1+ forecasts are admitted to the existing comparison, under SIDC or the single A-EFFort method.','SIDC retains its explicit current 24-hour window. When A-EFFort XML is expired, recent published web probabilities appear under the same A-EFFort method with the input-magnetogram reference time; their missing issue/validity timestamps remain missing. This comparison does not retrain or reweight an ensemble.')
 anchor="const form=root.querySelector('[data-flare-archive]');async function inspect"
 replacement="""const form=root.querySelector('[data-flare-archive]');if(window.SpaceWxSolarFeed&&!config.gateway){const controls=form.querySelector('.wx-solar-controls');for(const el of controls.querySelectorAll('label'))if(!el.contains(form.elements.provider))el.hidden=true;const b=controls.querySelector('button');b.type='button';b.textContent='Open Provider Archive';b.onclick=()=>window.open(form.elements.provider.value==='sidc'?'https://esa-swe-services-sidc-be.content.swe.s2p.esa.int/prod/WEB/index.php?pc=S109&psc=b&component=archive':'https://a-effort-astro-noa-gr.content.swe.s2p.esa.int/prod/web/archive.php','_blank','noopener');}async function inspect"""
 replace(anchor,replacement)
 folder=Path(__file__).parent;bridge='\n'.join((folder/name).read_text() for name in ('dashboard-services.js','dashboard-guidance.js'))
 if '</script' in bridge.lower():raise ValueError('Unsafe script terminator')
 new='<script id="esaSolarDelivery">\n'+bridge+'\n</script>\n'+match[1]+module+match[3]
 updated=html[:match.start()]+new+html[match.end():]
 destination.parent.mkdir(parents=True,exist_ok=True);destination.write_text(updated)
 script_pattern=r'<script\b([^>]*)>(.*?)</script\s*>'
 old=list(re.finditer(script_pattern,html,re.S|re.I));new=list(re.finditer(script_pattern,updated,re.S|re.I))
 old_other=[m[0] for m in old if not re.search(r'\bid=[\"\']solarProviderServices[\"\']',m[1])]
 new_other=[m[0] for m in new if not re.search(r'\bid=[\"\'](?:solarProviderServices|esaSolarDelivery)[\"\']',m[1])]
 if old_other!=new_other:raise ValueError('Unintended change outside solar delivery scripts')
 report={'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'output_sha256':hashlib.sha256(destination.read_bytes()).hexdigest(),'hook_count':len(hooks),'unchanged_script_blocks':len(old_other),'added_script':'esaSolarDelivery','changed_script':'solarProviderServices','forecast_window_policy':'A-EFFort web issue/valid dates are not fabricated; recent input-magnetogram reference is explicit.'}
 destination.with_suffix('.build.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2));return report
if __name__=='__main__':build(sys.argv[1],sys.argv[2])
