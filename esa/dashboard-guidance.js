/* Current A-EFFort web-feed adapter. Reference time is not an issue time. */
(() => {
'use strict';
const f=window.SpaceWxSolarFeed;
if(!f)throw Error('Solar delivery module is required');
const read=f.readText,parse=f.parseFlareXML;
f.readText=async function(url,options={}){
 const u=new URL(url);
 if(u.searchParams.get('pc')==='S124'&&u.searchParams.get('component')!=='archive'){
  const d=await f.feed(!!options.force),p=f.api.requireProduct(d,'aeffort');
  if(p.web?.format==='aeffort-web-v1')return {text:JSON.stringify(p.web),source:p.source,at:Date.parse(p.fetched_at)||0,contentType:'application/json'};
 }
 return read(url,options);
};
f.parseFlareXML=function(text,provider){
 if(provider!=='aeffort'||!String(text).trim().startsWith('{'))return parse(text,provider);
 if(text.length>1000000)throw Error('Forecast Feed Too Large');
 const d=JSON.parse(text),reference=f.api.iso(d.reference_time);
 if(d.format!=='aeffort-web-v1'||!reference||!Array.isArray(d.records)||d.records.length>101)throw Error('Invalid A-EFFort Web Feed');
 if(d.issued_at!==null||d.valid_start!==null||d.valid_end!==null)throw Error('Unrecognized Web Time Convention');
 const seen=new Set(),records=[];
 for(const r of d.records){
  if(r.region!=='full-disk'&&!/^\d{5}$/.test(r.region||''))throw Error('Invalid A-EFFort Region');
  if(seen.has(r.region))throw Error('Duplicate A-EFFort Region');seen.add(r.region);
  let previous=1;const values={};
  for(const key of ['M1+','M5+','X1+','X5+']){const v=r.probabilities?.[key];if(typeof v!=='number'||!Number.isFinite(v)||v<0||v>previous)throw Error('Invalid A-EFFort Probability');values[key]=v;previous=v;}
  records.push({provider,region:r.region,issued:reference,referenceTime:reference,referenceType:'Input Magnetogram',webGuidance:true,validStart:null,validEnd:null,probabilities:values,cumulative:true,location:r.location||null,timeConvention:'Input magnetogram UTC; no issue or validity timestamps supplied by the web feed.'});
 }
 if(!seen.has('full-disk'))throw Error('Missing Full-Disk A-EFFort Record');
 return {records,warnings:['The XML API is not current. These values are from the current published web feed. Reference is the input magnetogram time, not the forecast issue time. Explicit validity dates are not supplied; no dates or probabilities were synthesized.']};
};
f.recentGuidance=function(r,now=Date.now()){
 const ref=Date.parse(r.referenceTime);
 return r.webGuidance===true&&Number.isFinite(ref)&&ref<=now+300000&&ref>=now-6*3600000;
};
f.forecastLabel=function(r,current){
 return r.webGuidance?(f.recentGuidance(r)?'Recent Published Web Guidance':'Older Published Web Guidance'):(current?'Current 24-Hour Forecast':'Archive / Outside Current 24-Hour Window');
};
})();
