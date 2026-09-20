const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const html=fs.readFileSync('SpaceWxOps_Coronal_Hole_HSS_Outlook.html','utf8');
const extract=id=>html.match(new RegExp('<script id="'+id+'">([^]*?)<\\/script>'))[1];
const model=JSON.parse(fs.readFileSync('research/proton_forecast/model.json'));
const context=vm.createContext({window:{},document:{getElementById:id=>({textContent:id==='wxfProtonModel'?JSON.stringify(model):'null'})},Date,AbortSignal});
vm.runInContext(extract('suprathermalProduct'),context);
const now=Date.parse('2026-09-20T00:00Z'),data={schemaVersion:'wxf-suprathermal-1',rows:[{time_tag:'2026-09-19T23:00Z',p1:1,quality:0}]};
assert.equal(context.window.SpaceWxSuprathermal.usable(data,now),true);
for(const bad of [{...data,error:'timeout'},{...data,rows:[{...data.rows[0],quality:1}]},{...data,rows:[{...data.rows[0],p1:null}]},{...data,rows:[{...data.rows[0],time_tag:'2026-09-20T00:01Z'}]}])assert.equal(context.window.SpaceWxSuprathermal.usable(bad,now),false);
assert.equal(context.window.SpaceWxSuprathermal.usable(data,now+31*60000),false);
vm.runInContext(extract('wxfProtonDashboard'),context);
const fixture=JSON.parse(fs.readFileSync('research/proton_forecast/inference-fixture.json'));
const prediction=context.window.SpaceWxProtonExperiment.predict(fixture.features);
for(const key in fixture.probabilities)assert.ok(Math.abs(prediction[key]-fixture.probabilities[key])<1e-12,key);
assert.equal(extract('wxfProtonDashboard').trim(),fs.readFileSync('research/proton_forecast/dashboard.js','utf8').trim());
assert.deepEqual(JSON.parse(html.match(/<script type="application\/json" id="wxfProtonModel">([^]*?)<\/script>/)[1]),model);
console.log('STIS freshness/quality and browser/Python proton inference parity passed');
// Particle floors must never clip signed magnetic measurements such as Bz/Dst.
const plotContext=vm.createContext({Date,Number,Array,String,timeOf:r=>r.time,toNumber:Number,coverageGapThresholdMs:()=>600000,coverageGapIntervals:()=>[],escapeHtml:String,formatTraceValue:String,formatIssuedZulu:String,transparentize:x=>x,hoverLabelStyle:()=>({})});
vm.runInContext(html.match(/      function lineTrace\([^]*?\n      \}/)[0],plotContext);
assert.equal(plotContext.lineTrace([{time:'2026-09-20T00:00Z',bz:-15}],'bz','Bz','#fff').y[0],-15);
console.log('Signed geomagnetic measurements remain negative where measured');

// On-demand input engineering, temporal isolation, and independent published relations.
const sep=context.window.SpaceWxProtonExperiment;
const scenario={flareClass:'M1.0',peakTime:'2026-09-19T12:00',riseMinutes:10,longitude:78,latitude:0,background:'manual',P10:1,P50:.1,P10Earlier:.5,P50Earlier:.05,priorFlares:3,P10Active:'no',P50Active:'no',integral:.00987,previous:'no',previousIntegral:'',radio:'unknown',opticalClass:'',currentAp:''};
const runAt=Date.parse('2026-09-19T12:15Z'),first=sep.run(scenario,null,runAt);
assert.equal(first.legacy.peakP10,10);assert.equal(first.legacy.peakDelayHours,9.4);
assert.equal(first.legacy.peakTime,'2026-09-19T21:24:00.000Z');
assert.equal(first.validStart,'2026-09-19T12:10:00.000Z');assert.equal(first.validEnd,'2026-09-20T12:10:00.000Z');
assert.equal(first.features[5],Math.log10(1.01));assert.equal(first.features[7],Math.log10(1.01/.51));
assert.equal(first.eligible.p10_40,true);
assert.equal(sep.run({...scenario,P10Active:'yes'},null,runAt).eligible.p10_40,false);
assert.equal(sep.run({...scenario,P50Active:'unknown'},null,runAt).eligible.p50_10,null);
assert.equal(sep.run({...scenario,longitude:''},null,runAt).legacy.peakDelayHours,null);
assert.equal(sep.run({...scenario,previous:'unknown'},null,runAt).legacy.peakP10,null);
assert.equal(sep.run({...scenario,flareClass:'C1.0'},null,runAt).legacy.peakP10,null);
assert.equal(sep.run({...scenario,integral:''},null,runAt).legacy.peakP10,null);
assert.ok(Math.abs(sep.run({...scenario,previous:'yes',previousIntegral:.167},null,runAt).legacy.peakP10-10)<1e-12);
for(const patch of [{peakTime:'2026-09-20T00:00'},{longitude:91},{latitude:'not a coordinate'},{P10:''},{P10:-1},{priorFlares:1.5},{integral:-1},{riseMinutes:''}])assert.throws(()=>sep.run({...scenario,...patch},null,runAt));
assert.notDeepEqual(sep.run({...scenario,P10:3},null,runAt).probabilities,first.probabilities);
assert.deepEqual(sep.run({...scenario,radio:'II',currentAp:100,opticalClass:'2B'},null,runAt).probabilities,first.probabilities); // Explicitly recorded, not untrained coefficients.
const peak=Date.parse(scenario.peakTime+'Z');
const history={rawFlares:[{max_time:'2026-09-19T11:00Z',max_xrlong:1e-5},{max_time:'2026-09-19T13:00Z',max_xrlong:.001}],observations:Array.from({length:292},(_,i)=>({time:new Date(peak-86400000+i*300000).toISOString(),P10:1,P50:.1}))};
const auto=sep.run({...scenario,background:'auto'},history,runAt);
assert.equal(auto.background.priorFlares,1);
assert.equal(auto.background.P10,1);
const changedFuture={...history,observations:history.observations.map(r=>Date.parse(r.time)>=peak?{...r,P10:500,P50:100}:r)};
assert.deepEqual(sep.run({...scenario,background:'auto'},changedFuture,runAt).features,auto.features); // No future-particle leakage into predictors.
assert.throws(()=>sep.run({...scenario,background:'auto'},{...history,observations:history.observations.slice(-12)},runAt));
assert.ok(html.includes('name: "HIGH FLYER"'));
assert.ok(!html.includes('"Ap / Geomagnetic"'));
assert.ok(html.includes('["realtime.ap", "3-hour Ap", "LIVE"]'));
assert.ok(html.includes('filter(tile=>tile.key!=="realtime.alerts")'));
assert.ok(!html.includes('if(state.preset!=="monitor")mountGlobalAlertRail()'));
console.log('On-demand proton inputs, null/zero validation, pre-flare isolation, published equations and persistent alert contracts passed');
