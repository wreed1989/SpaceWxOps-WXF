"""Build the coordinated Solar Flare workspace from the reviewed complete HTML.
Exact substitutions fail closed so an unrelated/older base is not silently patched.
"""
from pathlib import Path
import argparse, re, hashlib, json

BASE_SHA='db459baa888202fb94b62fdd0e46940c2f684cbd04cf98d6a5ba01f9baa89938'

def replace_once(text, old, new):
    if text.count(old)!=1: raise ValueError(f'Expected one match, found {text.count(old)}: {old[:90]}')
    return text.replace(old,new,1)

def function(text,name,new,indent=2):
    start=re.search(r'^'+(' '*indent)+r'(?:async )?function '+re.escape(name)+r'\(',text,re.M)
    if not start: raise ValueError('Missing function '+name)
    tail=re.search(r'^'+(' '*indent)+r'(?:async )?function ',text[start.end():],re.M)
    if not tail: raise ValueError('Missing next function after '+name)
    end=start.end()+tail.start()
    return text[:start.start()]+new+'\n\n'+text[end:]

def build(src,module,guidance=None):
    if hashlib.sha256(src.encode()).hexdigest()!=BASE_SHA: raise ValueError('This build requires the reviewed SpaceWxOps_Solar_Evidence.html base')
    original=list(re.finditer(r'<script\b([^>]*)>(.*?)</script\s*>',src,re.S|re.I))
    replacements={}
    if guidance is not None:
        if not guidance.get("issued") or not guidance.get("valid_end") or not guidance.get("regions"): raise ValueError("Invalid guidance snapshot")
        replacements[5]="\nwindow.FLARE_GUIDANCE_PAYLOAD = "+json.dumps(guidance,ensure_ascii=True).replace("<","\\u003c")+";\n"
    text=original[6][2]
    text=replace_once(text,'label: "WXF SHARP · RESEARCH",','label: "WXF",')
    text=replace_once(text,'const FLARE_GUIDANCE_PRIMARY_KEYS = new Set(["ensemble", "mcstat", "evolp", "sharpmag", "swpc", "sidc", "ccmc_aeffort"]);','const FLARE_GUIDANCE_PRIMARY_KEYS = new Set(["mcstat", "evolp", "sharpmag", "swpc", "sidc", "ccmc_aeffort"]);')
    text=re.sub(r'        \{\n          key: "ensemble",.*?\n        \},\n','',text,count=1,flags=re.S)
    text=function(text,'completeFlareGuidanceMembers','''      function completeFlareGuidanceMembers(regions) {
        // Only published probabilities are displayed. Do not create a browser
        // consensus or a synthetic full-disk maximum from regional benchmarks.
        const list = Array.isArray(regions) ? regions : [];
        list.forEach(region => { region.members ||= {}; delete region.members.ensemble; });
        return list;
      }''',6)
    text=function(text,'builtInSolarRegionHasSunspots','''      function builtInSolarRegionHasSunspots(row) {
        // Include currently numbered plages as well as spotted regions. Their
        // identity can still have flare guidance or share a measured HARP.
        const id = canonicalNoaaRegionNumber(row?.region);
        const position = String(row?.location || '').match(/[EW](\\d{1,3})/i);
        const lon = toNumber(row?.longitude);
        return Number.isFinite(id) && (position ? Number(position[1])<=90 : Number.isFinite(lon)&&Math.abs(lon)<=90);
      }''',6)
    text=replace_once(text,'''        const allDisplayRows = eligibleRows.filter((definition) =>
          FLARE_GUIDANCE_PRIMARY_KEYS.has(definition.key)
          || flareGuidanceMemberHasData(members[definition.key])
        );''','''        const allDisplayRows = eligibleRows.filter((definition) => {
          const member = members[definition.key];
          if (!flareGuidanceMemberHasData(member)) return false;
          if (flareGuidanceDefinitionStatus(payload, definition, member).state !== "available") return false;
          const m = toNumber(member?.m1), x = toNumber(member?.x1);
          return !(Number.isFinite(m) && Number.isFinite(x) && x > m);
        });''')
    text=replace_once(text,'''        const pinnedSwpc = allDisplayRows.find((definition) => definition.key === "swpc") || null;
        const comparisonRows = allDisplayRows.filter((definition) => definition.key !== "swpc");
        const pageSize = 5;
        const comparisonPageSize = pinnedSwpc ? pageSize - 1 : pageSize;''','''        const pinnedRows = ["swpc", "sharpmag"].map(key => allDisplayRows.find(row => row.key === key)).filter(Boolean);
        const comparisonRows = allDisplayRows.filter(row => !["swpc", "sharpmag"].includes(row.key));
        const pageSize = 5;
        const comparisonPageSize = pageSize - pinnedRows.length;''')
    text=replace_once(text,'const displayRows = [pinnedSwpc, ...comparisonPage].filter(Boolean);','const displayRows = [...pinnedRows, ...comparisonPage];')
    text=replace_once(text,'<tr class="${rowClass}" title="${escapeHtml(rowTitle)}">','<tr class="${rowClass}" data-flare-method="${definition.key}" title="${escapeHtml(rowTitle)}">')
    text=replace_once(text,"${escapeHtml(definition.label)}${status.state==='stale'?' · EXPIRED / RETAINED':member?.method==='morphology_fallback'?' · FALLBACK':''}","${escapeHtml(definition.label)}")
    text=replace_once(text,'SWPC pinned · Alternatives ${comparisonStart}–${comparisonEnd} of ${comparisonRows.length}','${page + 1} / ${pageCount}')
    text=replace_once(text,'setText("flareGuidanceHeader", "Next 24 h");','setText("flareGuidanceHeader", "M1+ / X1+");')
    text=replace_once(text,'method: source.method || null,','method: source.method || null,\n          componentId: source.component_id || source.componentId || null,')
    text=replace_once(text,'quality: flareSourceRoot.quality?.level || flareSourceRoot.quality || "research"','quality: flareSourceRoot.quality?.level || flareSourceRoot.quality || "research",\n            generationStatus: payload.generationStatus || null')
    text=function(text,'flareGuidanceValidText','''      function flareGuidanceValidText(selected, payload, liveSwpc) {
        const value = liveSwpc?.validStart && selected?.id === 'full-disk' ? liveSwpc : selected;
        const start = parseDate(value?.validStart || payload.validStart);
        const end = parseDate(value?.validEnd || payload.validEnd);
        const fmt = d => Number.isFinite(d.getTime()) ? d.toISOString().slice(0,16).replace('T',' ') : '';
        return fmt(start) && fmt(end) ? `${fmt(start)} – ${fmt(end)} UTC` : '';
      }''',6)
    text=replace_once(text,'const objectiveKeys = ["ensemble", "sharpmag", "mcstat", "evolp"];','const objectiveKeys = ["sharpmag", "mcstat", "evolp"];')
    text=text.replace('member?.issued ? `Issued ${formatAnyTime(member.issued)}` : "",','member?.issued ? `Issued ${parseDate(member.issued).toISOString().slice(0,16).replace("T"," ")} UTC` : "",')
    text=replace_once(text,'${escapeHtml(region.label)}</option>', '${escapeHtml(region.shortLabel || region.label)}</option>')
    replacements[6]=text
    s=original[45][2]
    s=replace_once(s,"const handles=k=>['solar.solarmap','solar.sidc-holes','model.euhforia','data.esa-hapi'].includes(k);","const handles=k=>['solar.solarmap','solar.sidc-holes','solar.connectivity','model.euhforia','data.esa-hapi'].includes(k);")
    s=replace_once(s,"function mount(parent,key){if(key==='solar.solarmap')", "function mount(parent,key){if(key==='solar.connectivity')return mountConnectivity(parent);if(key==='solar.solarmap')")
    replacements[45]=s
    s=original[52][2]
    s=re.sub(r'    connectivity: \{.*?\n    \},\n','',s,count=1,flags=re.S)
    s=replace_once(s,'["solar.solarmap", "SIDC Solarmap", "FEATURES"],','["solar.solarmap", "SIDC Solarmap", "FEATURES"],\n        ["solar.connectivity", "Magnetic Connectivity", "EVIDENCE"],')
    s=replace_once(s,'if (!modelAvailable(state.selectedModel)) state.selectedModel = "huxt";','if (state.selectedModel === "connectivity") state.selectedModel = "flare";\n    if (!modelAvailable(state.selectedModel)) state.selectedModel = "huxt";')
    s=re.sub(r'    if \(state.selectedModel === "connectivity"\) \{.*?\n    \}\n','',s,count=1,flags=re.S)
    s=function(s,'renderSunspotBrowser','''  function renderSunspotBrowser() { window.SpaceWxFlareWorkspace?.renderBrowser(); }''')
    s=function(s,'renderFlareAnalysis','''  function renderFlareAnalysis() { window.SpaceWxFlareWorkspace?.renderAnalysis(); }''')
    s=function(s,'renderFlareModel','''  function renderFlareModel(pipeline) {
    setWorkbench("MODEL", "Solar Flare", "", false);
    stage.innerHTML = `<div class="fd-model-layout">${modelNavigation()}
      <section class="fd-model-canvas sf-workspace">
        <div class="fd-panel-heading"><h2>Solar Flare</h2><button type="button" class="fd-button" data-sf-refresh>Refresh</button></div>
        <div class="sf-top"><section id="fdFlareGuidanceSlot"></section><section id="fdSunspotBrowser"></section></div>
        <section id="fdFlareAnalysis"></section>
      </section></div>`;
    mountProduct("forecast.flare", $("#fdFlareGuidanceSlot", stage), {bare:true,className:"fd-flare-live-guidance"});
    window.SpaceWxSolarServices?.refreshFlares();
    window.SpaceWxFlareWorkspace?.load();
    const card = document.getElementById("card-flare-guidance");
    if (card && typeof MutationObserver === "function") {
      flareWorkspaceObserver = new MutationObserver(syncFlareWorkspaceSummary);
      flareWorkspaceObserver.observe(card,{childList:true,subtree:true,characterData:true});
    }
    syncFlareWorkspaceSummary();
    setInspectorTitle("Solar Flare");
  }''')
    replacements[52]=s
    # Preserve every other script byte-for-byte except the two requested names.
    out=src
    for i in sorted(replacements,reverse=True):
        m=original[i];out=out[:m.start(2)]+replacements[i]+out[m.end(2):]
    out=replace_once(out,'<script id="fdDeskScript">','<script id="solarFlareWorkspace">\n'+module+'\n</script>\n<script id="fdDeskScript">')
    out=out.replace('Full Disk combines each independent HARP/region component once and reports coverage.','Full Disk combines each unique HARP/region component once under an independence assumption. It is not separately calibrated; coverage and fallbacks are reported.')
    out=out.replace('Solar Flare Probability','Solar Flare').replace('Coronal Hole / HSS Outlook','Coronal Hole / HSS')
    out=out.replace('id="flareGuidanceHeader">Next 24 h<','id="flareGuidanceHeader">M1+ / X1+<')
    forbidden=['OPERATIONAL GUIDANCE · NO RUN REQUIRED','SWPC is always the first benchmark. Numbered-region selection drives the forecast','Other methods retain their own valid windows']
    for v in forbidden:
        if v in out:raise ValueError('Removed text still present: '+v)
    return out

def main():
    ap=argparse.ArgumentParser();ap.add_argument('base',type=Path);ap.add_argument('output',type=Path);a=ap.parse_args()
    guidance_path=Path(__file__).resolve().parents[1]/'flare_guidance.json'
    text=build(a.base.read_text(),Path(__file__).with_name('workspace.js').read_text(),json.loads(guidance_path.read_text()) if guidance_path.exists() else None);a.output.write_text(text)
    print(json.dumps({'output':str(a.output),'bytes':a.output.stat().st_size,'sha256':hashlib.sha256(text.encode()).hexdigest()}))
if __name__=='__main__':main()
