#!/usr/bin/env python3
"""Build on the exact reviewed Solar Flare HTML. Do not use the old root HTML."""
from pathlib import Path
import argparse,hashlib,json,re
BASE_SHA='c0a6ba01badcf866615da4ad9c8fd832605e9220769ef5ad7adc51d58f54d4a0'
def assemble(module:str,source:Path):
    s=module.strip()+'\n'
    funcs=(source/'renderers.js').read_text()
    s=s.replace("lastRegion='';", "lastRegion='',tab='overview',auditMode='coverage';")
    def replace(name,new):
        nonlocal s
        m=re.search(r'^function '+name+r'\(.*?(?=^function |^async function |^document\.|^window\.|^setInterval\(|^\}\)\(\);)',s,re.M|re.S)
        if not m:raise RuntimeError(name)
        s=s[:m.start()]+new+'\n'+s[m.end():]
    for name in ['renderBrowser','renderAnalysis']:
        m=re.search(r'^function '+name+r'\(.*?(?=^function |\Z)',funcs,re.M|re.S)
        replace(name,m.group(0).rstrip())
    for m in re.finditer(r'^function (\w+)\(.*?(?=^function |\Z)',funcs,re.M|re.S):
        if m.group(1) not in ['renderBrowser','renderAnalysis']:s=s.replace('function renderBrowser()',m.group(0)+'\nfunction renderBrowser()',1)
    css=(source/'workspace.css').read_text().replace('`','\\`')
    replace('style',"function style(){if(document.getElementById('sfWorkspaceStyle'))return;const s=document.createElement('style');s.id='sfWorkspaceStyle';s.textContent=`"+css+"`;document.head.appendChild(s);}")
    s=s.replace('[data-sf-catalog],[data-sf-zoom]', '[data-sf-catalog],[data-sf-zoom],[data-sf-tab],[data-sf-audit]')
    s=s.replace("if(b.hasAttribute('data-sf-zoom'))", "if(b.dataset.sfTab){tab=b.dataset.sfTab;stopLoop();queue();return;}if(b.dataset.sfAudit){auditMode=b.dataset.sfAudit;queue();return;}\n if(b.hasAttribute('data-sf-zoom'))")
    s=s.replace("window.addEventListener('spacewxops:flare-guidance',queue);", "document.addEventListener('keydown',e=>{const t=e.target.closest('[data-sf-tab]');if(!t||!['ArrowLeft','ArrowRight','Home','End'].includes(e.key))return;e.preventDefault();const items=Array.from(t.parentNode.querySelectorAll('[data-sf-tab]')),i=items.indexOf(t),next=e.key==='Home'?0:e.key==='End'?items.length-1:(i+(e.key==='ArrowRight'?1:-1)+items.length)%items.length;tab=items[next].dataset.sfTab;stopLoop();renderAnalysis();document.getElementById('sf-tab-'+tab)?.focus();});\nwindow.addEventListener('spacewxops:flare-guidance',queue);")
    s=s.replace("version:'2026.09.27.1'", "version:'2026.09.27.2'")
    return s

def build(base:Path,output:Path,source:Path,audit:Path):
    raw=base.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=BASE_SHA:raise ValueError('Expected reviewed SpaceWxOps_Solar_Flare.html baseline; refusing an unknown/older build')
    s=raw.decode();original=s
    old_module=re.search(r'<script\s+id=["\']solarFlareWorkspace["\'][^>]*>(.*?)</script>',s,re.S)
    if not old_module:raise ValueError('Solar Flare source missing')
    module=assemble(old_module[1],source)
    s,n=re.subn(r'(<script\s+id=["\']solarFlareWorkspace["\'][^>]*>).*?(</script>)',lambda m:m[1]+module+m[2],s,count=1,flags=re.S)
    if n!=1:raise ValueError('Solar Flare workspace not found')
    old='<div class="sf-top"><section id="fdFlareGuidanceSlot"></section><section id="fdSunspotBrowser"></section></div>\n        <section id="fdFlareAnalysis"></section>'
    new='<section id="fdSunspotBrowser"></section>\n        <div class="sf-desk"><section id="fdFlareGuidanceSlot"></section><section id="fdFlareAnalysis"></section></div>'
    if s.count(old)!=1:raise ValueError('Expected Solar Flare stage layout once')
    s=s.replace(old,new)
    move="${field('opticalClass','Optical Class','text')}${select('radio','Radio Sweep',[['unknown','Unknown'],['none','Neither'],['II','Type II'],['IV','Type IV'],['II+IV','Both']])}"
    if s.count(move)!=1:raise ValueError('Expected one optical/radio field pair')
    s=s.replace(move,'')
    anchor="${field('integral','Integrated X-Ray Flux (J/m²)','number','min=\"0\" step=\"any\"')}"
    if s.count(anchor)!=1:raise ValueError('Expected one SEP primary field anchor')
    s=s.replace(anchor,anchor+'\n<div class="wx-sep-field-pair">'+move+'</div>')
    s=s.replace('The integrated flux supports the conditional peak estimate. Optical class and radio sweep are retained in the event record; they do not change this fitted occurrence model.','Integrated flux supports the conditional peak estimate. Optical class and radio sweep are recorded inputs, not predictors of this fitted occurrence model.')
    for old,new in [('Coronal Hole / HSS','Coronal Hole | HSS'),('SEP / Proton','SEP | Protons')]:s=s.replace(old,new)
    a=json.loads(audit.read_text());encoded=json.dumps(a,separators=(',',':'),allow_nan=False).replace('<','\\u003c')
    s=s.replace('<script id="solarFlareWorkspace">','<script type="application/json" id="wxfFlareReassessment">'+encoded+'</script>\n<script id="solarFlareWorkspace">')
    if 'id="wxfFlareReassessment"' not in s:raise ValueError('Audit insertion failed')
    output.write_text(s)
    blocks=lambda t:re.findall(r'<script\b([^>]*)>(.*?)</script>',t,re.S|re.I)
    before=blocks(original);after=[(a,b) for a,b in blocks(s) if 'wxfFlareReassessment' not in a]
    if len(before)!=len(after):raise ValueError('Unexpected script insertion/removal')
    unchanged=sum(a==c and b==d for (a,b),(c,d) in zip(before,after))
    report={'baseline_sha256':hashlib.sha256(raw).hexdigest(),'output_sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'bytes':output.stat().st_size,'original_script_blocks':len(before),'unchanged_original_blocks':unchanged,'changed_original_blocks':[re.search(r'id=["\']([^"\']+)',a).group(1) if re.search(r'id=["\']([^"\']+)',a) else a for (a,b),(c,d) in zip(before,after) if a!=c or b!=d],'added_audit_blocks':1}
    output.with_suffix('.preservation.json').write_text(json.dumps(report,indent=2));return report
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('base',type=Path);p.add_argument('output',type=Path);p.add_argument('--source',type=Path,default=Path(__file__).parent);p.add_argument('--audit',type=Path,required=True);a=p.parse_args();print(json.dumps(build(a.base,a.output,a.source,a.audit),indent=2))
