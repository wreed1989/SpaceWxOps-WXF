/* Adjustable published CME views. No surrogate animation or invented run time. */
(() => {
 'use strict';
 const DIRECTORY='https://services.swpc.noaa.gov/images/animations/enlil/';
 const HUXT='https://swxforecastlab.s3.eu-west-2.amazonaws.com/WSA_DONKI_huxt_animation_latest.mp4';
 const OPS='https://raw.githubusercontent.com/wreed1989/SpaceWxOps-WXF/ops-live/';
 const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const assetName=url=>{try{const u=new URL(url);return u.searchParams.get('filename')||u.pathname.split('/').at(-1);}catch{return '';}};
 const utc=v=>Number.isFinite(Date.parse(v))?new Date(v).toISOString().slice(0,16).replace('T',' ')+' UTC':'Unavailable';
 let dispose=null;
 function framesFrom(html){
  const names=[...html.matchAll(/href=["']([^"']+\.jpg)["']/gi)].map(m=>m[1]).filter(x=>/^enlil_[a-z0-9_]+_\d{8}T\d{6}\.jpg$/i.test(x));
  const groups=new Map();for(const name of new Set(names)){const m=name.match(/^(.*)_(\d{8}T\d{6})\.jpg$/),s=m[2],valid=`${s.slice(0,4)}-${s.slice(4,6)}-${s.slice(6,8)}T${s.slice(9,11)}:${s.slice(11,13)}:${s.slice(13,15)}Z`;if(!Number.isFinite(Date.parse(valid)))continue;const a=groups.get(m[1])||[];a.push({url:DIRECTORY+name,valid,run:m[1]});groups.set(m[1],a);}
  return [...groups.values()].map(a=>a.sort((a,b)=>a.valid.localeCompare(b.valid))).sort((a,b)=>b.at(-1).valid.localeCompare(a.at(-1).valid))[0]||[];
 }
 function unmount(){dispose?.();dispose=null;}
 function mount(root){
  unmount();root.classList.add('wx-context','wx-cme-workspace');root.replaceChildren();
  let stopped=false;const cleanups=[],controllers=new Set(),byKey=new Map();
  async function request(url,text=false){const c=new AbortController();controllers.add(c);const timer=setTimeout(()=>c.abort(),12000);try{const r=await fetch(url,{credentials:'omit',cache:'no-store',signal:c.signal});if(!r.ok)throw Error('HTTP '+r.status);return text?await r.text():await r.json();}finally{clearTimeout(timer);controllers.delete(c);}}
  const defs=[
   {key:'swpc',label:'SWPC WSA–ENLIL',badge:'NOAA',cols:12,rows:40},
   {key:'huxt',label:'HUXt',badge:'SWx Forecast Lab',cols:12,rows:40},
   {key:'euhforia',label:'EUHFORIA',badge:'KU Leuven · RAL · ESA',cols:12,rows:40},
   {key:'m2m',label:'NASA M2M WSA–ENLIL',badge:'NASA',cols:12,rows:40},
   {key:'scoreboard',label:'CME Scoreboard',badge:'NASA CCMC',cols:24,rows:52},
   {key:'local-huxt',label:'WXF HUXt · Earth Wind Speed',badge:'Numerical Run',cols:12,rows:40},
   {key:'evidence',label:'CME Detection Evidence',badge:'CACTus · DONKI',cols:12,rows:40},
   {key:'pycat',label:'PyCAT',badge:'Planned',cols:24,rows:20}
  ];
  let refreshSWPC=()=>{},refreshHUXT=()=>{},refreshM2M=()=>{};
  let manifest=null;
  async function manifestUpdate(){try{const d=await request(OPS+'manifest.json?_='+Math.floor(Date.now()/300000));if(d?.schemaVersion!=='ops-delivery-1')throw Error('Invalid delivery');if(!stopped){manifest=d;refreshHUXT(false);refreshM2M();}}catch{}}
  function setStatus(body,text){const p=body.querySelector('[data-cme-status]');if(p)p.textContent=text;}
  const layout=window.SpaceWxWorkspaceLayout.mount(root,'cme',defs,(def,body)=>{
   body.classList.add('wx-cme-body');body.dataset.cmeCard=def.key;byKey.set(def.key,body);
   if(def.key==='euhforia'){body.classList.add('wx-cme-euhforia');cleanups.push(window.SpaceWxSolarServices?.mountEUHFORIA(body));return;}
   if(def.key==='scoreboard'){cleanups.push(window.SpaceWxCMEScoreboard.mount(body));return;}
   if(def.key==='local-huxt'){body.classList.add('wx-cme-scroll');const h=window.SpaceWxLocalHUXt?.mount(body);h?.refresh();cleanups.push(()=>h?.stop());return;}
   if(def.key==='evidence'){body.classList.add('wx-cme-scroll');cleanups.push(window.SpaceWxSolarEvidence?.mount(body,'cme'));return;}
   if(def.key==='pycat'){body.innerHTML='<p class="wx-status">Not Connected</p><p class="wx-status">Reserved for measured CME geometry from the SWPC / Met Office Python CME Analysis Tool.</p>';return;}
   if(def.key==='swpc'){
    body.innerHTML='<div class="wx-cme-media"><img data-enlil-image alt="NOAA SWPC WSA–ENLIL forecast"></div><div class="wx-cme-controls"><button data-enlil-play disabled>Play</button><input data-enlil-slider type="range" min="0" max="0" value="0" disabled aria-label="ENLIL forecast frame"><button data-enlil-refresh>Refresh</button></div><p class="wx-status" data-cme-status role="status">Loading…</p>';
    const img=body.querySelector('img'),slider=body.querySelector('input'),play=body.querySelector('[data-enlil-play]');let frames=[],index=0,timer=null,pending=false,updating=false;
    function stop(){clearInterval(timer);timer=null;play.textContent='Play';}
    function show(){if(stopped||!frames[index])return;const f=frames[index];slider.value=index;pending=true;img.hidden=false;img.onload=()=>{pending=false;setStatus(body,`Valid ${utc(f.valid)} · ${index+1}/${frames.length}`);};img.onerror=()=>{pending=false;stop();img.hidden=true;setStatus(body,'Unavailable');};img.src=f.url;}
    refreshSWPC=async()=>{if(stopped||updating)return;updating=true;stop();try{const found=framesFrom(await request(DIRECTORY,true));if(!found.length)throw Error('No frame list');if(stopped)return;frames=found;index=Math.max(0,frames.findIndex(f=>Date.parse(f.valid)>=Date.now()));slider.max=frames.length-1;slider.disabled=false;play.disabled=frames.length<2;show();}catch{if(stopped)return;if(frames.length){setStatus(body,'Refresh Unavailable · Retaining Dated Run');}else{img.onload=()=>setStatus(body,'Latest SWPC Image · Read Run / Valid Times On Image');img.onerror=()=>{img.hidden=true;setStatus(body,'Unavailable');};img.src=DIRECTORY+'latest.jpg?refresh='+Date.now();}}finally{updating=false;}};
    slider.oninput=()=>{stop();index=Number(slider.value);show();};play.onclick=()=>{if(timer){stop();return;}play.textContent='Pause';timer=setInterval(()=>{if(!stopped&&!pending){index=(index+1)%frames.length;show();}},600);};body.querySelector('[data-enlil-refresh]').onclick=refreshSWPC;cleanups.push(stop);return;
   }
   if(def.key==='huxt'){
    body.innerHTML='<div class="wx-cme-media"><video data-huxt-video controls loop muted playsinline preload="metadata" aria-label="HUXt propagation animation"></video></div><div class="wx-cme-controls"><span>WSA · DONKI</span><button data-huxt-refresh>Refresh</button></div><p class="wx-status" data-cme-status role="status">Loading…</p>';
    const video=body.querySelector('video');video.muted=true;let current='',fallback=false;
    refreshHUXT=(force=false)=>{if(stopped)return;const p=manifest?.products?.huxtAnimation;const mirrored=p?.status==='available'&&p.path==='huxt-animation.mp4';const url=mirrored?OPS+p.path+'?v='+encodeURIComponent(p.sha256):HUXT+(force?'?refresh='+Date.now():'');if(!force&&url===current)return;current=url;fallback=false;video.src=url;video.load();setStatus(body,'Read Run / Valid Times On Animation');};
    video.onerror=()=>{if(stopped)return;if(!fallback&&video.src.startsWith(OPS)){fallback=true;video.src=HUXT+'?refresh='+Date.now();video.load();}else setStatus(body,'Animation Unavailable');};
    video.onloadedmetadata=()=>setStatus(body,'WSA Ambient Wind + DONKI CMEs · Read Model Times On Animation');body.querySelector('button').onclick=()=>refreshHUXT(true);cleanups.push(()=>{video.pause();video.removeAttribute('src');video.load();});return;
   }
   if(def.key==='m2m'){
    body.innerHTML='<div class="wx-cme-controls"><label>Published Run<select data-m2m-run aria-label="NASA M2M published run"></select></label><button data-m2m-refresh>Refresh</button></div><div class="wx-cme-media"><img alt="NASA M2M linked WSA–ENLIL propagation animation" hidden></div><p class="wx-status" data-cme-status role="status">Loading…</p>';
    const select=body.querySelector('select'),img=body.querySelector('img');let choices=[],selection='',loaded='';
    function show(){const p=choices.find(c=>c.key===selection)||choices[0];if(!p){select.disabled=true;img.hidden=true;setStatus(body,'No Published Animation Available');return;}selection=p.key;select.value=selection;select.disabled=false;const mirror=manifest?.products?.m2mAnimation;const canMirror=mirror?.status==='available'&&mirror.path==='m2m-animation.gif'&&(mirror.sourceURL===p.url||(mirror.event===p.event&&assetName(mirror.sourceURL)===assetName(p.url)));const url=canMirror?OPS+mirror.path+'?v='+encodeURIComponent(mirror.sha256):p.url;if(url!==loaded){loaded=url;img.hidden=false;let fallback=false;img.onerror=()=>{if(canMirror&&!fallback){fallback=true;img.src=p.url;}else{img.hidden=true;setStatus(body,'Animation Unavailable');}};img.src=url;}
     setStatus(body,`${p.event} · Submitted ${utc(p.submitted)}${Date.now()-Date.parse(p.submitted)>72*3600000?' · Older Run':''}`);
    }
    refreshM2M=()=>{if(stopped)return;const snap=window.SpaceWxCMEScoreboard.snapshot?.();const values=[];for(const event of snap?window.SpaceWxCMEScoreboard.parse(snap.rows):[]){for(const p of event.predictions){if(!/NASA M2M|GSFC SWRC/i.test(p.method)||!p.submitted)continue;for(const url of p.links.filter(u=>/\.gif(?:$|[?&])/i.test(u)))values.push({key:p.id+url,event:event.id,submitted:p.submitted,url,method:p.method});}}values.sort((a,b)=>b.submitted.localeCompare(a.submitted)||Number(/tim[._-]vel/i.test(b.url))-Number(/tim[._-]vel/i.test(a.url)));choices=[...new Map(values.map(v=>[v.url,v])).values()].slice(0,30);const mirror=manifest?.products?.m2mAnimation;if(!choices.length&&mirror?.status==='available')choices=[{key:mirror.sourceURL,event:mirror.event,submitted:mirror.submittedAt,url:mirror.sourceURL,method:mirror.method}];if(!choices.some(p=>p.key===selection))selection=choices[0]?.key||'';select.innerHTML=choices.map(p=>`<option value="${esc(p.key)}">${esc(p.event)} · ${utc(p.submitted)}</option>`).join('');show();};select.onchange=()=>{selection=select.value;show();};body.querySelector('button').onclick=async()=>{try{await window.SpaceWxCMEScoreboard.refresh();}catch{}await manifestUpdate();refreshM2M();};
   }
  });
  const onScore=()=>refreshM2M();window.addEventListener('spacewx:cme-scoreboard',onScore);
  const visibleRefresh=()=>{if(!document.hidden&&!stopped){refreshSWPC();manifestUpdate();}};
  document.addEventListener('visibilitychange',visibleRefresh);
  const timer=setInterval(visibleRefresh,10*60000);
  dispose=()=>{stopped=true;clearInterval(timer);controllers.forEach(c=>c.abort());window.removeEventListener('spacewx:cme-scoreboard',onScore);document.removeEventListener('visibilitychange',visibleRefresh);cleanups.forEach(f=>{try{f?.();}catch{}});layout.stop();};
  refreshSWPC();refreshHUXT();refreshM2M();manifestUpdate();
 }
 window.SpaceWxCME={mount,unmount,framesFrom};
})();
