(()=>{
'use strict';
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const utc=s=>Number.isFinite(Date.parse(s))?new Date(s).toISOString().replace('T',' ').slice(0,16)+' UTC':'Unavailable';
const percent=p=>Number.isFinite(p)?(p*100).toFixed(1)+'%':'Unavailable';
const targets=[['p10_10','≥10 MeV · ≥10 pfu','#5dccdf'],['p10_40','≥10 MeV · >40 pfu','#ffb66d'],['p50_10','≥50 MeV · ≥10 pfu','#b797fa']];
const read=id=>{try{return JSON.parse(document.getElementById(id)?.textContent||'null');}catch(_){return null;}};
const model=read('wxfProtonModel');let snapshot=read('wxfProtonBootstrap'),pending=null;
// Draft and last run survive feed refreshes and navigation. Edits never trigger inference.
let session=null;
const number=v=>v===null||v===undefined||String(v).trim()===''?null:Number(v);
const median=a=>{const v=a.filter(Number.isFinite).sort((a,b)=>a-b),n=v.length;return n?(v[(n-1)>>1]+v[n>>1])/2:null;};
function predict(values){
 if(!model)throw Error('Trained WXF model unavailable');
 const missing=values.map(v=>!Number.isFinite(v)),filled=values.map((v,i)=>missing[i]?model.median[i]:v);
 const z=filled.map((v,i)=>(v-model.mean[i])/model.scale[i]).concat(missing.map(Number)),out={};
 for(const [key,m]of Object.entries(model.models)){
  const raw=z.reduce((s,v,i)=>s+v*m.coef[i],m.intercept),logit=raw*m.calSlope+m.calIntercept;
  out[key]=1/(1+Math.exp(-Math.max(-40,Math.min(40,logit))));
 }
 out.p10_40=Math.min(out.p10_40,out.p10_10);return out;
}
function automaticBackground(peak,data){
 const by=new Map((data?.observations||[]).map(r=>[Date.parse(r.time),r]));
 let last=Math.floor(peak/300000)*300000;if(last===peak)last-=300000;
 const prior=Array.from({length:288},(_,i)=>by.get(last-(287-i)*300000)||{});
 const valid=v=>Number.isFinite(v)&&v>=0;
 if(!prior.slice(-3).some(r=>valid(r.P10)&&valid(r.P50))||['P10','P50'].some(ch=>prior.filter(r=>valid(r[ch])).length<240))throw Error('Automatic inputs need at least 20 hours of valid pre-flare GOES data and a recent paired sample. Choose analyst-supplied inputs for a documented historical scenario.');
 const out={};
 for(const ch of ['P10','P50']){
  out[ch]=median(prior.slice(-12).map(r=>valid(r[ch])?r[ch]:null));
  out[ch+'Earlier']=median(prior.slice(-72,-12).map(r=>valid(r[ch])?r[ch]:null));
 }
 if(!Array.isArray(data?.rawFlares))throw Error('Recent flare history is unavailable; refresh or provide analyst inputs.');
 out.priorFlares=data.rawFlares.filter(r=>Date.parse(r.max_time)>=peak-86400000&&Date.parse(r.max_time)<peak&&r.max_xrlong>=1e-6).length;
 const start=peak+600000,before=Array.from(by.entries()).filter(([t])=>t>=start-900000&&t<start).sort((a,b)=>a[0]-b[0]);
 for(const ch of ['P10','P50']){
  const complete=before.length>=3&&before.every(([,r])=>valid(r[ch]));
  out[ch+'Active']=complete?(before.every(([,r])=>r[ch]>=10)?'yes':'no'):'unknown';
 }
 return out;
}
function legacyEstimates(input,peakFlux,longitude,peak){
 const integral=number(input.integral),previous=number(input.previousIntegral),inDomain=peakFlux>=2.4e-6;
 const priorKnown=input.previous==='no'||(input.previous==='yes'&&Number.isFinite(previous)&&previous>=0);
 const alpha=input.previous==='yes'&&previous>.08?Math.pow(previous/.167,1.146):1;
 const peakP10=inDomain&&Number.isFinite(integral)&&integral>0&&priorKnown?10*alpha*Math.pow(integral/.00987,.82):null;
 const peakDelayHours=inDomain&&Number.isFinite(longitude)?9.4+Math.pow((longitude-78)/18.1,2):null;
 return {peakP10,peakDelayHours,peakTime:Number.isFinite(peakDelayHours)?new Date(peak+peakDelayHours*3600000).toISOString():null};
}
function run(input,data=snapshot,now=Date.now()){
 const match=String(input.flareClass||'').trim().toUpperCase().match(/^([CMX])(\d+(?:\.\d+)?)$/);
 const flux=match?({C:1e-6,M:1e-5,X:1e-4}[match[1]]*+match[2]):NaN;
 const peak=Date.parse(String(input.peakTime||'').replace(/Z$/,'')+'Z'),rise=number(input.riseMinutes),lon=number(input.longitude),lat=number(input.latitude);
 if(!(flux>=1e-6&&flux<=.01))throw Error('Enter a peak class from C1 through X100.');
 if(!Number.isFinite(peak)||peak>now-600000)throw Error('Enter the observed flare peak in UTC, at least 10 minutes before this run.');
 if(!Number.isFinite(rise)||rise<0||rise>1440)throw Error('Enter flare rise time from 0 to 1,440 minutes.');
 if([lon,lat].some(v=>v!==null&&(!Number.isFinite(v)||Math.abs(v)>90)))throw Error('Use coordinates from −90° to +90°, or leave them unknown.');
 const b=input.background==='manual'?Object.fromEntries(['P10','P50','P10Earlier','P50Earlier','priorFlares'].map(k=>[k,number(input[k])]).concat(['P10Active','P50Active'].map(k=>[k,input[k]]))):automaticBackground(peak,data);
 if(['P10','P50','P10Earlier','P50Earlier','priorFlares'].some(k=>!Number.isFinite(b[k])||b[k]<0)||!Number.isInteger(b.priorFlares))throw Error('Enter nonnegative GOES medians and an integer preceding C1+ flare count. Zero is valid; blanks are not zero.');
 if(['P10Active','P50Active'].some(k=>!['yes','no','unknown'].includes(b[k])))throw Error('Specify the event status at the forecast window start.');
 for(const k of ['integral','previousIntegral'])if(number(input[k])!==null&&(!Number.isFinite(number(input[k]))||number(input[k])<0))throw Error('Optional integrated flux values must be nonnegative.');
 const features=[Math.log10(flux),Math.log1p(rise),lon===null?null:Math.sin(lon*Math.PI/180),lon===null?null:Math.cos(lon*Math.PI/180),lat===null?null:Math.abs(lat)/90,Math.log10(b.P10+.01),Math.log10(b.P50+.01),Math.log10((b.P10+.01)/(b.P10Earlier+.01)),Math.log10((b.P50+.01)/(b.P50Earlier+.01)),Math.log1p(b.priorFlares)];
 const eligible={p10_10:b.P10Active==='unknown'?null:b.P10Active==='no',p10_40:b.P10Active==='unknown'?null:b.P10Active==='no',p50_10:b.P50Active==='unknown'?null:b.P50Active==='no'};
 return {input:{...input},background:b,event:{peakTime:new Date(peak).toISOString(),flareClass:match[0]},createdAt:new Date(now).toISOString(),validStart:new Date(peak+600000).toISOString(),validEnd:new Date(peak+600000+86400000).toISOString(),features,eligible,probabilities:predict(features),legacy:legacyEstimates(input,flux,lon,peak)};
}
function draftFor(event){
 const ev=event||snapshot?.outlooks?.at(-1)?.event||null;
 return {flareClass:ev?.flareClass||'',peakTime:ev?.peakTime?.slice(0,16)||'',riseMinutes:ev?.riseMinutes??'',longitude:ev?.longitude??'',latitude:ev?.latitude??'',background:'auto',P10:'',P50:'',P10Earlier:'',P50Earlier:'',priorFlares:'',P10Active:'unknown',P50Active:'unknown',integral:'',previous:'unknown',previousIntegral:'',opticalClass:'',radio:'unknown'};
}
async function refresh(){
 if(pending)return pending;
 pending=(async()=>{const r=await fetch('https://raw.githubusercontent.com/wreed1989/SpaceWxOps-WXF/main/chhss-data/proton-forecast.json',{cache:'no-store',signal:AbortSignal.timeout(15000)});if(!r.ok)throw Error(`HTTP ${r.status}`);const j=await r.json();if(j.schemaVersion!=='WXF-SEP-0.1')throw Error('Invalid WXF proton product');snapshot=j;})().finally(()=>pending=null);return pending;
}
function mount(root,parent){
 session??={draft:draftFor(),result:null,dirty:false};
 let disposed=false,error='';
 const field=(key,label,type='number',extra='')=>`<label>${label}<input data-sep-input="${key}" aria-label="${label}" type="${type}" value="${esc(session.draft[key])}" ${extra}></label>`;
 const select=(key,label,options)=>`<label>${label}<select data-sep-input="${key}" aria-label="${label}">${options.map(([v,t])=>`<option value="${v}"${session.draft[key]===v?' selected':''}>${t}</option>`).join('')}</select></label>`;
 function eventOptions(){return '<option value="">Select a reported flare…</option>'+(snapshot?.outlooks||[]).map((r,i)=>`<option value="${i}"${r.event.peakTime.slice(0,16)===session.draft.peakTime?' selected':''}>${esc(r.event.flareClass)} · ${utc(r.event.peakTime)}</option>`).join('');}
 function build(){
  root.innerHTML=`<section class="wx-sep-inputs"><h3>Model inputs</h3><div class="wx-particle-toolbar"><label>Load flare <select data-wxf-sep-event aria-label="Load observed flare">${eventOptions()}</select></label><button data-sep-reset>Clear inputs</button></div>
   <div class="wx-sep-input-grid">${field('peakTime','Flare peak · UTC','datetime-local','step="60"')}${field('flareClass','Peak X-ray class','text','placeholder="e.g. M5.0"')}${field('riseMinutes','Start → peak · minutes','number','min="0" max="1440" step="any"')}${field('longitude','Longitude · west +','number','min="-90" max="90" step="any" placeholder="Unknown"')}${field('latitude','Latitude · north +','number','min="-90" max="90" step="any" placeholder="Unknown"')}${select('background','Particle & flare history',[['auto','Automatic · pre-flare GOES'],['manual','Analyst supplied']])}</div>
   <div data-sep-manual${session.draft.background==='manual'?'':' hidden'}><p class="wx-particle-status">Enter pre-flare medians from five-minute GOES samples. Event status refers to three consecutive five-minute samples immediately before the forecast window starts. The ≥10 pfu event must be inactive for either 10 MeV target.</p><div class="wx-sep-input-grid">${field('P10','10 MeV · last 1 h median · pfu')}${field('P50','50 MeV · last 1 h median · pfu')}${field('P10Earlier','10 MeV · preceding 5 h median · pfu')}${field('P50Earlier','50 MeV · preceding 5 h median · pfu')}${field('priorFlares','Prior 24 h · global C1+ flare count')}${select('P10Active','10 MeV ≥10 pfu already active?',[['unknown','Unknown · withhold probability'],['no','No'],['yes','Yes']])}${select('P50Active','50 MeV ≥10 pfu already active?',[['unknown','Unknown · withhold probability'],['no','No'],['yes','Yes']])}</div></div>
   <details data-sep-optional><summary>Peak-flux estimate &amp; additional event inputs</summary><p class="wx-particle-status">The optional published PROTONS relations estimate >10 MeV peak flux and flare-peak → proton-peak delay, conditional on an SEP event. Integrate to the decay level (peak + pre-flare background) / 2, including background in the integral. These estimates require C2.4+; they do not change the WXF occurrence probabilities.</p><div class="wx-sep-input-grid">${field('integral','SXR onset → half-power integral · J/m²','number','min="0" step="any"')}${select('previous','Previous flare from same region?',[['unknown','Unknown'],['no','No'],['yes','Yes']])}${field('previousIntegral','Previous flare integral · J/m²','number','min="0" step="any"')}</div><p class="wx-particle-status">Event record only: optical class and radio sweep are saved with this run but are not fitted predictors in WXF-SEP-0.1.</p><div class="wx-sep-input-grid">${field('opticalClass','Optical class · record only','text')}${select('radio','Radio sweep · record only',[['unknown','Unknown'],['none','None observed'],['II','Type II'],['IV','Type IV'],['II+IV','Type II & IV']])}</div></details>
   <div class="wx-particle-toolbar"><button data-sep-apply>Run WXF Proton Model</button><button data-sep-background>Load pre-flare inputs</button><span class="wx-particle-status" data-sep-draft></span></div><p data-sep-error role="status"></p></section>
   <section class="wx-sep-results" data-sep-results></section><div class="wx-particle-plot" data-wxf-sep-observed style="min-height:400px;height:440px"></div><p class="wx-particle-status" data-sep-feed></p>
   <details><summary>Method, output availability &amp; verification</summary><p>WXF-SEP-0.1 estimates three fixed, whole-window event probabilities from peak class, rise time, location, pre-flare particle levels/trends and the prior global C1+ count. It is not a reproduction of SWPC’s internal model. Missing coordinates use training-set imputation. No probability is shown when the event was already active or its baseline status is unknown.</p><p>PCA absorption, SST dose, 50 MeV peak flux and proton onset delay are not calculated. Each needs a separately specified and validated method; a proton probability cannot substitute for these quantities. Exact PROTONS occurrence probabilities additionally require the lookup tables in Balch (1999), Tables 6–8; the 2008 verification tables cannot substitute for them.</p>${verification()}<p>The separate peak estimates follow <a href="https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2007SW000337" target="_blank" rel="noopener">Balch (2008), section 2</a>, also reproduced as equations 7–9 in <a href="https://repository.library.noaa.gov/view/noaa/52048/noaa_52048_DS1.pdf" target="_blank" rel="noopener">Whitman et al., PROTONS review, pp. 34–35</a>. These historical empirical relations are not newly calibrated or verified by the WXF scores above. Integrate SXR from onset through the decay time at (peak + pre-flare background) / 2. The integral includes the background; it is not a background-subtracted fluence. Peak delay is not onset delay and may exceed the 24-hour probability window. No confidence interval is inferred from the published average errors.</p></details>`;
  root.querySelectorAll('[data-sep-input]').forEach(el=>el.oninput=()=>{session.draft[el.dataset.sepInput]=el.value;session.dirty=true;root.querySelector('[data-sep-manual]').hidden=session.draft.background!=='manual';draftStatus();});
  root.querySelector('[data-wxf-sep-event]').onchange=e=>{if(e.target.value==='')return;session.draft=draftFor(snapshot.outlooks[+e.target.value].event);session.dirty=true;build();};
  root.querySelector('[data-sep-reset]').onclick=()=>{session.draft=draftFor({});session.dirty=true;build();};
  root.querySelector('[data-sep-background]').onclick=()=>{try{const peak=Date.parse(session.draft.peakTime+'Z');if(!Number.isFinite(peak))throw Error('Enter the flare peak in UTC first.');const b=automaticBackground(peak,snapshot);Object.assign(session.draft,b,{background:'manual'});session.dirty=true;build();}catch(e){root.querySelector('[data-sep-error]').textContent=e.message;}};
  root.querySelector('[data-sep-apply]').onclick=()=>{try{const result=run(session.draft);session.result=result;session.dirty=false;root.querySelector('[data-sep-error]').textContent='';paintResult();draftStatus();}catch(e){root.querySelector('[data-sep-error]').textContent=e.message;}};
  paintResult();paintObserved();draftStatus();
 }
 function draftStatus(){root.querySelector('[data-sep-draft]').textContent=session.dirty?'Inputs changed · Run to apply':session.result?'Showing last completed run':'Inputs ready · Run to calculate';window.SpaceWxProductFlow?.sync(parent);}
 function paintResult(){
  const el=root.querySelector('[data-sep-results]');el.querySelectorAll('.js-plotly-plot').forEach(p=>window.Plotly?.purge(p));
  const r=session.result;if(!r){el.innerHTML='<p class="wx-sep-run-note">Set the flare inputs above and run the model. Observed GOES proton flux is shown below.</p>';return;}
  const late=Date.parse(r.createdAt)>Date.parse(r.validStart)+1800000,expired=Date.now()>Date.parse(r.validEnd),l=r.legacy;
  el.innerHTML=`<p class="wx-sep-run-note"><b>${esc(r.event.flareClass)} · peak ${utc(r.event.peakTime)}</b><br>Run ${utc(r.createdAt)} · ${r.input.background==='manual'?'Analyst-supplied history':'Automatic pre-flare history'}${expired?' · EXPIRED / historical scenario':''}<br>Target window: ${utc(r.validStart)} – ${utc(r.validEnd)}${late?'<br>Late reconstruction: these are whole-window probabilities, not remaining risk.':''}</p>
   <div class="wx-proton-summary">${targets.map(([key,label,color])=>`<div><strong style="color:${color}">${label}</strong><span>${r.eligible[key]===true?percent(r.probabilities[key]):r.eligible[key]===false?'Already active':'Baseline unknown'}</span><small>New event · 15-minute sustained crossing</small></div>`).join('')}</div><div class="wx-particle-plot" data-wxf-sep-prob style="height:220px;min-height:200px"></div>
   ${l.peakP10!==null||l.peakDelayHours!==null?`<div class="wx-proton-summary"><div><strong>Conditional >10 MeV peak · empirical</strong><span>${l.peakP10===null?'Integral / prior flare needed':l.peakP10.toPrecision(3)+' pfu'}</span></div><div><strong>Flare peak → proton peak · empirical</strong><span>${l.peakDelayHours===null?'Longitude needed':l.peakDelayHours.toFixed(1)+' h'}</span><small>${l.peakTime?utc(l.peakTime):''} · conditional on an SEP event</small></div></div>`:''}
   <details><summary>Inputs used in this run</summary><p class="wx-particle-status">Peak ${esc(r.input.flareClass)} at ${utc(r.event.peakTime)} · rise ${esc(r.input.riseMinutes)} min · longitude ${esc(number(r.input.longitude)??'unknown')}° (west +) · latitude ${esc(number(r.input.latitude)??'unknown')}° (north +). Global prior C1+ flares: ${r.background.priorFlares}.</p><p class="wx-particle-status">Pre-flare medians: 10 MeV ${r.background.P10.toPrecision(4)} pfu (preceding five hours ${r.background.P10Earlier.toPrecision(4)}); 50 MeV ${r.background.P50.toPrecision(4)} pfu (preceding five hours ${r.background.P50Earlier.toPrecision(4)}). Baseline active: 10 MeV ${esc(r.background.P10Active)}; 50 MeV ${esc(r.background.P50Active)}.</p><p class="wx-particle-status">Half-power SXR integral ${esc(r.input.integral||'unknown')} J/m² · previous same-region flare ${esc(r.input.previous)} · previous integral ${esc(number(r.input.previousIntegral)??'unknown')} J/m². Record only: optical ${esc(r.input.opticalClass||'unknown')}; radio ${esc(r.input.radio)}.</p></details>`;
  const p=targets.map(([k])=>r.eligible[k]===true?100*r.probabilities[k]:null);
  window.Plotly?.react(el.querySelector('[data-wxf-sep-prob]'),[{type:'bar',orientation:'h',x:p,y:targets.map(t=>t[1]),marker:{color:targets.map(t=>t[2])},hovertemplate:'%{y}<br>%{x:.1f}%<extra>WXF experimental</extra>'}],{paper_bgcolor:'transparent',plot_bgcolor:'#0a1823',font:{color:'#bed4e1',size:11},margin:{l:155,r:25,t:12,b:45},xaxis:{title:{text:'Whole-window probability (%)'},range:[0,Math.min(100,Math.max(20,...p.filter(Number.isFinite).map(v=>v*1.2)))],gridcolor:'#213c4d',zeroline:false},yaxis:{autorange:'reversed'},showlegend:false,hoverlabel:{bgcolor:'#102635',bordercolor:'#64c8df',font:{color:'#f0f7fb'}}},{responsive:true,displayModeBar:false,scrollZoom:false});
  window.SpaceWxProductFlow?.sync(parent);
 }
 function paintObserved(){
  const payload=(snapshot?.observations||[]).flatMap(r=>[10,50].map(e=>({time_tag:r.time,energy:`>=${e} MeV`,flux:r['P'+e]}))).filter(r=>Number.isFinite(r.flux));
  const chart=window.SpaceWxParticles.protonChart({goesProtons:{payload}},24);chart.layout.annotations=[];
  window.Plotly?.react(root.querySelector('[data-wxf-sep-observed]'),chart.traces,chart.layout,{responsive:true,displayModeBar:false,scrollZoom:false});
  root.querySelector('[data-sep-feed]').textContent=`${error?error+' · ':''}GOES observations through ${utc(snapshot?.observations?.at(-1)?.time)}${Date.now()-Date.parse(snapshot?.observations?.at(-1)?.time)>90*60000?' · STALE':''}. Plots use your Alert Settings. Refresh updates observations; it does not run the model or change your inputs.`;
 }
 function verification(){
  if(!model)return '<p>Trained model unavailable.</p>';
  return `<p>Retrospective held-out years: 2022–2026. Training: 2010–2014; calibration: 2015–2021. Chronological boundaries include an embargo and exclude shared active regions. Counts below are flare-triggered forecasts; overlapping windows are not independent SEP events.</p><div class="wx-particle-table"><table><thead><tr><th>Target</th><th>Scored / positive forecasts</th><th>Brier skill · 95% interval</th><th>Detection / false alarms at 20%</th></tr></thead><tbody>${targets.map(([key,label])=>{const v=model.models[key].verification;return `<tr><td>${label}</td><td>${v.n} / ${v.events}</td><td>${(v.brierSkill*100).toFixed(1)}%<br><small>${v.brierSkill95.map(x=>(x*100).toFixed(1)+'%').join(' to ')}</small></td><td>${percent(v.POD)} / ${v.FAR===null?'No yes forecasts':percent(v.FAR)}</td></tr>`;}).join('')}</tbody></table></div><p>Brier skill compares probability error with the training event rate; higher is better and zero means no improvement. Detection is the fraction of positive forecasts caught. False-alarm ratio is the fraction of issued yes forecasts that were wrong. Intervals use 1,000 resamples of 14-day calendar blocks to retain dependence among nearby flares. These scores use retrospective observations, not a replay of feed delays. They do not establish operational warning performance. This initial model has low detection at the stated 20% cutoff.</p>`;
 } build();return {paint:()=>{if(!disposed){paintObserved();}},async refresh(){try{await refresh();error='';}catch(e){error='WXF refresh unavailable; showing dated data';}if(!disposed){root.querySelector('[data-wxf-sep-event]').innerHTML=eventOptions();paintObserved();}},stop(){disposed=true;root.querySelectorAll('.js-plotly-plot').forEach(p=>window.Plotly?.purge(p));}};
}
window.SpaceWxProtonExperiment={mount,predict,refresh,run,automaticBackground,legacyEstimates};
})();
