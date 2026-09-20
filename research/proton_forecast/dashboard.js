(()=>{
'use strict';
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const utc=s=>Number.isFinite(Date.parse(s))?new Date(s).toISOString().replace('T',' ').slice(0,16)+' UTC':'Unavailable';
const percent=p=>Number.isFinite(p)?(p*100).toFixed(1)+'%':'Unavailable';
const targets=[['p10_10','≥10 MeV · ≥10 pfu','#5dccdf'],['p10_40','≥10 MeV · >40 pfu','#ffb66d'],['p50_10','≥50 MeV · ≥10 pfu','#b797fa']];
const read=id=>{try{return JSON.parse(document.getElementById(id)?.textContent||'null');}catch(_){return null;}};
const model=read('wxfProtonModel');let snapshot=read('wxfProtonBootstrap'),pending=null;
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
async function refresh(){
 if(pending)return pending;
 pending=(async()=>{const r=await fetch('https://raw.githubusercontent.com/wreed1989/SpaceWxOps-WXF/main/chhss-data/proton-forecast.json',{cache:'no-store',signal:AbortSignal.timeout(15000)});if(!r.ok)throw Error(`HTTP ${r.status}`);const j=await r.json();if(j.schemaVersion!=='WXF-SEP-0.1')throw Error('Invalid WXF proton product');snapshot=j;})().finally(()=>pending=null);return pending;
}
function mount(root,parent){
 let index=-1,disposed=false,manual=null,error='';
 function paint(){
  if(disposed)return;
  const rows=snapshot?.outlooks||[],chosen=rows[index<0?rows.length-1:index],opened=!!root.querySelector('details[open]');
  if(!chosen){root.innerHTML=`<p class="wx-particle-status">${esc(snapshot?.reason||snapshot?.rejected?.[0]?.reason||'No C1+ flare with adequate observations in an active 24-hour window. A quiet interval is not a zero-probability forecast.')}</p><details><summary>Method &amp; verification</summary>${verification()}</details>`;return;}
  const outlook=manual||chosen,event=outlook.event,expired=Date.now()>Date.parse(outlook.validEnd),late=outlook.latencyMinutes>30;
  root.innerHTML=`<div class="wx-particle-toolbar"><label>Flare event <select data-wxf-sep-event aria-label="WXF proton flare event">${rows.map((r,i)=>`<option value="${i}"${r===chosen?' selected':''}>${esc(r.event.flareClass)} · ${utc(r.event.peakTime)}</option>`).join('')}</select></label><span class="wx-particle-status ${expired?'wx-particle-warning':''}">${expired?'EXPIRED · ':''}${manual?'Analyst scenario · ':''}Calculated ${utc(outlook.createdAt)}</span></div>
  <div class="wx-proton-summary">${targets.map(([key,label,color])=>`<div><strong style="color:${color}">${label}</strong><span>${outlook.eligible?.[key]===false?'Event already active at window start':percent(outlook.probabilities[key])}</span><small>New event · 15-minute sustained crossing</small></div>`).join('')}</div>
  <p class="wx-particle-status">Fixed post-flare window: ${utc(outlook.validStart)} – ${utc(outlook.validEnd)}. ${late?'Late reconstruction: part of this window elapsed before calculation. These are whole-window probabilities, not the remaining risk.':'Probabilities apply to this entire window; later flares can also contribute.'}</p>
  <div class="wx-particle-plot" data-wxf-sep-prob style="min-height:220px;height:240px"></div>
  <div class="wx-particle-plot" data-wxf-sep-observed style="min-height:400px;height:440px"></div>
  <p class="wx-particle-status">${esc(error)}${error?' · ':''}GOES observations through ${utc(snapshot?.observations?.at(-1)?.time)}${Date.now()-Date.parse(snapshot?.observations?.at(-1)?.time)>90*60000?' · STALE':''}. GOES plots use your Alert Settings. WXF probability targets remain the three thresholds stated above. No flux trajectory, PCA absorption, radiation dose or aurora probability is inferred from these probabilities.</p>
  <details${opened?' open':''}><summary>Inputs, analyst adjustments &amp; verification</summary>
   <p>Predictors: flare peak and rise time, reported disk location when available, preceding GOES 10/50 MeV levels and trends, and recent C1+ flare count. The two 10 MeV targets require the ≥10 pfu event to be inactive at window start. Missing location remains unknown. STIS, CME and radio data are not yet fitted predictors in this version.</p>
   <div class="wx-particle-toolbar"><label>Peak class <input data-sep-class aria-label="Proton model flare class" value="${esc(event.flareClass)}" size="6"></label><label>Longitude · west + <input data-sep-lon aria-label="Proton model longitude" type="number" min="-90" max="90" value="${event.longitude??''}" placeholder="Unknown" style="width:100px"></label><label>Latitude · north + <input data-sep-lat aria-label="Proton model latitude" type="number" min="-90" max="90" value="${event.latitude??''}" placeholder="Unknown" style="width:100px"></label><button data-sep-apply>Calculate scenario</button><button data-sep-reset>Reset</button></div><p data-sep-error role="status"></p>
   <p>Peak ${utc(event.peakTime)} · Rise ${Number(event.riseMinutes).toFixed(0)} min · ${outlook.missingFeatures?.length?'Unavailable inputs: '+esc(outlook.missingFeatures.join(', ')):'All fitted inputs available'}. Analyst adjustments affect this view only; published outlooks remain unchanged.</p>
   ${verification()}
   <p><a href="https://www.swpc.noaa.gov/products/goes-proton-flux" target="_blank" rel="noopener">GOES proton measurements</a> · <a href="https://github.com/wreed1989/SpaceWxOps-WXF/tree/main/research/proton_forecast" target="_blank" rel="noopener">WXF method, source manifest and hindcast</a></p>
  </details>`;
  const colors=targets.map(t=>t[2]),p=targets.map(([key])=>outlook.eligible?.[key]===false?null:100*outlook.probabilities[key]);
  const layout={paper_bgcolor:'transparent',plot_bgcolor:'#0a1823',font:{color:'#bed4e1',size:11},margin:{l:155,r:25,t:12,b:45},xaxis:{title:{text:'Whole-window probability (%)'},range:[0,Math.min(100,Math.max(20,...p.filter(Number.isFinite).map(x=>x*1.2)))],gridcolor:'#213c4d',zeroline:false},yaxis:{autorange:'reversed'},showlegend:false,hoverlabel:{bgcolor:'#102635',bordercolor:'#64c8df',font:{color:'#f0f7fb'}}};
  window.Plotly?.react(root.querySelector('[data-wxf-sep-prob]'),[{type:'bar',orientation:'h',x:p,y:targets.map(t=>t[1]),marker:{color:colors},text:p.map(x=>x===null?'Already active':x.toFixed(1)+'%'),textposition:'outside',textangle:0,cliponaxis:false,textfont:{color:'#e8f4fb'},hovertemplate:'%{y}<br>%{x:.1f}%<extra>WXF experimental</extra>'}],layout,{responsive:true,displaylogo:false,scrollZoom:false});
  const payload=(snapshot.observations||[]).flatMap(r=>[10,50].map(e=>({time_tag:r.time,energy:`>=${e} MeV`,flux:r['P'+e]}))).filter(r=>Number.isFinite(r.flux));
  const chart=window.SpaceWxParticles.protonChart({goesProtons:{payload}},24);
  chart.layout.annotations=(chart.layout.annotations||[]).filter(a=>!String(a.text).includes('UMASEP')).concat([10,50].map((e,i)=>({text:`<b>≥${e} MeV</b> · observed GOES flux`,xref:'paper',yref:'paper',x:0,y:i?.475:1.035,showarrow:false,xanchor:'left'})));
  window.Plotly?.react(root.querySelector('[data-wxf-sep-observed]'),chart.traces,chart.layout,{responsive:true,displaylogo:false,scrollZoom:false});
  root.querySelector('[data-wxf-sep-event]').onchange=e=>{index=+e.target.value;manual=null;paint();};
  root.querySelector('[data-sep-reset]').onclick=()=>{manual=null;paint();};
  root.querySelector('[data-sep-apply]').onclick=()=>{
    const val=root.querySelector('[data-sep-class]').value.trim().toUpperCase(),match=val.match(/^([CMX])(\d+(?:\.\d+)?)$/),lon=root.querySelector('[data-sep-lon]'),lat=root.querySelector('[data-sep-lat]');
    const flux=match?({C:1e-6,M:1e-5,X:1e-4}[match[1]]*+match[2]):NaN;
    if(!(flux>=1e-6&&flux<=.01)||![lon,lat].every(el=>el.value===''||(Number.isFinite(+el.value)&&Math.abs(+el.value)<=90))){root.querySelector('[data-sep-error]').textContent='Enter a C1+ peak class and coordinates from −90 to +90°, or leave coordinates empty.';return;}
    const longitude=lon.value===''?null:+lon.value,latitude=lat.value===''?null:+lat.value,features={...chosen.features,log_peak:Math.log10(flux),longitude_sin:longitude===null?null:Math.sin(longitude*Math.PI/180),longitude_cos:longitude===null?null:Math.cos(longitude*Math.PI/180),latitude_abs:latitude===null?null:Math.abs(latitude)/90};
    manual={...chosen,event:{...chosen.event,flareClass:val,peakFlux:flux,longitude,latitude},features,probabilities:predict(model.features.map(k=>features[k])),createdAt:new Date().toISOString(),missingFeatures:model.features.filter(k=>!Number.isFinite(features[k]))};paint();
  };
  window.SpaceWxProductFlow?.sync(parent);
 }
 function verification(){
  if(!model)return '<p>Trained model unavailable.</p>';
  return `<p>Retrospective held-out years: 2022–2026. Training: 2010–2014; calibration: 2015–2021. Chronological boundaries include an embargo and exclude shared active regions. Counts below are flare-triggered forecasts; overlapping windows are not independent SEP events.</p><div class="wx-particle-table"><table><thead><tr><th>Target</th><th>Scored / positive forecasts</th><th>Brier skill · 95% interval</th><th>Detection / false alarms at 20%</th></tr></thead><tbody>${targets.map(([key,label])=>{const v=model.models[key].verification;return `<tr><td>${label}</td><td>${v.n} / ${v.events}</td><td>${(v.brierSkill*100).toFixed(1)}%<br><small>${v.brierSkill95.map(x=>(x*100).toFixed(1)+'%').join(' to ')}</small></td><td>${percent(v.POD)} / ${v.FAR===null?'No yes forecasts':percent(v.FAR)}</td></tr>`;}).join('')}</tbody></table></div><p>Brier skill compares probability error with the training event rate; higher is better and zero means no improvement. Detection is the fraction of positive forecasts caught. False-alarm ratio is the fraction of issued yes forecasts that were wrong. Intervals use 1,000 resamples of 14-day calendar blocks to retain dependence among nearby flares. These scores use retrospective observations, not a replay of feed delays. They do not establish operational warning performance. This initial model has low detection at the stated 20% cutoff.</p>`;
 }
 paint();return {paint,async refresh(){try{await refresh();error='';}catch(e){error='WXF refresh unavailable; showing dated data';}paint();},stop(){disposed=true;root.querySelectorAll('.js-plotly-plot').forEach(p=>window.Plotly?.purge(p));}};
}
window.SpaceWxProtonExperiment={mount,predict,refresh};
})();
