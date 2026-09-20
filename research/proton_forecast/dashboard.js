(()=>{
'use strict';
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const utc=s=>Number.isFinite(Date.parse(s))?new Date(s).toISOString().replace('T',' ').slice(0,16)+' UTC':'Unavailable';
const percent=p=>Number.isFinite(p)?(p*100).toFixed(1)+'%':'Unavailable';
const targets=[['p10_10','≥10 MeV · ≥10 pfu','#5dccdf'],['p10_40','≥10 MeV · >40 pfu','#ffb66d'],['p50_10','≥50 MeV · ≥10 pfu','#b797fa']];
const read=id=>{try{return JSON.parse(document.getElementById(id)?.textContent||'null');}catch(_){return null;}};
const model=read('wxfProtonModel'),testCases=read('wxfProtonTests')?.cases||[],databaseVerification=read('wxfProtonVerification');let snapshot=read('wxfProtonBootstrap'),pending=null;
// Draft and last run survive feed refreshes and navigation. Edits never trigger inference.
let session=null;
const selectedTest=()=>testCases.find(c=>c.id===session?.testCase)||null;
const activeData=()=>selectedTest()?.data||snapshot;
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
function channelContext(prior,ch){
 const valid=prior.map(r=>Number.isFinite(r[ch])&&r[ch]>=0),above=prior.map((r,i)=>valid[i]&&r[ch]>=10);
 const recent=above.some((v,i)=>i>=2&&v&&above[i-1]&&above[i-2]);let gap=0,longest=0;
 for(const ok of valid){gap=ok?0:gap+1;longest=Math.max(longest,gap);}
 const complete=prior.length===288&&valid.filter(Boolean).length>=274&&longest<=6;
 return {status:recent?'recent':complete?'clear':'unknown',coverage:valid.filter(Boolean).length/288,maxGapMinutes:longest*5,lastAbove:prior.filter((_,i)=>above[i]).at(-1)?.time||null};
}
function automaticBackground(peak,data){
 const by=new Map((data?.observations||[]).map(r=>[Date.parse(r.time),r]));
 let last=Math.floor(peak/300000)*300000;if(last===peak)last-=300000;
 const prior=Array.from({length:288},(_,i)=>by.get(last-(287-i)*300000)||{});
 const valid=v=>Number.isFinite(v)&&v>=0;
 if(!prior.slice(-3).some(r=>valid(r.P10)&&valid(r.P50))||['P10','P50'].some(ch=>prior.filter(r=>valid(r[ch])).length<240))throw Error('Automatic inputs need at least 20 hours of valid pre-flare GOES data and a recent paired sample. Choose analyst-supplied inputs for a documented historical scenario.');
 const out={episodeContext:{}};
 for(const ch of ['P10','P50']){
  out.episodeContext[ch]=channelContext(prior,ch);out[ch+'Recent']=out.episodeContext[ch].status;
  out[ch]=median(prior.slice(-12).map(r=>valid(r[ch])?r[ch]:null));
  out[ch+'Earlier']=median(prior.slice(-72,-12).map(r=>valid(r[ch])?r[ch]:null));
 }
 if(Number.isFinite(Date.parse(data?.flareHistoryStart))&&Date.parse(data.flareHistoryStart)>peak-86400000)throw Error('The flare-history feed does not cover the preceding 24 hours.');
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
 const classFlux=match?({C:1e-6,M:1e-5,X:1e-4}[match[1]]*+match[2]):NaN;
 const measured=number(input.peakFlux);
 const flux=Number.isFinite(measured)&&input.reportedClass===match?.[0]?measured:classFlux;
 const peak=Date.parse(String(input.peakTime||'').replace(/Z$/,'')+'Z'),rise=number(input.riseMinutes),lon=number(input.longitude),lat=number(input.latitude);
 if(!(flux>=1e-6&&flux<=.01))throw Error('Enter a peak class from C1 through X100.');
 if(!Number.isFinite(peak)||peak>now-600000)throw Error('Enter the observed flare peak in UTC, at least 10 minutes before this run.');
 if(!Number.isFinite(rise)||rise<0||rise>1440)throw Error('Enter flare rise time from 0 to 1,440 minutes.');
 if([lon,lat].some(v=>v!==null&&(!Number.isFinite(v)||Math.abs(v)>90)))throw Error('Use coordinates from −90° to +90°, or leave them unknown.');
 const b=input.background==='manual'?Object.fromEntries(['P10','P50','P10Earlier','P50Earlier','priorFlares'].map(k=>[k,number(input[k])]).concat(['P10Active','P50Active','P10Recent','P50Recent'].map(k=>[k,input[k]||'unknown']))):automaticBackground(peak,data);
 if(['P10','P50','P10Earlier','P50Earlier','priorFlares'].some(k=>!Number.isFinite(b[k])||b[k]<0)||!Number.isInteger(b.priorFlares))throw Error('Enter nonnegative GOES medians and an integer preceding C1+ flare count. Zero is valid; blanks are not zero.');
 if(['P10Active','P50Active'].some(k=>!['yes','no','unknown'].includes(b[k])))throw Error('Specify the event status at the forecast window start.');
 for(const k of ['integral','previousIntegral'])if(number(input[k])!==null&&(!Number.isFinite(number(input[k]))||number(input[k])<0))throw Error('Optional integrated flux values must be nonnegative.');
 const features=[Math.log10(flux),Math.log1p(rise),lon===null?null:Math.sin(lon*Math.PI/180),lon===null?null:Math.cos(lon*Math.PI/180),lat===null?null:Math.abs(lat)/90,Math.log10(b.P10+.01),Math.log10(b.P50+.01),Math.log10((b.P10+.01)/(b.P10Earlier+.01)),Math.log10((b.P50+.01)/(b.P50Earlier+.01)),Math.log1p(b.priorFlares)];
 const baselineEligible={p10_10:b.P10Active==='unknown'?null:b.P10Active==='no',p10_40:b.P10Active==='unknown'?null:b.P10Active==='no',p50_10:b.P50Active==='unknown'?null:b.P50Active==='no'};
 const eligible=baselineEligible;
 const episodeContext=b.episodeContext||Object.fromEntries(['P10','P50'].map(ch=>[ch,{status:b[ch+'Recent']||'unknown',lastAbove:null}]));
 return {episodeContext,input:JSON.parse(JSON.stringify(input)),inputSnapshotAt:data?.generatedAt||null,background:b,event:{peakTime:new Date(peak).toISOString(),flareClass:match[0]},createdAt:new Date(now).toISOString(),validStart:new Date(peak+600000).toISOString(),validEnd:new Date(peak+600000+86400000).toISOString(),features,eligible,probabilities:predict(features),legacy:legacyEstimates(input,flux,lon,peak)};
}
function availableEvents(data=snapshot){return (data?.events||data?.outlooks?.map(r=>r.event)||[]).slice().sort((a,b)=>Date.parse(a.peakTime)-Date.parse(b.peakTime));}
function draftFor(event,data=snapshot){
 const ev=event===undefined?availableEvents(data).at(-1):event;
 const draft={flareClass:ev?.flareClass||'',reportedClass:ev?.flareClass||'',peakFlux:ev?.peakFlux??null,peakTime:ev?.peakTime?.slice(0,16)||'',riseMinutes:ev?.riseMinutes??'',longitude:ev?.longitude??'',latitude:ev?.latitude??'',background:'auto',P10:'',P50:'',P10Earlier:'',P50Earlier:'',priorFlares:'',P10Active:'unknown',P50Active:'unknown',P10Recent:'unknown',P50Recent:'unknown',integral:ev?.integral??'',previous:ev?.previous||'unknown',previousIntegral:ev?.previousIntegral??'',opticalClass:ev?.opticalClass||'',radio:ev?.radio||'unknown',region:ev?.region??null,inputSources:ev?.inputSources||{},inputNotes:ev?.inputNotes||[],locationMethod:ev?.locationMethod||'',integralEnd:ev?.integralEnd||null,previousPeak:ev?.previousPeak||null,sourcePeak:ev?.peakTime||null,overrides:[]};
 try{if(draft.peakTime)Object.assign(draft,automaticBackground(Date.parse(draft.peakTime+'Z'),data));}
 catch(e){draft.inputError=e.message;}
 return draft;
}
async function refresh(){
 if(pending)return pending;
 pending=(async()=>{const r=await fetch('https://raw.githubusercontent.com/wreed1989/SpaceWxOps-WXF/main/chhss-data/proton-forecast.json',{cache:'no-store',signal:AbortSignal.timeout(15000)});if(!r.ok)throw Error(`HTTP ${r.status}`);const j=await r.json();if(j.schemaVersion!=='WXF-SEP-0.1'||!Array.isArray(j.observations)||!Array.isArray(j.rawFlares))throw Error('WXF proton inputs unavailable');if(!snapshot||Date.parse(j.generatedAt)>=Date.parse(snapshot.generatedAt))snapshot=j;})().finally(()=>pending=null);return pending;
}
function mount(root,parent){
 session??={draft:draftFor(),result:null,dirty:false,autoFollow:true,testCase:null,decision:.2,showHistory:false};
 let disposed=false,error='';
 const field=(key,label,type='number',extra='')=>`<label>${label}<input data-sep-input="${key}" aria-label="${label}" type="${type}" value="${esc(session.draft[key])}" ${extra}></label>`;
 const select=(key,label,options)=>`<label>${label}<select data-sep-input="${key}" aria-label="${label}">${options.map(([v,t])=>`<option value="${v}"${session.draft[key]===v?' selected':''}>${t}</option>`).join('')}</select></label>`;
 function eventOptions(){return '<option value="">Select a reported flare…</option>'+availableEvents(activeData()).slice().reverse().map((event)=>`<option value="${esc(event.peakTime)}"${event.peakTime.slice(0,16)===session.draft.peakTime?' selected':''}>${esc(event.flareClass)} · ${utc(event.peakTime)}</option>`).join('');}
 function build(){
  root.innerHTML=`<section class="wx-sep-inputs"><div class="wx-sep-setup-head"><h3>Event setup</h3><span data-sep-draft></span></div>
   <div class="wx-sep-control-row"><label>Source<select data-sep-case aria-label="Proton test case"><option value="live"${selectedTest()?'':' selected'}>Live · reported flares</option>${testCases.map(c=>`<option value="${esc(c.id)}"${session.testCase===c.id?' selected':''}>${esc(c.title)}</option>`).join('')}</select></label><label>Reported flare<select data-wxf-sep-event aria-label="Load observed flare">${eventOptions()}</select></label><button data-sep-apply>Run WXF Proton Model</button></div>
   <p data-sep-test-note class="wx-sep-test-note"${selectedTest()?'':' hidden'}></p>
   <div class="wx-sep-input-grid">${field('peakTime','Flare peak · UTC','datetime-local','step="60"')}${field('flareClass','Peak X-ray class','text','placeholder="e.g. M5.0"')}${field('riseMinutes','Start → peak · minutes','number','min="0" max="1440" step="any"')}${field('longitude','Longitude · west +','number','min="-90" max="90" step="any" placeholder="Unknown"')}${field('latitude','Latitude · north +','number','min="-90" max="90" step="any" placeholder="Unknown"')}${field('integral','Integrated X-ray flux · J/m²','number','min="0" step="any"')}</div>
   <details data-sep-manual><summary>Analyst adjustments · particle history</summary><div class="wx-sep-input-grid">${select('background','Particle & flare history',[['auto','Automatic · pre-flare GOES'],['manual','Analyst supplied']])}</div><p class="wx-particle-status">Enter pre-flare medians from five-minute GOES samples. Current status uses the three five-minute samples before the window. Recent history checks the preceding 24 hours for a sustained ≥10 pfu crossing. Recent activity is context, not an automatic exclusion. Elevated pre-flare levels and trends remain model inputs; the probability concerns a new or renewed crossing in the stated window.</p><div class="wx-sep-input-grid">${field('P10','10 MeV · last 1 h median · pfu')}${field('P50','50 MeV · last 1 h median · pfu')}${field('P10Earlier','10 MeV · preceding 5 h median · pfu')}${field('P50Earlier','50 MeV · preceding 5 h median · pfu')}${field('priorFlares','Prior 24 h · global C1+ flare count')}${select('P10Active','10 MeV ≥10 pfu already active?',[['unknown','Unknown · withhold probability'],['no','No'],['yes','Yes']])}${select('P50Active','50 MeV ≥10 pfu already active?',[['unknown','Unknown · withhold probability'],['no','No'],['yes','Yes']])}${select('P10Recent','10 MeV · preceding 24 h',[['unknown','Unknown'],['clear','No sustained crossing'],['recent','Sustained crossing']])}${select('P50Recent','50 MeV · preceding 24 h',[['unknown','Unknown'],['clear','No sustained crossing'],['recent','Sustained crossing']])}</div></details>
   <details data-sep-optional><summary>Analyst adjustments · peak estimate &amp; event record</summary><p class="wx-particle-status">The optional published PROTONS relations estimate >10 MeV peak flux and flare-peak → proton-peak delay, conditional on an SEP event. Integrate to the decay level (peak + pre-flare background) / 2, including background in the integral. These estimates require C2.4+; they do not change the WXF occurrence probabilities.</p><div class="wx-sep-input-grid">${select('previous','Previous flare from same region?',[['unknown','Unknown'],['no','No'],['yes','Yes']])}${field('previousIntegral','Previous flare integral · J/m²','number','min="0" step="any"')}</div><p class="wx-particle-status">Event record only: optical class and radio sweep are saved with this run but are not fitted predictors in WXF-SEP-0.1.</p><div class="wx-sep-input-grid">${field('opticalClass','Optical class · record only','text')}${select('radio','Radio sweep · record only',[['unknown','Unknown'],['none','None observed'],['II','Type II'],['IV','Type IV'],['II+IV','Type II & IV']])}</div></details>
   <details><summary>Input sources &amp; quality</summary><p class="wx-sep-auto-status" data-sep-auto></p><div data-sep-sources></div></details><div class="wx-sep-setup-footer"><span data-sep-context></span><div><button data-sep-background>Reload automatic inputs</button><button data-sep-reset>Clear inputs</button></div></div><p data-sep-error role="status"></p></section>
   <section class="wx-sep-results" data-sep-results></section><div class="wx-sep-chart-head"><strong>Observed proton flux</strong><label><input type="checkbox" data-sep-history ${session.showHistory?'checked':''}> Show preceding 24 hours</label></div><div class="wx-particle-plot" data-wxf-sep-observed style="min-height:400px;height:440px"></div><p class="wx-particle-status" data-sep-feed></p>
   <details><summary>Method, output availability &amp; verification</summary><p>WXF-SEP-0.1 estimates three fixed, whole-window event probabilities from peak class, rise time, location, pre-flare particle levels/trends and the prior global C1+ count. It is not a reproduction of SWPC’s internal model. Missing coordinates use training-set imputation. Probability is withheld when the event is already active at the window start or that baseline is unknown. Prior activity alone does not exclude the forecast: the target can be a renewed crossing after flux fell below threshold. Pre-flare context is retained separately from in-window outcomes.</p><p>PCA absorption, SST dose, 50 MeV peak flux and proton onset delay are not calculated. Each needs a separately specified and validated method; a proton probability cannot substitute for these quantities. Exact PROTONS occurrence probabilities additionally require the lookup tables in Balch (1999), Tables 6–8; the 2008 verification tables cannot substitute for them.</p>${verification()}<p>The separate peak estimates follow <a href="https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2007SW000337" target="_blank" rel="noopener">Balch (2008), section 2</a>, also reproduced as equations 7–9 in <a href="https://repository.library.noaa.gov/view/noaa/52048/noaa_52048_DS1.pdf" target="_blank" rel="noopener">Whitman et al., PROTONS review, pp. 34–35</a>. These historical empirical relations are not newly calibrated or verified by the WXF scores above. Integrate SXR from onset through the decay time at (peak + pre-flare background) / 2. The integral includes the background; it is not a background-subtracted fluence. Peak delay is not onset delay and may exceed the 24-hour probability window. No confidence interval is inferred from the published average errors.</p></details>`;
  root.querySelectorAll('[data-sep-input]').forEach(el=>el.oninput=()=>{
   const key=el.dataset.sepInput;session.draft[key]=el.value;session.dirty=true;session.autoFollow=false;
   session.draft.overrides=[...new Set([...session.draft.overrides,key])];
   if(key==='flareClass')session.draft.peakFlux=null;
   if(key==='peakTime'){
    const peakTime=el.value;session.draft={...draftFor({}),peakTime,overrides:['peakTime']};
    try{Object.assign(session.draft,automaticBackground(Date.parse(peakTime+'Z'),activeData()));}catch(e){session.draft.inputError=e.message;}
    build();return;
   }
   if(['P10','P50','P10Earlier','P50Earlier','priorFlares','P10Active','P50Active','P10Recent','P50Recent'].includes(key)){
    session.draft.background='manual';root.querySelector('[data-sep-input="background"]').value='manual';
   }
   if(key==='background'&&el.value==='auto'){
    try{Object.assign(session.draft,automaticBackground(Date.parse(session.draft.peakTime+'Z'),activeData()));delete session.draft.inputError;build();return;}
    catch(e){session.draft.inputError=e.message;}
   }
   draftStatus();
  });
  root.querySelector('[data-wxf-sep-event]').onchange=e=>{if(e.target.value==='')return;session.draft=draftFor(availableEvents(activeData()).find(event=>event.peakTime===e.target.value),activeData());session.autoFollow=false;session.dirty=true;build();};
  root.querySelector('[data-sep-reset]').onclick=()=>{session.testCase=null;session.result=null;session.draft=draftFor({});session.autoFollow=false;session.dirty=true;build();};
  root.querySelector('[data-sep-background]').onclick=()=>{
   const ev=availableEvents(activeData()).find(event=>event.peakTime.slice(0,16)===session.draft.peakTime);
   if(!ev&&session.draft.peakTime){try{Object.assign(session.draft,automaticBackground(Date.parse(session.draft.peakTime+'Z'),activeData()),{background:'auto'});delete session.draft.inputError;session.dirty=true;build();}catch(e){root.querySelector('[data-sep-error]').textContent=e.message;}return;}
   session.draft=draftFor(ev,activeData());session.autoFollow=false;session.dirty=true;build();
  };
  root.querySelector('[data-sep-apply]').onclick=()=>{try{const result=run(session.draft,activeData());result.testCaseId=session.testCase;session.result=result;session.dirty=false;session.autoFollow=false;root.querySelector('[data-sep-error]').textContent='';paintResult();paintObserved();draftStatus();}catch(e){root.querySelector('[data-sep-error]').textContent=e.message;}};
  root.querySelector('[data-sep-case]').onchange=e=>{
   session.testCase=e.target.value==='live'?null:e.target.value;session.result=null;session.dirty=false;session.autoFollow=!session.testCase;
   session.draft=draftFor(selectedTest()?.event,activeData());build();
  };
  root.querySelector('[data-sep-export-verification]')?.addEventListener('click',()=>{
   const blob=new Blob([JSON.stringify(databaseVerification,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='WXF_Proton_Verification.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  });
  root.querySelector('[data-sep-history]').onchange=e=>{session.showHistory=e.target.checked;paintObserved();};
  root.querySelector('[data-sep-decision]')?.addEventListener('change',e=>{session.decision=Number(e.target.value);paintDecision();});
  paintDecision();paintResult();paintObserved();draftStatus();
 }
 function draftStatus(){
  const tc=selectedTest(),d=session.draft,missing=number(d.longitude)===null||number(d.latitude)===null;
  const waiting=Date.parse(d.peakTime+'Z')>Date.now()-600000;
  const ready=d.peakTime&&d.flareClass&&!(d.background==='auto'&&d.inputError);
  root.querySelector('[data-sep-test-note]').textContent=tc?'HISTORICAL TEST · '+tc.title+' · Live alerts remain current.'+(d.overrides.length?' Modified scenario.':''):'';
  root.querySelector('[data-sep-context]').textContent=['P10','P50'].map(ch=>`${ch==='P10'?'10':'50'} MeV: ${d[ch+'Recent']==='recent'?'recent event':d[ch+'Recent']==='clear'?'no recent crossing':'history unknown'}`).join(' · ');
  const parts=[d.sourcePeak?'Loaded reported flare'+(d.region?' · AR '+d.region:''):'Enter a flare or select a reported event'];
  if(d.peakFlux!==null)parts.push('Peak '+Number(d.peakFlux).toExponential(3)+' W/m²');
  parts.push(missing?((d.inputNotes||[]).some(n=>n.includes('off-limb'))?'Off-limb detection · disk coordinates unavailable':'Location unknown · trained imputation'):d.overrides.some(k=>k==='longitude'||k==='latitude')?'Analyst coordinates':d.locationMethod||'Analyst coordinates');
  if(d.integralEnd&&!d.overrides.includes('integral'))parts.push('Completed integral through '+utc(d.integralEnd));
  if(d.overrides.length)parts.push('Analyst overrides applied');
  root.querySelector('[data-sep-auto]').textContent=parts.join(' · ');
  root.querySelector('[data-sep-draft]').textContent=waiting?'Waiting until 10 minutes after the observed peak; refresh inputs before Run':(d.background==='auto'&&d.inputError)?d.inputError:!ready?'Choose a reported flare or enter the required inputs':session.dirty?'Inputs changed · Run to apply':session.result?'Showing last completed run':'Automatic inputs loaded · Run to calculate';
  root.querySelector('[data-sep-sources]').innerHTML=`<p class="wx-particle-status">Input snapshot ${utc(activeData()?.generatedAt)}. No model runs automatically. Peak edits clear the old event association; edits to pre-flare measurements switch to analyst mode.</p>${Object.entries(d.inputSources).filter(([,url])=>/^https:\/\//.test(url)).map(([key,url])=>`<p class="wx-particle-status"><a href="${esc(url)}" target="_blank" rel="noopener">${esc(key)} source</a></p>`).join('')}<p class="wx-particle-status">${(d.inputNotes||[]).map(esc).join(' ')}</p><p class="wx-particle-status">${(activeData()?.inputWarnings||[]).map(w=>esc(w.reason)).join(' · ')}</p>`;
  window.SpaceWxProductFlow?.sync(parent);
 }
 function paintResult(){
  const el=root.querySelector('[data-sep-results]');el.querySelectorAll('.js-plotly-plot').forEach(p=>window.Plotly?.purge(p));
  const r=session.result;if(!r){el.innerHTML='<p class="wx-sep-run-note">Set the flare inputs above and run the model. Observed GOES proton flux is shown below.</p>';return;}
  const tc=testCases.find(c=>c.id===r.testCaseId);
  const late=Date.parse(r.createdAt)>Date.parse(r.validStart)+1800000,expired=Date.now()>Date.parse(r.validEnd),l=r.legacy;
  el.innerHTML=`<p class="wx-sep-run-note"><b>${tc?'HISTORICAL TEST · ':''}${esc(r.event.flareClass)} · peak ${utc(r.event.peakTime)}</b><br>Run ${utc(r.createdAt)} · ${r.input.background==='manual'?'Analyst-supplied history':'Automatic pre-flare history'}${expired&&!tc?' · Historical reconstruction':''}<br>Target window: ${utc(r.validStart)} – ${utc(r.validEnd)}${late&&!tc?'<br>Late reconstruction: these are whole-window probabilities, not remaining risk.':''}</p>
   <div class="wx-sep-probabilities" aria-label="Proton event probabilities">${targets.map(([key,label,color])=>`<div title="Probability of a sustained threshold crossing in the stated window, including renewed crossings after flux fell below threshold. Probabilities are not yes/no warnings."><strong style="color:${color}">${label}</strong><span>${r.eligible[key]===true?percent(r.probabilities[key]):r.background[(key==='p50_10'?'P50':'P10')+'Active']==='yes'?'Active event':'Baseline unknown'}</span></div>`).join('')}</div>
   ${tc?`<div class="wx-sep-test-outcomes"><strong>Recorded outcome</strong><p>${esc(tc.description)}</p><div class="wx-particle-table"><table><thead><tr><th>Target</th><th>Pre-flare context</th><th>Following 24 h</th><th>Peak · pfu</th></tr></thead><tbody>${targets.map(([key,label])=>{const ch=key==='p50_10'?'P50':'P10',ctx=tc.episodeContext[ch];return `<tr><td>${label}</td><td>${ctx.status==='recent'?'Recent event':ctx.status==='clear'?'No recent crossing':'Unknown'}${ctx.lastAbove?'<br><small>Last ≥10 pfu '+utc(ctx.lastAbove)+'</small>':''}</td><td>${tc.outcomes[key].label===1?'Threshold crossed':tc.outcomes[key].label===0?'No crossing':'Not scored'}</td><td>${Number(tc.outcomes[key].observed_peak_pfu).toPrecision(3)}</td></tr>`;}).join('')}</tbody></table></div><small>${r.input.overrides.length?'Recorded observations refer to the original case, not the edited scenario.':'Archived observations; these are not additional validation samples.'}</small></div>`:''}

   ${l.peakP10!==null||l.peakDelayHours!==null?`<div class="wx-proton-summary"><div><strong>Conditional >10 MeV peak · empirical</strong><span>${l.peakP10===null?'Integral / prior flare needed':l.peakP10.toPrecision(3)+' pfu'}</span></div><div><strong>Flare peak → proton peak · empirical</strong><span>${l.peakDelayHours===null?'Longitude needed':l.peakDelayHours.toFixed(1)+' h'}</span><small>${l.peakTime?utc(l.peakTime):''} · conditional on an SEP event</small></div></div>`:''}
   <details><summary>Inputs used in this run</summary><p class="wx-particle-status">Peak ${esc(r.input.flareClass)} at ${utc(r.event.peakTime)} · rise ${esc(r.input.riseMinutes)} min · longitude ${esc(number(r.input.longitude)??'unknown')}° (west +) · latitude ${esc(number(r.input.latitude)??'unknown')}° (north +). Global prior C1+ flares: ${r.background.priorFlares}.</p><p class="wx-particle-status">Pre-flare medians: 10 MeV ${r.background.P10.toPrecision(4)} pfu (preceding five hours ${r.background.P10Earlier.toPrecision(4)}); 50 MeV ${r.background.P50.toPrecision(4)} pfu (preceding five hours ${r.background.P50Earlier.toPrecision(4)}). Baseline active: 10 MeV ${esc(r.background.P10Active)}; 50 MeV ${esc(r.background.P50Active)}.</p><p class="wx-particle-status">Half-power SXR integral ${esc(number(r.input.integral)??'unknown')} J/m² · previous same-region flare ${esc(r.input.previous)} · previous integral ${esc(number(r.input.previousIntegral)??'unknown')} J/m². Record only: optical ${esc(r.input.opticalClass||'unknown')}; radio ${esc(r.input.radio)}.</p></details>`;
  window.SpaceWxProductFlow?.sync(parent);
 }
 function paintObserved(){
  const tc=selectedTest(),revealed=!tc||session.result?.testCaseId===tc.id,data=activeData();
  const selectedPeak=Date.parse((tc?.event.peakTime||session.result?.event.peakTime||session.draft.peakTime||'').replace(/Z$/,'')+'Z');
  const peak=Number.isFinite(selectedPeak)?selectedPeak:Date.now()-86400000,start=peak+600000,end=peak+86400000+600000;
  const observations=(data?.observations||[]).filter(r=>revealed||Date.parse(r.time)<peak);
  const payload=observations.flatMap(r=>[10,50].map(e=>({time_tag:r.time,energy:`>=${e} MeV`,flux:r['P'+e]}))).filter(r=>Number.isFinite(r.flux));
  const hours=24+1/6+(session.showHistory?24:0),chart=window.SpaceWxParticles.protonChart({goesProtons:{payload}},hours,end);chart.layout.annotations=[];
  chart.layout.shapes.push({type:'line',xref:'x',yref:'paper',x0:new Date(start).toISOString(),x1:new Date(start).toISOString(),y0:0,y1:1,line:{color:'#7ddaea',width:1.5,dash:'dot'}},{type:'rect',xref:'x',yref:'paper',x0:new Date(start).toISOString(),x1:new Date(end).toISOString(),y0:0,y1:1,fillcolor:'rgba(83,195,221,.05)',line:{width:0},layer:'below'});
  if(session.showHistory)chart.layout.shapes.push({type:'line',xref:'x',yref:'paper',x0:new Date(peak).toISOString(),x1:new Date(peak).toISOString(),y0:0,y1:1,line:{color:'#ffbe83',width:1.5,dash:'dot'}});
  window.Plotly?.react(root.querySelector('[data-wxf-sep-observed]'),chart.traces,chart.layout,{responsive:true,displayModeBar:false,scrollZoom:false});
  root.querySelector('[data-sep-feed]').textContent=`Flare peak: ${utc(new Date(peak).toISOString())} · Forecast: ${utc(new Date(start).toISOString())} – ${utc(new Date(end).toISOString())}. ${session.showHistory?'Orange divider: flare peak; cyan divider: forecast start.':'Plot begins at the flare peak; cyan divider starts the forecast window.'} `+(tc?(revealed?'Archived observations; live alerts remain current.':'Select Run to reveal the archived outcome.'):`${error?error+' · ':''}GOES through ${utc(data?.observations?.at(-1)?.time)}${Date.now()-Date.parse(data?.observations?.at(-1)?.time)>90*60000?' · STALE':''}.`);
 }

 function scoreRows(){return targets.map(([key,label])=>[key,label,databaseVerification?.targets[key]||null]);}
 function paintDecision(){
  const el=root.querySelector('[data-sep-decision-table]');if(!el)return;
  el.innerHTML=`<table><thead><tr><th>Target</th><th>Detection</th><th>False-alarm ratio</th><th>Yes forecasts</th></tr></thead><tbody>${scoreRows().map(([key,label,v])=>{const m=v?.decisionSweep.find(x=>x.decisionProbability===session.decision);return `<tr><td>${label}</td><td>${percent(m?.POD)}</td><td>${m?.FAR===null?'No yes forecasts':percent(m?.FAR)}</td><td>${m?m.hits+m.falseAlarms:'—'}</td></tr>`;}).join('')}</tbody></table>`;
 }
 function verification(){
  if(!model)return '<p>Trained model unavailable.</p>';
  return `<p>Historical verification · 2022–2026. Training: 2010–2014; calibration: 2015–2021. These scores include new and renewed threshold crossings; they do not establish which flare caused an enhancement. Counts are forecast windows, not independent proton events. Pre-flare activity is recorded separately, with a no-recent-crossing subset in the export.</p><div class="wx-particle-table"><table><thead><tr><th>Target</th><th>Scored / positive</th><th>Brier skill · 95% range</th></tr></thead><tbody>${scoreRows().map(([key,label,v])=>`<tr><td>${label}</td><td>${v?v.n+' / '+v.events:'Unavailable'}</td><td>${v?(v.brierSkill*100).toFixed(1)+'%<br><small>'+v.brierSkill95.map(x=>(x*100).toFixed(1)+'%').join(' to ')+'</small>':'Unavailable'}</td></tr>`).join('')}</tbody></table></div><p>Positive Brier skill means lower probability error than the training event rate. These scores do not use a yes/no cutoff. Intervals resample 14-day blocks.</p>
  <details class="wx-sep-score-details"><summary>Detection &amp; false alarms · scoring cutoff</summary><p>This is a WXF verification setting, not a pfu threshold or a required PROTONS setting. Forecast probabilities at or above the selected cutoff count as “yes” for this table. Changing it does not change forecasts or Alert Settings.</p><label>Probability cutoff <select data-sep-decision aria-label="Verification probability cutoff">${[.05,.1,.2,.3,.5].map(v=>`<option value="${v}"${v===session.decision?' selected':''}>${100*v}%</option>`).join('')}</select></label><div class="wx-particle-table" data-sep-decision-table></div><p>Detection: fraction of observed positive windows caught. False-alarm ratio: fraction of yes forecasts that were wrong. These inspected years must not be used to select a supposedly optimal cutoff.</p></details>
  <p>Database: ${databaseVerification?.dataset.forecastCases.toLocaleString()} forecast cases. <button data-sep-export-verification>Export statistics</button></p><p>The export retains the original all-window scores and exclusions from the pre-flare audit. Finalized historical inputs do not reproduce real-time feed delays. These scores do not establish operational performance or parity with PROTONS.</p>`;
 } build();return {paint:()=>{if(!disposed){paintObserved();}},async refresh(){try{await refresh();error='';}catch(e){error='WXF refresh unavailable; showing dated data';}if(!disposed){if(session.autoFollow&&!session.dirty&&!session.result){session.draft=draftFor();build();}else{root.querySelector('[data-wxf-sep-event]').innerHTML=eventOptions();paintObserved();}}},stop(){disposed=true;root.querySelectorAll('.js-plotly-plot').forEach(p=>window.Plotly?.purge(p));}};
}
window.SpaceWxProtonExperiment={mount,predict,refresh,run,automaticBackground,legacyEstimates,draftFor,availableEvents,testCases,channelContext};
})();
