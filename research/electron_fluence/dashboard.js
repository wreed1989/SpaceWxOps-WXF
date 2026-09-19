(()=>{
  'use strict';
  const URL='https://raw.githubusercontent.com/wreed1989/SpaceWxOps-WXF/main/chhss-data/electron-fluence.json';
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const num=v=>typeof v==='number'&&Number.isFinite(v)&&v>=0;
  const fmt=v=>num(v)?v.toExponential(2):'Unavailable';
  const utc=t=>Number.isFinite(Date.parse(t))?new Date(t).toISOString().replace('T',' ').slice(0,16)+' UTC':'Unavailable';
  function valid(d){
    if(d?.schemaVersion!=='WXF-EF-0.2'||!Number.isFinite(Date.parse(d.issuedAt)))return false;
    if(d.status==='withheld')return Array.isArray(d.forecast)&&d.forecast.length===0;
    if(d.status!=='experimental'||!Array.isArray(d.history)||d.history.length!==24||!d.history.every(r=>r.flux===null||num(r.flux))||!num(d.evaluation?.metrics?.WXF?.['24']?.mae)||!num(d.evaluation?.metrics?.diurnalPersistence?.['24']?.mae)||!d.evaluation?.thresholds?.moderate||!Number.isFinite(Date.parse(d.dataAsOf))||Date.parse(d.issuedAt)<Date.parse(d.dataAsOf)||d.forecast?.length!==24)return false;
    return d.forecast.every((r,i)=>Date.parse(r.time)===Date.parse(d.dataAsOf)+(i+1)*3600000&&
      ['low','median','high','fluxLow','fluxMedian','fluxHigh'].every(k=>r[k]===null||num(r[k]))&&
      (r.low===null?r.median===null&&r.high===null:num(r.median)&&num(r.high)&&r.low<=r.median&&r.median<=r.high)&&
      num(r.fluxLow)&&num(r.fluxMedian)&&num(r.fluxHigh)&&r.fluxLow<=r.fluxMedian&&r.fluxMedian<=r.fluxHigh&&
      ['', 'flux'].every(p=>{const k=n=>p?p+n[0].toUpperCase()+n.slice(1):n;return r[k('q25')]===undefined&&r[k('q75')]===undefined || (r[k('low')]===null?r[k('q25')]===null&&r[k('q75')]===null:num(r[k('q25')])&&num(r[k('q75')])&&r[k('low')]<=r[k('q25')]&&r[k('q25')]<=r[k('median')]&&r[k('median')]<=r[k('q75')]&&r[k('q75')]<=r[k('high')]);}));
  }
  function fresh(d,now=Date.now()){
    return valid(d)&&d.status==='experimental'&&now-Date.parse(d.dataAsOf)<=2*3600000&&Date.parse(d.issuedAt)<=now+5*60000;
  }
  let data=null;
  function accept(d){if(valid(d)&&(!data||Date.parse(d.issuedAt)>=Date.parse(data.issuedAt)))data=d;}
  try{accept(JSON.parse(document.getElementById('wxfElectronBootstrap')?.textContent||'null'));}catch(_){}
  async function refresh(){const c=new AbortController(),timer=setTimeout(()=>c.abort(),15000);try{const r=await fetch(URL,{signal:c.signal,cache:'no-store',credentials:'omit'});if(!r.ok)throw Error('HTTP '+r.status);const d=await r.json();if(!valid(d))throw Error('Invalid WXF publication');accept(d);window.SpaceWxHeaderStatus?.report('wxfElectron','WXF electron publication',fresh(d),d.status==='withheld'?d.reason:fresh(d)?'Current validated publication':'Observation cutoff is stale');return '';}catch(e){window.SpaceWxHeaderStatus?.report('wxfElectron','WXF electron publication',false,e.message);return 'Live refresh unavailable; showing the dated snapshot.';}finally{clearTimeout(timer);}}
  function chart(d,view='fluence',thresholdScale=true){
    const flux=view==='flux',rows=d.forecast,x=rows.map(r=>r.time),prefix=flux?'flux':'';
    const values=key=>rows.map(r=>r[prefix?prefix+key[0].toUpperCase()+key.slice(1):key]);
    const traces=[];
    const plume=(lo,hi,name,color,edge)=>{
      traces.push({name,x,y:values(hi),mode:'lines',type:'scatter',line:{width:1,color:edge},hoverinfo:'skip',showlegend:false,connectgaps:false,legendgroup:name});
      traces.push({name,x,y:values(lo),mode:'lines',type:'scatter',line:{width:1,color:edge},fill:'tonexty',fillcolor:color,hoverinfo:'skip',connectgaps:false,legendgroup:name});
    };
    plume('low','high','90% prediction range','rgba(93,168,233,.13)','rgba(121,185,239,.27)');
    const inner=values('q25').every((v,i)=>v===null?values('q75')[i]===null:num(v)&&num(values('q75')[i]));
    if(inner)plume('q25','q75','50% prediction range','rgba(105,184,245,.29)','rgba(127,199,249,.46)');
    traces.push({name:'WXF median',x,y:values('median'),mode:'lines+markers',type:'scatter',line:{color:'#ffca93',width:2.8},marker:{size:4},connectgaps:false,
      customdata:rows.map((r,i)=>[values('low')[i],values('high')[i],values('q25')[i],values('q75')[i]]),
      hovertemplate:'%{x|%d %b %H:%M UTC}<br><b>Median %{y:.2e}</b>'+(inner?'<br>50% range %{customdata[2]:.2e}–%{customdata[3]:.2e}':'')+'<br>90% range %{customdata[0]:.2e}–%{customdata[1]:.2e}<extra>WXF experimental</extra>'});
    if(flux)traces.unshift({name:'Observed hourly flux',x:d.history.map(r=>r.time),y:d.history.map(r=>r.flux),mode:'lines',type:'scatter',line:{color:'#62d5cf',width:2},connectgaps:false,hovertemplate:'%{x|%d %b %H:%M UTC}<br>%{y:.2e} e⁻ cm⁻² s⁻¹ sr⁻¹<extra>Hourly average</extra>'});
    else if(num(d.observedFluence))traces.unshift({name:'Observed rolling 24 h',x:[d.dataAsOf],y:[d.observedFluence],mode:'markers',type:'scatter',marker:{size:8,color:'#62d5cf'},hovertemplate:'%{x|%d %b %H:%M UTC}<br>%{y:.2e} e⁻ cm⁻² sr⁻¹<extra>Observed</extra>'});
    const style=window.SpaceWxAlertStyle,all=traces.flatMap(t=>t.y).filter(num);
    const max=Math.max(flux?15:2e8,...all.map(value=>value*1.25));
    const layout={autosize:true,paper_bgcolor:'rgba(0,0,0,0)',plot_bgcolor:'#0a1723',font:{color:'#b7cfdf',size:11},margin:{l:76,r:24,t:48,b:52},
      legend:{orientation:'h',x:0,y:1.15,font:{size:10},traceorder:'normal',groupclick:'togglegroup'},hovermode:'x unified',hoverlabel:{bgcolor:'#111e2b',bordercolor:'#617f98',font:{color:'#fff',size:12}},
      xaxis:{type:'date',title:'UTC',tickformat:'%H:%M\n%d %b',gridcolor:'#233b4d'},
      yaxis:{title:{text:flux?'Flux · e⁻ cm⁻² s⁻¹ sr⁻¹':'Rolling 24 h · e⁻ cm⁻² sr⁻¹'},type:'linear',range:[0,max],minallowed:0,tickformat:'.1e',gridcolor:'#233b4d',automargin:true},
      shapes:[{type:'line',xref:'x',x0:d.dataAsOf,x1:d.dataAsOf,yref:'paper',y0:0,y1:1,line:{color:'#7893a6',width:1,dash:'dot'}}],annotations:[{xref:'x',x:d.dataAsOf,yref:'paper',y:1.015,text:'Forecast →',showarrow:false,xanchor:'left',font:{color:'#9bb5c9',size:10}}]};
    if(!flux&&thresholdScale&&style){const o=style.overlay('electron',max);layout.shapes.push(...o.shapes);layout.annotations.push(...o.annotations);traces.find(t=>t.name==='WXF median').marker.color=values('median').map(v=>style.color('electron',v));}
    if(!flux&&thresholdScale&&!style)for(const [value,color]of [[1.1e8,'#f4cd62'],[4.8e8,'#ef4444']])if(value<=max){layout.shapes.push({type:'line',xref:'paper',x0:0,x1:1,y0:value,y1:value,line:{color,width:1,dash:'dash'}});layout.annotations.push({xref:'paper',x:.98,y:value,xanchor:'right',yanchor:'bottom',text:value.toExponential(1),showarrow:false,font:{color,size:10},bgcolor:'#102333'});}
    return {traces,layout};
  }
  function historicalMarkup(d){
    const hv=d?.historicalValidation,hist=hv?.models?.fullEventGuidance,ci=hv?.pairedComparisons?.diurnalPersistence?.['7']?.bootstrap95;
    const signed=v=>Number.isFinite(v)?v.toExponential(2):'Unavailable';
    return hist?`<p><strong>Historical verification · 2022–August 2026</strong><br>${hv.foldCount} chronological test periods · ${hv.originCount.toLocaleString()} forecasts on ${hv.dates.toLocaleString()} dates. Each recipe is refitted using only earlier data. Full event-guidance +24 h MAE: ${fmt(hist.leads['24'].mae)}; nominal 90% range coverage: ${(100*hist.leads['24'].coverage).toFixed(1)}%. Paired 95% interval for MAE improvement over diurnal persistence: ${signed(ci?.[0])} to ${signed(ci?.[1])}. Seven-day blocks preserve temporal dependence; 27-day sensitivity is reported too.</p><p>Historical tests support the forecast recipe over persistence. The interval for added skill over measured drivers spans zero, so the candidate stays separate. At 4.8e8, the once-per-day sample contains ${hist.thresholds.high.exceedanceDays} exceedance dates: ${hist.thresholds.high.hits} hits, ${hist.thresholds.high.misses} misses and ${hist.thresholds.high.falseAlarms} false alarms from the median forecast. These dates can belong to the same event. Only ${(100*hv.eligibleOriginFraction).toFixed(1)}% of scheduled origins meet the strict historical observation/target-quality gates. This study does not measure live-feed availability or validate new HUXt wind predictors.</p>`:'';
  }
  function mount(root,flowRoot=root,initial=null){
    if(initial)accept(initial);let stopped=false,view='fluence',full=true,error='',which='current';
    function modelControl(){return '<div class="wx-particle-toolbar"><label>WXF model <select data-wxf-model><option value="current">Current · default</option><option value="candidate" '+(!valid(data?.candidate)?'disabled':'')+'>Candidate · IPS/HSS + CME · research</option></select></label></div>';}
    function wireModel(){const el=root.querySelector('[data-wxf-model]');if(el){el.value=which;el.onchange=e=>{which=e.target.value;paint();};}}
    function paint(){
      if(stopped)return;const open=!!root.querySelector('details[open]');root.querySelectorAll('.js-plotly-plot').forEach(p=>window.Plotly?.purge(p));
      if(!data){root.innerHTML='<p class="wx-particle-status">WXF forecast has not been received yet. Refresh to retrieve the experimental publication.</p>';return;}
      if(which==='candidate'&&!valid(data.candidate))which='current';
      const candidate=which==='candidate',d=candidate?data.candidate:data,e=d.evaluation,active=fresh(d),latest=d.forecast?.at(-1),cov=e?.coverage?.['24'],missing=d.completeObservedHours<24;
      if(d.status==='withheld'){root.innerHTML=modelControl()+`<p class="wx-particle-warning">Forecast withheld · ${esc(d.reason)}</p><p class="wx-particle-status">Issued ${utc(d.issuedAt)}. No missing data are substituted with zero.</p>${historicalMarkup(d)}`;wireModel();window.SpaceWxProductFlow?.sync(flowRoot);return;}
      const base=e.metrics.diurnalPersistence['24'].mae,wxf=e.metrics.WXF['24'].mae;
      const guidance=d.arrivalGuidance,p=d.predictorValues||{},runs=guidance?.predictions||[];
      const upcoming=[...new Set(runs.filter(r=>{const h=(Date.parse(r.arrival)-Date.parse(d.dataAsOf))/3600000;return h>=0&&h<=24;}).map(r=>r.event))];
      const rec=p.recurrence_24h_coverage>=.75?Math.round(p.recurrence_24h_speed)+' km/s':'Unavailable';
      const sources=[...new Set(runs.map(r=>r.provider))].join(', ')||'No active arrival submissions';
      const previous=e.ablation?.previousWXF?.development?.metrics?.WXF?.['24']?.mae;
      root.innerHTML=modelControl()+`<div class="wx-particle-toolbar"><span class="wx-particle-status ${!active?'wx-particle-warning':''}">${active?(candidate?'SHADOW CANDIDATE':'EXPERIMENTAL'):'STALE SNAPSHOT'} · Data through ${utc(d.dataAsOf)} · Issued ${utc(d.issuedAt)}</span></div>
        <div class="wx-particle-stat"><div><span>+24 h median</span><strong>${fmt(latest.median)}</strong></div><div><span>Empirical range</span><strong>${fmt(latest.low)}–${fmt(latest.high)}</strong></div></div>
        <div class="wx-particle-toolbar"><label>Display <select data-wxf-view><option value="fluence">Rolling 24-hour fluence</option><option value="flux">Hourly electron flux</option></select></label><label><input data-wxf-scale type="checkbox" ${full?'checked':''}> Show threshold</label><span class="wx-particle-status">${esc(d.spacecraft||'GOES-19')} · >2 MeV · GEO</span>${view==='fluence'?'<span class="wx-particle-status">Thresholds: '+(window.SpaceWxAlertStyle?.thresholds('electron')||[{value:1.1e8},{value:4.8e8}]).map(r=>fmt(r.value)).join(' · ')+'</span>':''}</div>
        ${candidate?'<p class="wx-particle-warning">Historical hindcasts are available. Added CME/HSS skill over measured drivers is not established; current WXF remains the default.</p>':''}
        <p class="wx-particle-status">${esc(d.guidanceMode||'Current WXF')} · ${upcoming.length} CME event${upcoming.length===1?'':'s'} with point-arrival forecasts in the next 24 h ${candidate?'· 27-day wind recurrence: '+rec:'· Arrival guidance is context for the current model.'}</p>
        <div class="wx-particle-plot" data-wxf-plot></div>
        <p class="wx-particle-status">${missing?'Recent observations contain a gap. Rolling totals remain unavailable until that gap leaves the 24-hour window. ':''}${error?esc(error)+' ':''}${candidate?'CME timing and recurrent-wind guidance inform this candidate; they do not guarantee a dropout.':'Current WXF uses observed drivers. Select the candidate above to compare the new arrival-conditioned model.'} The darker plume contains the central 50% of residual-based paths; the outer plume spans 90%. These are empirical prediction ranges, not guaranteed coverage or confidence intervals for a mean. Thresholds follow Alert Settings → Electron Fluence; they do not predict spacecraft failure.</p>
        <details ${open?'open':''}><summary>Method, verification &amp; forecast limits</summary>
        <p>${candidate?'This candidate learns hourly electron changes from observed flux and solar-wind history, predicted CME arrival timing and uncertainty, 27-day wind recurrence, time since reported IPS/HSS onsets and the electron response already observed after each event.':'Current WXF learns hourly electron changes from recent flux and lagged observed solar-wind drivers.'} Seven days estimate the local diurnal shape only. Whole 24-hour error sequences create the range; each flux path is integrated separately into the preceding rolling 24 hours.</p>
        <p>DONKI IPS and HSS reports are gated by each version’s submission time. The candidate learns event age, report delay, pre/post-event diurnal-adjusted electron response, and measured wind-rise/compression timing. A shock is called CME-associated only when its available catalog version links a CME. Later revisions cannot enter an earlier forecast.</p>
        <p>Scoreboard guidance is limited to submissions available at the forecast origin, with one current prediction per provider and CME. Actual arrival times and later storm outcomes are excluded. Active providers: ${esc(sources)}. Provider agreement is not an impact probability. Future Bz, precise dropout timing and subsequent recovery remain uncertain.</p>
        <p>${candidate?'Historical observations span Jan 2020 onward; training begins Feb 2020.':'Current-model training begins Apr 2025 with GOES-19 only.'} Training ends Feb 2026; error ranges use Mar–May; development evaluation uses Jun–Aug. ${candidate?'GOES-16 and GOES-19 retain spacecraft identity, and no profile or fluence window crosses their handoff.':''} Next-day mean absolute error: ${fmt(wxf)} versus ${fmt(base)} for diurnal persistence (${((1-wxf/base)*100).toFixed(1)}% lower in this cohort). ${num(previous)?'Previous WXF on the same cohort: '+fmt(previous)+'. ':''}The nominal 90% range covered ${(cov*100).toFixed(1)}% of eligible outcomes: ${e.originCount} overlapping origins on ${e.distinctDates} dates.</p>
        <p>In the candidate experiment, the larger dataset and measured drivers account for most of the improvement. Tests do not yet establish a reliable additional benefit from CME timing or recurrence alone. The model card includes chronological historical tests and paired block confidence intervals. Historical validation can establish statistical support when every training and calibration target precedes its test period. Live verification adds evidence about real feed delays and outages.</p>
        ${historicalMarkup(d)}
        <p>Office criteria: 1.1e8 and 4.8e8 e⁻ cm⁻² sr⁻¹ in the preceding rolling 24 hours. The original evaluation counted ${e.thresholds.moderate.exceedanceCount} lower-criterion exceedances among ${e.thresholds.moderate.dailyOrigins} daily samples. The broader historical test reports both criteria; adjacent days can belong to one event. No satellite-failure or threshold-exceedance probabilities are published. Editing Alert Settings changes plot styling, not historical validation counts.</p>
        <p>Current CH/HSS geometry is recorded for future calibration. The newly developed CH model lacks a consistent historical issue series. WXF now also runs numerical HUXt with SWPC’s processed inner boundary and DONKI cones. Its Earth wind-speed plot is under CME | Solar Wind. Those issued time series are being archived; historical paired HUXt runs are still needed before they change the electron forecast. An external-guidance outage leaves current WXF running and switches the candidate to the separately evaluated model with observed drivers and recurrence.</p>
        <p>Incomplete or proton-contaminated samples are excluded. Five-minute averages are integrated as boxcars; no gap filling. ${d.outOfTrainingRange?.length?'Some current predictors are outside their training ranges; extrapolation is especially uncertain. ':''}GEO measurements do not resolve LEO drag, surface charging, all satellite orbits, or material shielding.</p>
        <p><a href="https://github.com/wreed1989/SpaceWxOps-WXF/blob/main/research/electron_fluence/README.md" target="_blank" rel="noopener">WXF model card</a> · <a href="https://iswa.ccmc.gsfc.nasa.gov/hapi/info?id=goesp_part_flux_P5M" target="_blank" rel="noopener">Particle source</a> · <a href="${URL}" target="_blank" rel="noopener">Numerical forecast</a></p>
        </details>`;
      wireModel();root.querySelector('[data-wxf-view]').value=view;
      const c=chart(d,view,full);window.Plotly?.react(root.querySelector('[data-wxf-plot]'),c.traces,c.layout,{responsive:true,displaylogo:false,scrollZoom:false,displayModeBar:false});
      root.querySelector('[data-wxf-view]').onchange=e=>{view=e.target.value;paint();};root.querySelector('[data-wxf-scale]').onchange=e=>{full=e.target.checked;paint();};
      window.SpaceWxProductFlow?.sync(flowRoot);
    }
    async function update(){error=await refresh();paint();}
    function stop(){stopped=true;root.querySelectorAll('.js-plotly-plot').forEach(p=>window.Plotly?.purge(p));}
    paint();return {refresh:update,stop,paint};
  }
  window.SpaceWxElectronExperiment={mount,valid,fresh,chart,accept};
})();
