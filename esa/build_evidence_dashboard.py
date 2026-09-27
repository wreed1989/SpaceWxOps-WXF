#!/usr/bin/env python3
"""Patch the complete Solar Live conversation artifact, preserving other scripts."""
from pathlib import Path
import hashlib,json,re,sys
ROOT=Path(__file__).resolve().parent
BASE_SHA='c154016d0a01049565816a45464034e807da848b573c1d9d24d88b1d621672a4'
PAT=re.compile(r'<script\b([^>]*)>(.*?)</script\s*>',re.S|re.I)
def once(text,old,new):
 if text.count(old)!=1: raise ValueError('Expected one source anchor: '+old[:110])
 return text.replace(old,new,1)
def patch_solar(s):
 s=once(s,"['flares_solardemon','Solar Demon Flares'],",'')
 s=once(s,"['coronal_holes_sidc','SIDC Coronal Holes']","['coronal_holes_sidc','SIDC CH Boundary Overlay']")
 s=once(s,"['coronal_holes_sidc','flares_solardemon']","['coronal_holes_sidc']")
 s=once(s,"doc=safeSVG(current.svg);for(const [id]of LAYERS)","doc=safeSVG(current.svg);doc.getElementById('group_current_flares_solardemon')?.setAttribute('display','none');for(const [id]of LAYERS)")
 s=s.replace("?' · Unavailable':''","?' · Not Supplied':''")
 s=once(s,"+' · '+rows.length+' Detections'","+' · '+rows.length+' Detections · Detection Catalog Available'")
 return s

def build(source,dest):
 original=Path(source).read_bytes()
 if hashlib.sha256(original).hexdigest()!=BASE_SHA: raise ValueError('Use the complete SpaceWxOps_Solar_Live.html baseline; do not substitute the old repository root HTML.')
 text=original.decode();changed=[];unchanged=[]
 def patch(m):
  attrs,s=m.groups();idmatch=re.search(r'\bid=["\']([^"\']+)',attrs);sid=idmatch[1] if idmatch else 'anonymous'
  before=s
  if sid=='esaSolarDelivery':s=patch_solar(s)
  elif sid=='fdDeskScript':
   s=once(s,'["solar.sidc-holes", "SIDC Coronal Holes", "DETECTIONS"],','["solar.sidc-holes", "SIDC Coronal Holes", "DETECTIONS"],\n      ["solar.solardemon", "Solar Demon · M1+", "DETECTIONS"],\n      ["solar.cactus", "CACTus CME Detections", "DETECTIONS"],')
  elif sid=='cmeSolarWindProduct':
   s=once(s,'<div class="wx-cme-grid">','<div data-swe-cme-evidence></div><div class="wx-cme-grid">')
   pos=s.index('window.SpaceWxSolarServices?.mountEUHFORIA')
   # Insert at the start of the containing statement, preserving its existing binding.
   line=s.rfind('\n',0,pos)+1
   s=s[:line]+"  const stopEvidence=window.SpaceWxSolarEvidence?.mount(root.querySelector('[data-swe-cme-evidence]'),'cme');\n"+s[line:]
   s=once(s,'disposed=true;stop();stopScoreboard();','disposed=true;stop();stopScoreboard();stopEvidence?.();')
  elif sid=='monitorLayoutPolicy':
   anchor='if(key === "solar.cycle")'
   if anchor not in s:anchor='if (key === "solar.cycle")'
   if anchor not in s:
    match=re.search(r'if\s*\([^\n]*solar\.cycle[^\n]*\)',s)
    if not match:raise ValueError('Tile policy anchor missing')
    anchor=match[0]
   s=once(s,anchor,"if(/^(solar\\.(solarmap|sidc-holes|solardemon|cactus)|model\\.euhforia|data\\.esa-hapi)$/.test(key))return {cols:12,rows:30};\n    "+anchor)
  (changed if s!=before else unchanged).append(sid)
  return m.group(0).replace(before,s,1) if s!=before else m.group(0)
 text=PAT.sub(patch,text)
 group=re.search(r'<optgroup label="Kanzelhöhe Hα">(.*?)</optgroup>',text,re.S)
 if not group:raise ValueError('H-alpha optgroup missing')
 text=text[:group.start()]+group[1]+text[group.end():]
 module=(ROOT/'solar-model-evidence.js').read_text()
 if '</script' in module.lower():raise ValueError('Unsafe inline script closing tag')
 text=once(text,'<script id="geomagProductView">','<script id="solarModelEvidence">\n'+module+'\n</script>\n<script id="geomagProductView">')
 Path(dest).write_text(text)
 report={'baseline_sha256':BASE_SHA,'output_sha256':hashlib.sha256(text.encode()).hexdigest(),'changed_script_ids':changed,'unchanged_script_blocks':len(unchanged),'new_script':'solarModelEvidence','output_bytes':len(text.encode())}
 Path(dest).with_suffix('.build.json').write_text(json.dumps(report,indent=2))
 return report
if __name__=='__main__':
 print(json.dumps(build(sys.argv[1],sys.argv[2]),indent=2))
