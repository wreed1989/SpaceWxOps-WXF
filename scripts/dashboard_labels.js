/* Presentation-only title casing for static and dynamically rendered desk labels.
   Keep data values, free text, units, provider prose and option values intact. */
(()=>{
 'use strict';
 const units=new Set(['i','p','m','s','h','d','e','min','hr','km','cm','mm','nm','sr','pfu','nT','mSv','Sv','mGy','Gy','keV','MeV','GeV','dB','ap','ap60','Kp','Dst']);
 function format(value){
  return String(value??'').replace(/Latitude\s*[·:]\s*north\s*\+/gi,'Latitude: N(+) S(-)').replace(/Longitude\s*[·:]\s*west\s*\+/gi,'Longitude: W(+) E(-)').replace(/\b[A-Za-z][A-Za-z0-9]*\b/g,(word,offset,text)=>{
   if(units.has(word)||/[A-Z]/.test(word)||(/^[eE]\d+$/.test(word))||text[offset-1]==="'"||text[offset-1]==='’')return word;
   return word[0].toUpperCase()+word.slice(1);
  });
 }
 const selector='[data-ui-label],h1,h2,h3,h4,h5,h6,label,legend,summary,button,option,th,[role="tab"],.fd-eyebrow,.wx-particle-eyebrow,.wx-particle-stat span,.wx-proton-summary strong,.wx-facts span,.alert-label,.alert-name,.fd-alert-rail-label strong,.fd-workbench-title strong,.modal-title,.header-title,.mini-kpi-label,.kpi-label,.card-title,.gtitle,.xtitle,.x2title,.ytitle,.y2title,.legendtext';
 const named='[aria-label],[title]';
 const ignored='script,style,textarea,input,output,code,pre,[contenteditable="true"],[data-preserve-case]';
 function name(el){
  for(const attr of ['aria-label','title']){const value=el.getAttribute(attr);if(value&&value.length<100&&!/[.!]$/.test(value)&&!/:\/\//.test(value)){const next=format(value);if(next!==value)el.setAttribute(attr,next);}}
 }
 function apply(el){
  if(!el||el.closest(ignored))return;
  name(el);
  // An option's implicit value is its text. Its display label can change safely.
  if(el.tagName==='OPTION'){
   const label=format(el.textContent);if(el.getAttribute('label')!==label)el.setAttribute('label',label);if(el.getAttribute('aria-label')!==label)el.setAttribute('aria-label',label);return;
  }
  function textNodes(parent){
   for(const node of parent.childNodes){
    if(node.nodeType===3){const next=format(node.nodeValue);if(next!==node.nodeValue)node.nodeValue=next;}
    else if(node.nodeType===1&&!node.matches('select,'+ignored)&&!node.matches('p,small,[role="status"],.fd-muted,.wx-particle-status'))textNodes(node);
   }
  }
  textNodes(el);

 }
 function refresh(root){
  if(!root||root.nodeType!==1)return;
  if(root.matches(named))name(root);
  if(root.closest(ignored))return;
  root.querySelectorAll(named).forEach(name);
  if(root.matches(selector))apply(root);
  root.querySelectorAll(selector).forEach(apply);
 }
 window.SpaceWxLabels={format,apply,refresh};
 if(typeof document==='undefined'||!document.querySelectorAll)return;
 function start(){
  refresh(document.body);
  const pending=new Set();let frame=0;
  const observer=new MutationObserver(records=>{
   for(const r of records){
    if(r.type==='attributes')pending.add(r.target);
    else if(r.type==='characterData'){
     const label=r.target.parentElement?.closest(selector);if(label)pending.add(label);
    }else for(const n of r.addedNodes){
     if(n.nodeType===1)pending.add(n);
     else if(n.nodeType===3){const label=n.parentElement?.closest(selector);if(label)pending.add(label);}
    }
   }
   if(pending.size&&!frame)frame=requestAnimationFrame(()=>{frame=0;const roots=[...pending];pending.clear();roots.forEach(refresh);});
  });
  observer.observe(document.body,{subtree:true,childList:true,characterData:true,attributes:true,attributeFilter:['aria-label','title']});
 }
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true});else start();
})();
