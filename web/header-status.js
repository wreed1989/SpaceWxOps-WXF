(()=>{
  'use strict';
  const entries=new Map(), esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const labels={R:'Radio blackouts',S:'Solar radiation storms',G:'Geomagnetic storms'};
  let coreStarted=false,scales=null;
  function parseScales(raw,now=Date.now()){
    const row=raw?.['0'],time=Date.parse(`${row?.DateStamp}T${row?.TimeStamp}Z`);
    const fresh=Number.isFinite(time)&&now-time<=15*60000&&time<=now+5*60000;
    return {time,fresh,levels:Object.fromEntries(Object.keys(labels).map(k=>{
      const v=row?.[k]?.Scale, n=v===null||v===undefined||v===''?NaN:Number(v);
      return [k,fresh&&Number.isInteger(n)&&n>=0&&n<=5?n:null];
    }))};
  }
  function report(key,label,ok,detail='',extra={}){
    entries.set(key,{key,label,ok,detail,checkedAt:new Date().toISOString(),...extra});render();
  }
  function setCore(data,rows){
    coreStarted=true;if(data?.noaaScales)scales=data.noaaScales;
    for(const row of rows){
      const paused=['radioBursts','detOutages'].includes(row.key)&&/paused/i.test(row.detail||'');
      const degraded=/unavailable|not connected|fallback|preserving|retained|expired/i.test(row.detail||'');
      entries.set(row.key,{key:row.key,label:row.label,ok:paused?'off':row.ok===undefined?'pending':row.ok&&!degraded,detail:row.detail||'Waiting for first response',checkedAt:row.time});
    }
    const flare=data?.flareGuidance;
    if(flare){
      const end=Date.parse(flare.valid_end),start=Date.parse(flare.valid_start),issued=Date.parse(flare.issued);
      const expired=!Number.isFinite(end)||Date.now()>=end||!Number.isFinite(issued)||issued>Date.now()+300000;
      if(expired||flare.generation_status?.used_previous_forecast)report('flareGuidance','WXF flare publication',false,expired?`Forecast expired or has invalid dates (valid through ${flare.valid_end||'unknown'}).`:flare.generation_status.detail);
      else if(Number.isFinite(start)&&start>Date.now()+86400000)report('flareGuidance','WXF flare publication',false,'Forecast window is more than one day ahead; no current cycle received.');
    }
    render();
  }
  function snapshot(now=Date.now()){
    const rows=[...entries.values()].map(r=>r.ok===true&&now-Date.parse(r.checkedAt)>35*60000?{...r,ok:false,detail:'No successful check in the last 35 minutes.'}:r);
    if(scales){const s=parseScales(scales,now);if(!s.fresh||Object.values(s.levels).some(v=>v===null)){const i=rows.findIndex(r=>r.key==='noaaScales');const bad={key:'noaaScales',label:'NOAA R/S/G scales',ok:false,detail:'Reported scales are missing, invalid or older than 15 minutes.'};if(i<0)rows.push(bad);else rows[i]={...rows[i],...bad};}}
    return {issues:rows.filter(r=>r.ok===false),pending:rows.filter(r=>r.ok==='pending'),off:rows.filter(r=>r.ok==='off'),checked:rows.filter(r=>r.ok===true).length,started:coreStarted};
  }
  function render(){
    if(typeof document==='undefined')return;
    const scale=parseScales(scales),s=snapshot();
    for(const k of Object.keys(labels)){
      const el=document.querySelector(`[data-noaa-scale="${k}"]`);if(!el)continue;
      const n=scale.levels[k];el.querySelector('strong').textContent=n===null?'—':n;
      el.dataset.state=n===null?'unknown':n>=3?'alert':n>0?'watch':'quiet';
      el.title=`${labels[k]}: ${n===null?'current reading unavailable':n===0?'below NOAA storm threshold':'NOAA level '+n}`;
    }
    const scaleTime=document.getElementById('fdScaleTime');if(scaleTime)scaleTime.textContent=scale.fresh?'NOAA reported conditions · '+new Date(scale.time).toISOString().replace('T',' ').slice(0,16)+' UTC':'Current NOAA scales unavailable or older than 15 minutes.';
    const box=document.getElementById('fdFeedDropdown'),label=document.getElementById('fdFeedHealth'),list=document.getElementById('fdFeedIssues');
    if(!box||!label||!list)return;
    label.textContent=s.issues.length?`Feeds: ${s.issues.length} issue${s.issues.length===1?'':'s'}`:s.pending.length||!s.started?'Feeds: Checking':'Feeds: Ok';
    box.dataset.state=s.issues.length?'issue':s.pending.length||!s.started?'pending':'ok';
    const rows=[...s.issues,...s.pending];
    const markup=rows.map(r=>`<li><strong>${esc(r.label)}</strong><span>${esc(r.detail)}</span>${r.checkedAt?'<small>Checked '+esc(new Date(r.checkedAt).toISOString().replace('T',' ').slice(0,19))+' UTC</small>':''}</li>`).join('');
    const text=`<p>${s.checked} responding feeds${s.off.length?' · '+s.off.length+' disabled authenticated feeds':''}. Status covers core feeds and products opened in this session.</p>`+(rows.length?'<ul>'+markup+'</ul>':'<p>No reported feed failures.</p>');
    if(list.innerHTML!==text)list.innerHTML=text;
  }
  window.SpaceWxHeaderStatus={report,setCore,parseScales,snapshot,render};
})();
