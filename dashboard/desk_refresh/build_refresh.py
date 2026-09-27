from pathlib import Path
import re,json,hashlib,argparse
ROOT=Path(__file__).resolve().parent

def replace(s,a,b,n=1):
    if s.count(a)!=n: raise ValueError(f'Expected {n}, got {s.count(a)}: {a[:100]}')
    return s.replace(a,b)

def build(source,out,product):
    original=source.read_text(); html=original; changed={}
    def patch(ident,fn):
        nonlocal html
        pattern=r'(<script\b[^>]*\bid=[\"\']'+re.escape(ident)+r'[\"\'][^>]*>)([\s\S]*?)(</script\s*>)'
        m=re.search(pattern,html)
        if not m:raise ValueError(ident)
        body=fn(m[2]); assert not re.search(r'</script',body,re.I)
        html=html[:m.start(2)]+body+html[m.end(2):]
        changed[ident]={'oldSHA256':hashlib.sha256(m[2].encode()).hexdigest(),'newSHA256':hashlib.sha256(body.encode()).hexdigest()}
        return body
    def score(s):
        s=replace(s,"CACHE='spacewx-cme-scoreboard-v1';","CACHE='spacewx-cme-scoreboard-v1',MIRROR='https://raw.githubusercontent.com/wreed1989/SpaceWxOps-WXF/ops-live/cme-scoreboard.json';")
        s=replace(s,"const end=now.toISOString().slice(0,10)","const end=new Date(now.getTime()+86400000).toISOString().slice(0,10)")
        s=replace(s,"Number(!!a.arrival||a.noArrival)-Number(!!b.arrival||b.noArrival)||b.observed.localeCompare(a.observed)","b.observed.localeCompare(a.observed)")
        begin=s.index('  async function refresh(){');end=s.index('  function mount(root){',begin)
        s=s[:begin]+'''  function adopt(candidate){
    if(!candidate||!stamp(candidate.retrievedAt)||Date.parse(candidate.retrievedAt)>Date.now()+300000)return false;
    if(!Array.isArray(candidate.rows)||candidate.rows.some(r=>!r||!r.cmeID||!stamp(r.observedTime)))return false;
    if(!cached||Date.parse(candidate.retrievedAt)>=Date.parse(cached.retrievedAt)){
      cached=candidate;try{localStorage.setItem(CACHE,JSON.stringify(cached));}catch{}
      window.dispatchEvent(new Event('spacewx:cme-scoreboard'));
    }return true;
  }
  async function refresh(){
    if(inflight)return inflight;
    inflight=(async()=>{
      let received=0;
      await Promise.allSettled([MIRROR+'?_='+Math.floor(Date.now()/300000),...urls()].map(async url=>{
        const ctrl=new AbortController(),timer=setTimeout(()=>ctrl.abort(),12000);
        try{const r=await fetch(url,{signal:ctrl.signal,credentials:'omit',cache:'no-store'});if(!r.ok)throw Error('HTTP '+r.status);
          const raw=await r.json();const candidate=url.startsWith(MIRROR)?raw:{rows:raw,source:url,retrievedAt:new Date().toISOString()};
          if(!adopt(candidate))throw Error('Invalid or future-dated catalog');received++;
        }finally{clearTimeout(timer);}
      }));
      const current=!!cached&&Date.now()-Date.parse(cached.retrievedAt)<=3*3600000;
      window.SpaceWxHeaderStatus?.report('scoreboard','NASA CME Scoreboard',received>0&&current,received?(current?'Dated catalog received':'Published catalog is stale'):'Unavailable');
      if(!received)throw Error('Unavailable');return cached;
    })();try{return await inflight;}finally{inflight=null;}
  }
''' + s[end:]
        a=s.index("    root.className='wx-cme-card wx-scoreboard';");b=s.index('    let events=',a)
        s=s[:a]+'''    root.classList.add('wx-scoreboard');root.innerHTML=`<div class="wx-score-controls"><label>CME Event<select data-score-event aria-label="CME Scoreboard event"></select></label><button data-score-refresh>Refresh</button></div><p class="wx-status" data-score-status role="status">Loading…</p><div data-score-content></div><details class="wx-score-methods"><summary>Source Details</summary><p>Bars retain each submitter’s reported arrival uncertainty. Missing uncertainty remains unspecified. Provider averages and medians are summaries, not independent model runs. The catalog refreshes every five minutes while visible.</p><a href="https://ccmc.gsfc.nasa.gov/scoreboards/cme/earth/" target="_blank" rel="noopener">NASA CME Scoreboard</a></details>`;
''' +s[b:]
        s=replace(s,"error='',timer=null;","error='',timer=null,stopped=false,loading=false,userSelected=false;")
        s=replace(s,'    function paint(){\n      events=',"    function paint(){\n      if(stopped)return;\n      events=")
        s=replace(s,'if(!events.some(e=>e.id===selected))','if(!userSelected||!events.some(e=>e.id===selected))')
        a=s.index("      status.classList.toggle('wx-score-error'");b=s.index('\n      const event=',a)
        s=s[:a]+'''      const stale=!!cached&&Date.now()-Date.parse(cached.retrievedAt)>3*3600000;
      status.classList.toggle('wx-score-error',!!error||stale);status.textContent=`${loading?'Refreshing · ':''}${cached?'Retrieved '+utc(cached.retrievedAt)+' · '+events.length+' Events':'No Catalog Available'}${stale?' · Stale Catalog':''}${error?' · Refresh Unavailable':''}`;
''' +s[b:]
        s=replace(s,'      const outcome=event.arrival?',"      content.querySelectorAll('.js-plotly-plot').forEach(p=>window.Plotly?.purge(p));\n      const outcome=event.arrival?")
        s=replace(s,'height:Math.max(290,series.length*45+80)','height:Math.min(600,Math.max(260,series.length*35+80))')
        # Keep non-M2M provider image inspection in an optional disclosure; default uses the dedicated animation cards.
        s=replace(s,'<div data-score-model></div>','<details class="wx-score-media"><summary>Other Published Run Imagery</summary><div data-score-model></div></details>')
        s=replace(s,"slot.querySelector('select').onchange=show;show();","slot.querySelector('select').onchange=show;slot.closest('details').addEventListener('toggle',()=>{if(slot.closest('details').open&&!slot.querySelector('img').getAttribute('src'))show();});")
        a=s.index('    async function update(){');b=s.index('  window.SpaceWxCMEScoreboard=',a)
        s=s[:a]+'''    async function update(){
      if(stopped||loading)return;loading=true;error='';const button=root.querySelector('[data-score-refresh]');button.disabled=true;button.textContent='Refreshing…';paint();
      try{await refresh();}catch(e){error=e.message;}finally{loading=false;if(!stopped){paint();button.disabled=false;button.textContent='Refresh';}}
    }
    const visible=()=>{if(!document.hidden&&root.isConnected)update();},onData=()=>paint();
    select.onchange=()=>{selected=select.value;userSelected=true;paint();};root.querySelector('[data-score-refresh]').onclick=update;
    window.addEventListener('spacewx:cme-scoreboard',onData);document.addEventListener('visibilitychange',visible);
    paint();update();timer=setInterval(visible,5*60000);
    return ()=>{stopped=true;clearInterval(timer);window.removeEventListener('spacewx:cme-scoreboard',onData);document.removeEventListener('visibilitychange',visible);root.querySelectorAll('.js-plotly-plot').forEach(p=>window.Plotly?.purge(p));};
  }
''' +s[b:]
        return replace(s,'modelLinks,urls};','modelLinks,urls,snapshot:()=>cached};')
    patch('cmeScoreboardProduct',score)
    def cme(_):
        s=(ROOT/'cme_new.js').read_text()
        s=replace(s,"let choices=[],selection='',loaded='';","let choices=[],selection='',loaded='',userSelected=false;")
        s=replace(s,'if(!choices.some(p=>p.key===selection))','if(!userSelected||!choices.some(p=>p.key===selection))')
        s=replace(s,'selection=select.value;show();','selection=select.value;userSelected=true;show();')
        return replace(s,'||!p.submitted)continue;','||!p.submitted||Date.parse(p.submitted)>Date.now()+300000)continue;')
    patch('cmeSolarWindProduct',cme)
    def electron(s):
        s=replace(s,'/main/chhss-data/electron-fluence.json','/ops-live/electron-fluence.json')
        s=replace(s,"now-Date.parse(d.dataAsOf)<=2*3600000","now-Date.parse(d.dataAsOf)>=-5*60000&&now-Date.parse(d.dataAsOf)<=2*3600000")
        s=replace(s,'fetch(URL,{signal:',"fetch(URL+'?_='+Math.floor(Date.now()/300000),{signal:")
        s=s.replace('Current validated publication','Current experimental publication')
        return s
    patch('wxfElectronProduct',electron)
    def particles(s):
        s=replace(s,"  const REFM=","  const OPSREFM='https://raw.githubusercontent.com/wreed1989/SpaceWxOps-WXF/ops-live/particle-forecasts.json';\n  const REFM=")
        s=replace(s,'[get(RELAY),get(REFM,true),get(GOES)]','[get(RELAY),get(REFM,true),get(GOES),get(OPSREFM+\'?_=\'+Math.floor(Date.now()/300000))]')
        s=replace(s,"      if(results[1].status==='fulfilled')", "      if(results[3].status==='fulfilled')accept(results[3].value);\n      if(results[1].status==='fulfilled')")
        # Report a successful current relay when a direct browser request is blocked.
        s=replace(s,"      try{localStorage.setItem(CACHE,JSON.stringify(snapshot));}catch(_){}", "      try{const d=parseREFM(snapshot.sources.refm?.payload);const age=Date.now()-Date.parse(d.issued);if(age>=-300000&&age<=36*3600000&&(results[1].status==='fulfilled'||results[3].status==='fulfilled'))errors.electron='';}catch{}\n      try{localStorage.setItem(CACHE,JSON.stringify(snapshot));}catch(_){}")
        return s.replace('Electron Forecast','Electron')
    patch('particleForecastProduct',particles)
    def layout(s):
        s=replace(s,"name==='swpc'?'SWPC adjustable cards':'Shift Change adjustable cards'","({swpc:'SWPC',shift:'SHIFT CHANGE',cme:'CME'}[name]||name)+' adjustable cards'")
        s=replace(s,"name==='swpc'?'SWPC':'Shift Change'","({swpc:'SWPC',shift:'SHIFT CHANGE',cme:'CME'}[name]||name)")
        return s
    patch('workspaceLayout',layout)
    def labels(s):
        s=replace(s,'preset === "coordinate" ? "SWPC" : preset === "shift" ? "Shift Change" : preset.toUpperCase()', '({monitor:"MONITOR",model:"FORECASTING",forecast:"CHARTS",coordinate:"SWPC",shift:"SHIFT CHANGE"}[preset])')
        for old,new in [('setWorkbench("MODEL",','setWorkbench("FORECASTING",'),('setWorkbench("MODEL PRODUCTS",','setWorkbench("FORECASTING",'),('setWorkbench("MODEL · CORONAL HOLES",','setWorkbench("FORECASTING · CORONAL HOLES",'),('setWorkbench("FORECAST",','setWorkbench("CHARTS",'),('setWorkbench("FORECASTS",','setWorkbench("FORECASTING",')]:
            s=replace(s,old,new)
        return s.replace('Electron Forecast','Electron')
    patch('fdDeskScript',labels)
    for ident,file in [('cmeScoreboardBootstrap','cme-scoreboard.json'),('wxfElectronBootstrap','electron-fluence.json')]:
        patch(ident,lambda s,f=file:'\n'+json.dumps(json.loads((product/f).read_text()),separators=(',',':')).replace('<','\\u003c')+'\n')
    def particle_bootstrap(s):
        d=json.loads(s);n=json.loads((product/'particle-forecasts.json').read_text());d['sources']['refm']=n['sources']['refm'];return '\n'+json.dumps(d,separators=(',',':')).replace('<','\\u003c')+'\n'
    patch('particleForecastBootstrap',particle_bootstrap)
    css=(ROOT/'desk_refresh.css').read_text();js=(ROOT/'desk_headers.js').read_text()
    html=html.replace('</head>',f'<style id="deskRefreshStyles">\n{css}\n</style>\n</head>',1)
    html=html.replace('</body>',f'<script id="deskHeaderCleanup">\n{js}\n</script>\n</body>',1)
    out.write_text(html)
    (out.parent/(out.stem+'_Changes.json')).write_text(json.dumps({'sourceSHA256':hashlib.sha256(original.encode()).hexdigest(),'outputSHA256':hashlib.sha256(html.encode()).hexdigest(),'modifiedScripts':changed},indent=2))
    return changed

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('output',type=Path);p.add_argument('--products',type=Path,required=True);a=p.parse_args();print(json.dumps(build(a.input,a.output,a.products),indent=2))
