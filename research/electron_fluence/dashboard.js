(()=>{
  'use strict';
  const URL='https://raw.githubusercontent.com/wreed1989/SpaceWxOps-WXF/main/chhss-data/electron-fluence.json';
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const num=v=>typeof v==='number'&&Number.isFinite(v)&&v>=0;
  const fmt=v=>num(v)?v.toExponential(2):'Unavailable';
  const utc=t=>Number.isFinite(Date.parse(t))?new Date(t).toISOString().replace('T',' ').slice(0,16)+' UTC':'Unavailable';
  function valid(d){
    if(d?.schemaVersion!=='WXF-EF-0.1'||!Number.isFinite(Date.parse(d.issuedAt)))return false;
    if(d.status==='withheld')return Array.isArray(d.forecast)&&d.forecast.length===0;
    if(d.status!=='experimental'||!Array.isArray(d.history)||d.history.length!==24||!d.history.every(r=>r.flux===null||num(r.flux))||!num(d.evaluation?.metrics?.WXF?.['24']?.mae)||!num(d.evaluation?.metrics?.diurnalPersistence?.['24']?.mae)||!d.evaluation?.thresholds?.severe||!Number.isFinite(Date.parse(d.dataAsOf))||Date.parse(d.issuedAt)<Date.parse(d.dataAsOf)||d.forecast?.length!==24)return false;
    return d.forecast.every((r,i)=>Date.parse(r.time)===Date.parse(d.dataAsOf)+(i+1)*3600000&&
      ['low','median','high','fluxLow','fluxMedian','fluxHigh'].every(k=>r[k]===null||num(r[k]))&&
      (r.low===null?r.median===null&&r.high===null:num(r.median)&&num(r.high)&&r.low<=r.median&&r.median<=r.high)&&
      num(r.fluxLow)&&num(r.fluxMedian)&&num(r.fluxHigh)&&r.fluxLow<=r.fluxMedian&&r.fluxMedian<=r.fluxHigh);
  }
  function fresh(d,now=Date.now()){
    return valid(d)&&d.status==='experimental'&&now-Date.parse(d.dataAsOf)<=2*3600000&&Date.parse(d.issuedAt)<=now+5*60000;
  }
  let data=null;
  function accept(d){if(valid(d)&&(!data||Date.parse(d.issuedAt)>=Date.parse(data.issuedAt)))data=d;}
  try{accept(JSON.parse(document.getElementById('wxfElectronBootstrap')?.textContent||'null'));}catch(_){}
  async function refresh(){const c=new AbortController(),timer=setTimeout(()=>c.abort(),15000);try{const r=await fetch(URL,{signal:c.signal,cache:'no-store',credentials:'omit'});if(!r.ok)throw Error('HTTP '+r.status);const d=await r.json();if(!valid(d))throw Error('Invalid WXF publication');accept(d);return '';}catch(_){return 'Live refresh unavailable; showing the dated snapshot.';}finally{clearTimeout(timer);}}
  function chart(d,view='fluence',thresholdScale=false){
    const flux=view==='flux',rows=d.forecast,x=rows.map(r=>r.time),prefix=flux?'flux':'';
    const values=key=>rows.map(r=>r[prefix?prefix+key[0].toUpperCase()+key.slice(1):key]);
    const traces=[{name:'Empirical 90% range',x,y:values('high'),mode:'lines',type:'scatter',line:{width:0},hoverinfo:'skip',showlegend:false,connectgaps:false},
      {name:'Empirical 90% range',x,y:values('low'),mode:'lines',type:'scatter',line:{width:0},fill:'tonexty',fillcolor:'rgba(83,167,222,.19)',hoverinfo:'skip',connectgaps:false},
      {name:'WXF median',x,y:values('median'),mode:'lines+markers',type:'scatter',line:{color:'#ffbd7c',width:2.5},marker:{size:4},connectgaps:false,
       customdata:rows.map((r,i)=>[values('low')[i],values('high')[i]]),hovertemplate:'%{x|%d %b %H:%M UTC}<br>Median %{y:.2e}<br>Range %{customdata[0]:.2e}–%{customdata[1]:.2e}<extra>WXF experimental</extra>'}];
    if(flux)traces.unshift({name:'Observed hourly flux',x:d.history.map(r=>r.time),y:d.history.map(r=>r.flux),mode:'lines',type:'scatter',line:{color:'#62d5cf',width:2},connectgaps:false,hovertemplate:'%{x|%d %b %H:%M UTC}<br>%{y:.2e} e⁻ cm⁻² s⁻¹ sr⁻¹<extra>Hourly average</extra>'});
    else if(num(d.observedFluence))traces.unshift({name:'Observed rolling 24 h',x:[d.dataAsOf],y:[d.observedFluence],mode:'markers',type:'scatter',marker:{size:8,color:'#62d5cf'},hovertemplate:'%{x|%d %b %H:%M UTC}<br>%{y:.2e} e⁻ cm⁻² sr⁻¹<extra>Observed</extra>'});
    const style=window.SpaceWxAlertStyle,all=traces.flatMap(t=>t.y).filter(num);
    let max=Math.max(flux?15:1.2e8,...all)*1.12;
    if(thresholdScale&&!flux)max=Math.max(max,...(style?.thresholds('electron')||[{value:1.1e8},{value:4.8e8}]).map(r=>r.value*1.12));
    const layout={autosize:true,paper_bgcolor:'rgba(0,0,0,0)',plot_bgcolor:'#0c1c29',font:{color:'#b7cfdf',size:11},margin:{l:68,r:20,t:35,b:44},
      legend:{orientation:'h',x:0,y:1.14},hovermode:'x unified',hoverlabel:{bgcolor:'#111e2b',bordercolor:'#617f98',font:{color:'#fff',size:12}},
      xaxis:{type:'date',title:'UTC',tickformat:'%H:%M\n%d %b',gridcolor:'#233b4d'},
      yaxis:{title:{text:flux?'Flux · e⁻ cm⁻² s⁻¹ sr⁻¹':'Rolling 24 h · e⁻ cm⁻² sr⁻¹'},type:'linear',range:[0,max],minallowed:0,tickformat:'~s',gridcolor:'#233b4d',automargin:true},
      shapes:[],annotations:[]};
    if(!flux&&style){const o=style.overlay('electron',max);layout.shapes.push(...o.shapes);layout.annotations.push(...o.annotations);traces.find(t=>t.name==='WXF median').marker.color=values('median').map(v=>style.color('electron',v));}
    if(!flux&&!style)for(const [value,color]of [[1.1e8,'#f4cd62'],[4.8e8,'#fb8585']])if(value<=max){layout.shapes.push({type:'line',xref:'paper',x0:0,x1:1,y0:value,y1:value,line:{color,width:1,dash:'dash'}});layout.annotations.push({xref:'paper',x:.98,y:value,xanchor:'right',yanchor:'bottom',text:value.toExponential(1),showarrow:false,font:{color,size:10},bgcolor:'#102333'});}
    return {traces,layout};
  }
  function mount(root,flowRoot=root,initial=null){
    if(initial)accept(initial);let stopped=false,view='fluence',full=false,error='';
    function paint(){
      if(stopped)return;const open=!!root.querySelector('details[open]');root.querySelectorAll('.js-plotly-plot').forEach(p=>window.Plotly?.purge(p));
      if(!data){root.innerHTML='<p class="wx-particle-status">WXF forecast has not been received yet. Refresh to retrieve the experimental publication.</p>';return;}
      const d=data,e=d.evaluation,active=fresh(d),latest=d.forecast?.at(-1),cov=e?.coverage?.['24'],missing=d.completeObservedHours<24;
      if(d.status==='withheld'){root.innerHTML=`<p class="wx-particle-warning">Forecast withheld · ${esc(d.reason)}</p><p class="wx-particle-status">Issued ${utc(d.issuedAt)}. No missing data are substituted with zero.</p>`;return;}
      const base=e.metrics.diurnalPersistence['24'].mae,wxf=e.metrics.WXF['24'].mae;
      root.innerHTML=`<div class="wx-particle-toolbar"><span class="wx-particle-status ${!active?'wx-particle-warning':''}">${active?'EXPERIMENTAL':'STALE SNAPSHOT'} · Data through ${utc(d.dataAsOf)} · Issued ${utc(d.issuedAt)}</span></div>
        <div class="wx-particle-stat"><div><span>+24 h median</span><strong>${fmt(latest.median)}</strong></div><div><span>Empirical range</span><strong>${fmt(latest.low)}–${fmt(latest.high)}</strong></div></div>
        <div class="wx-particle-toolbar"><label>Display <select data-wxf-view><option value="fluence">Rolling 24-hour fluence</option><option value="flux">Hourly electron flux</option></select></label><label><input data-wxf-scale type="checkbox" ${full?'checked':''}> Show all thresholds</label><span class="wx-particle-status">GOES-19 · >2 MeV · GEO</span></div>
        <div class="wx-particle-plot" data-wxf-plot></div>
        <p class="wx-particle-status">${missing?'Recent observations contain a gap. Rolling totals remain unavailable until that gap leaves the 24-hour window. ':''}${error?esc(error)+' ':''}New CME/HSS arrivals are not explicitly predicted. The shaded range describes forecast uncertainty. Thresholds follow Alert Settings → Electron Fluence; they do not predict spacecraft failure.</p>
        <details ${open?'open':''}><summary>Method, verification &amp; forecast limits</summary>
        <p>WXF learns changes in hourly electron flux from recent electron levels and trends, and lagged solar-wind speed, magnetic field, southward-field coupling and proton dynamic pressure. Seven days estimate the local diurnal shape only. Whole 24-hour error sequences create the range; each flux path is integrated separately into the preceding rolling 24 hours.</p>
        <p>Storms can deplete the outer belt, while sustained high-speed wind can support later recovery and enhancement. This model learns those associations from measured drivers. It does not explicitly predict a new CME/HSS arrival or future Bz. The separate SWPC bulletin below is context, not an input to these numbers.</p>
        <p>Fixed model: trained Apr 2025–Feb 2026; error ranges calibrated Mar–May 2026; tested Jun–Aug 2026. Next-day mean absolute error: ${fmt(wxf)} versus ${fmt(base)} for diurnal persistence (${((1-wxf/base)*100).toFixed(1)}% lower in this test). The nominal 90% range covered ${(cov*100).toFixed(1)}% of eligible test outcomes. ${e.originCount} overlapping origins on ${e.distinctDates} dates; these are not independent events.</p>
        <p>At the original office thresholds (1.1 × 10⁸ / 4.8 × 10⁸): ${e.thresholds.moderate.exceedanceCount} moderate and ${e.thresholds.severe.exceedanceCount} severe exceedances in ${e.thresholds.severe.dailyOrigins} daily evaluation samples. Severe-event skill is unestablished; no threshold-exceedance probabilities are published. Future verification is pending. The model is frozen and never retuned automatically on test outcomes.</p>
        <p>Incomplete or proton-contaminated samples are excluded. Five-minute averages are integrated as boxcars; no gap filling. ${d.outOfTrainingRange?.length?'Some current predictors are outside their training ranges; extrapolation is especially uncertain. ':''}GEO measurements do not resolve LEO drag, surface charging, all satellite orbits, or material shielding.</p>
        <p><a href="https://github.com/wreed1989/SpaceWxOps-WXF/blob/main/research/electron_fluence/README.md" target="_blank" rel="noopener">WXF model card</a> · <a href="https://iswa.ccmc.gsfc.nasa.gov/hapi/info?id=goesp_part_flux_P5M" target="_blank" rel="noopener">Particle source</a> · <a href="${URL}" target="_blank" rel="noopener">Numerical forecast</a></p>
        ${d.externalGuidance?.bulletin?'<p>SWPC external guidance · preserved as issued · not used as model input:</p><pre style="white-space:pre-wrap;font-size:11px">'+esc(d.externalGuidance.bulletin)+'</pre>':''}</details>`;
      root.querySelector('[data-wxf-view]').value=view;
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
