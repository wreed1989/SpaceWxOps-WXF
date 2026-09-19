const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const html=fs.readFileSync('SpaceWxOps_Coronal_Hole_HSS_Outlook.html','utf8');
const nairasCode=html.match(/<script id="nairasProduct">([^]*?)<\/script>/)[1];
const core=name=>html.match(new RegExp('      function '+name+'\\([^]*?\\n      \\}'))[0];
const time=Date.parse('2026-09-19T21:00Z');
const source={altitudeKm:20,unit:'mSv/h',sourceTime:new Date(time).toISOString(),retrievedAt:new Date(time+60000).toISOString(),latitudes:Array.from({length:181},(_,i)=>i-90),longitudes:Array.from({length:360},(_,i)=>i),values:Array(65160).fill(.005)};
source.values[(60+90)*360+260]=.03;
source.values[(-60+90)*360+120]=.02;
source.values[90*360]=0;
source.values[91*360]=null;
function moduleFor(source){
  const t=vm.createContext({window:{},document:{getElementById:()=>({textContent:JSON.stringify({schemaVersion:'nairas-effective-dose-1',sources:{nowcast:source}})})},Date,Map,WeakMap});
  vm.runInContext(nairasCode,t);return t.window.SpaceWxNAIRAS;
}
const data=moduleFor(source);
assert.equal(data.reading({},time).rate,.03);
assert.equal(data.reading({scope:'south'},time).rate,.02);
assert.equal(data.reading({scope:'north'},time).longitude,-100);
assert.equal(data.reading({scope:'point',latitude:60.2,longitude:-100.3},time).rate,.03);
assert.equal(data.reading({scope:'point',latitude:0,longitude:0},time).rate,0);
assert.equal(data.reading({scope:'point',latitude:1,longitude:0},time).rate,null);
assert.equal(data.reading({scope:'point',latitude:1,longitude:0},time).fresh,false);
assert.equal(data.reading({},time+3*3600000).fresh,true);
assert.equal(data.reading({},time+3*3600000+1).fresh,false);
assert.equal(data.reading({},time-2*3600000).fresh,false);
assert.equal(data.reading({},time-1).fresh,false);
assert.equal(moduleFor({...source,error:'provider unavailable'}).reading({},time).fresh,false);
assert.equal(moduleFor({...source,values:[1]}).reading({},time).rate,null);
assert.match(data.reading({},time).detail,/Incomplete grid/);

// Saved coordinates and criteria survive upgrades. Bad criteria never become zero.
let saved={radiation:{yellow:.00025,red:.02,purple:null,scope:'point',latitude:-60,longitude:120,audible:true}};
const load=vm.createContext({structuredClone,toNumber:Number,readAlertSetting:()=>JSON.stringify(saved)});
vm.runInContext(html.match(/      const DEFAULT_RULES = \{[^]*?\n      \};/)[0]+'\n'+core('loadRules'),load);
assert.equal(load.loadRules().radiation.yellow,.00025);
assert.equal(load.loadRules().radiation.latitude,-60);
assert.equal(load.loadRules().radiation.scope,'point');
saved={radiation:{yellow:-1,red:'bad',purple:null,scope:'bad',latitude:91,longitude:181}};
assert.equal(load.loadRules().radiation.red,null);
assert.equal(load.loadRules().radiation.scope,'global');
assert.equal(load.loadRules().radiation.latitude,60);
saved={};assert.equal(load.loadRules().radiation.yellow,null);

let reading={...data.reading({},time),rate:.005};
const calls=[];
const context=vm.createContext({window:{SpaceWxNAIRAS:{reading:()=>reading}},state:{rules:{radiation:{yellow:.01,red:.02,purple:null,audible:true,scope:'global'}},previousAlertLevels:{},alertedEvents:{},alertPopupEvents:{}},
  levelRank:s=>({green:0,unknown:0,yellow:1,red:2,magenta:3}[s]||0),
  openAlertActivationPopup:e=>calls.push('popup:'+e.level),playAlertPing:level=>calls.push('audio:'+level),saveAudibleEventMemory(){},saveAlertPopupMemory(){},escapeHtml:String,audibleBellIcon:()=>'',thresholdCard:()=>''});
vm.runInContext(['radiationReading','radiationRate','radiationAlertCard','radiationAlertEvent','radiationAlertDetail','alertLevelFromRule','applyAudibleAlerts'].map(core).join('\n'),context);
context.audibleAlertEvents=()=>[context.radiationAlertEvent()];
context.applyAudibleAlerts();assert.equal(calls.length,0);
reading={...reading,rate:.015};context.applyAudibleAlerts();assert.deepEqual(calls,['popup:yellow','audio:yellow']);
context.applyAudibleAlerts();assert.equal(calls.length,2); // No repeat while elevated.
reading={...reading,rate:.03};context.applyAudibleAlerts();assert.equal(calls.length,4);
reading={...reading,fresh:false,rate:.04};context.applyAudibleAlerts();assert.equal(calls.length,4);
assert.equal(context.radiationAlertCard().level,'unknown');
assert.equal(context.state.previousAlertLevels.radiation,'red'); // Outages do not reset the crossing state.
reading={...reading,fresh:true,sourceTime:'2026-09-19T22:00Z'};context.applyAudibleAlerts();assert.equal(calls.length,4);
reading={...reading,rate:.005};context.applyAudibleAlerts();
reading={...reading,rate:.03,sourceTime:'2026-09-19T23:00Z'};context.applyAudibleAlerts();assert.equal(calls.length,6);
assert.match(context.radiationAlertDetail(),/2026-09-19 23:00 UTC/);
assert.match(context.radiationAlertDetail(),/mSv\/h/);
context.state.rules.radiation={yellow:null,red:null,purple:null};
assert.equal(context.alertLevelFromRule('radiation',0),'green');
assert.equal(context.alertLevelFromRule('radiation',10),'green');
assert.equal(context.radiationAlertCard().level,'unknown');
context.state.rules.radiation.yellow=0;
assert.equal(context.alertLevelFromRule('radiation',0),'yellow'); // A configured zero is distinct from unset.

// Save edits through the same handler used by autosave and the Save button.
const inputs=['yellow','red','purple'].map((field,i)=>({dataset:{rule:'radiation',field},value:['.00025','.02',''][i],disabled:false,setCustomValidity(message){this.error=message;},reportValidity(){}}));
const scope={dataset:{radiationSetting:'scope'},value:'south'};
const grid={querySelectorAll(selector){if(selector==='input[data-radiation-setting]')return [];if(selector==='[data-radiation-setting]')return [scope];return inputs;}};
Object.assign(context,{structuredClone,els:{settingsGrid:grid},saveAlertRules(){},closeSettings(){},renderAll(){}});
vm.runInContext(core('parseRuleInput')+'\n'+core('saveRulesFromForm')+'\n'+core('formatRuleInput'),context);
context.saveRulesFromForm();assert.equal(context.state.rules.radiation.yellow,.00025);
assert.equal(context.state.rules.radiation.purple,null);
assert.equal(context.state.rules.radiation.scope,'south');
assert.equal(context.formatRuleInput('radiation',.00025),'.00025'.replace(/^\./,'0.'));
inputs[0].value='';context.saveRulesFromForm();assert.equal(context.state.rules.radiation.yellow,null);
inputs[0].value='.03';context.saveRulesFromForm();assert.equal(context.state.rules.radiation.yellow,null); // Invalid order rejected.
assert.match(inputs[1].error,/increasing/);
console.log('Radiation maxima, location selection, freshness, saved settings and alert transitions passed');
