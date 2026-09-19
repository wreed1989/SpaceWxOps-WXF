// Exercise the actual inline client against the published producer contract.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const {webcrypto} = require('node:crypto');
const html = fs.readFileSync('SpaceWxOps_Coronal_Hole_HSS_Outlook.html', 'utf8');
const scripts = [...html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/g)];
for (const [, , code] of scripts) new vm.Script(code);
// Product contracts use the actual inline implementation. Dates, missing
// observations and independent ENLIL runs must survive source ingestion.
const products=vm.createContext({window:{},document:{getElementById(){return null;}},localStorage:{getItem(){return null;}},Date,Map,Set,URL,URLSearchParams});
for(const id of ['solarCycleProduct','cmeScoreboardProduct','cmeSolarWindProduct'])vm.runInContext(scripts.find(([,a])=>a.includes(`id="${id}"`))[2],products);
const cycle=products.window.SpaceWxSolarCycle;
const observed=cycle.parse([{'time-tag':'2026-08',ssn:76,smoothed_ssn:-1,'f10.7':116.22}, {'time-tag':'invalid',ssn:900}, {'time-tag':'2026-02',ssn:77.4,smoothed_ssn:99.8}], 'observed');
assert.equal(observed.length,2);
assert.equal(observed[0].date,'2026-02');
assert.equal(observed[1].smoothed_ssn,null);
assert.equal(observed[0]['f10.7'],null);
const predicted=cycle.parse([{'time-tag':'2030-12',predicted_ssn:8.1,low_ssn:0,high_ssn:13.6}], 'predicted');
const traces=cycle.traces(observed,predicted);
assert.equal(traces[1].y[1],null);
assert.equal(traces[2].y[0],0);
assert.equal(traces[4].line.dash,'dash');
assert.equal(traces[9].y[0],null);
assert.throws(()=>cycle.parse({'error':'unavailable'},'observed'),/Expected monthly/);
const trend=Array.from({length:7},(_,i)=>({date:`2026-0${i+1}`,smoothed_ssn:150-i*10}));
assert.equal(cycle.phase(trend).label,'Declining smoothed trend');
const frames=products.window.SpaceWxCME.framesFrom('<a href="enlil_com1_111_20260918T010000.jpg">old</a><a href="enlil_com2_222_20260919T010000.jpg">new</a><a href="enlil_com2_222_20260919T000000.jpg">new</a><a href="https://evil.test/enlil_com2_222_20260919T040000.jpg">external</a><a href="latest.jpg">latest</a>');
assert.equal(frames.length,2);
assert.equal(frames[0].run,'enlil_com2_222');
assert.equal(frames[0].valid,'2026-09-19T00:00:00Z');
assert.match(frames[0].url,/^https:\/\/services\.swpc\.noaa\.gov\//);
assert.doesNotMatch(html,/OSPREI CME Morphology|HUXt Solar Wind \+ CME/);
const scoreboard=products.window.SpaceWxCMEScoreboard;
const nasa=scoreboard.parse([{cmeID:'2026-09-18T12:00-CME-001',observedTime:'2026-09-18T12:00Z',arrivalTime:null,noArrivalObserved:false,predictions:[{predictedMethodName:'WSA-ENLIL + Cone (NASA M2M)',submissionTime:'2026-09-18T14:00Z',predictedArrivalTime:'2026-09-20T12:00Z',uncertaintyMinusInHrs:7,uncertaintyPlusInHrs:9,confidenceInPercentage:null,predictedMaxKpLowerRange:3,predictedMaxKpUpperRange:5,predictionNote:'https://iswa.gsfc.nasa.gov/api/redirect?filename=20260918_anim.tim-vel.gif\nhttps://evil.test/bad.gif'}]}]);
assert.equal(nasa[0].arrival,null);
assert.equal(nasa[0].noArrival,false);
assert.equal(nasa[0].predictions[0].confidence,null);
assert.equal(nasa[0].predictions[0].links.length,1);
assert.equal(scoreboard.arrivalSeries(nasa[0])[0].error_x.array[0],9*3600000);
assert.equal(scoreboard.arrivalSeries(nasa[0])[0].error_x.arrayminus[0],7*3600000);
assert.match(scoreboard.urls(new Date('2026-09-18'))[0],/kauai.*closeOutCMEsOnly=false/);
assert.match(scoreboard.urls(new Date('2026-10-01'))[0],/ccmc\.gsfc\.nasa\.gov\/CMESB-Earth/);
assert.equal(scoreboard.parse([]).length,0);
assert.throws(()=>scoreboard.parse({error:'unavailable'}),/Invalid NASA/);
// Monitor migration must preserve intentional emptiness, order and chosen sizes.
for(const id of ['monitorLayoutPolicy','particleForecastProduct','nairasProduct'])vm.runInContext(scripts.find(([,a])=>a.includes(`id="${id}"`))[2],products);
const monitor=products.window.SpaceWxMonitorLayout;
assert.equal(monitor.normalize([],()=>true).length,0);
const layoutRows=monitor.normalize([{key:'solar.cycle',cols:6,rows:8},{key:'realtime.imf',cols:8,rows:8},{key:'solar.cycle'},{key:'invalid'}],(_,k)=>k!=='invalid');
assert.deepEqual(Array.from(layoutRows,r=>r.key),['solar.cycle','realtime.imf']);
assert.equal(layoutRows[0].cols,24);
assert.equal(layoutRows[0].rows,60);
assert.equal(layoutRows[1].cols,24);
assert.equal(monitor.normalize([{kind:'visual',key:'helio',cols:8,rows:12,layoutVersion:2}],()=>true)[0].cols,8);
assert.equal(monitor.resize({cols:12,rows:10},504,72,1000).cols,24);
assert.equal(monitor.resize({cols:12,rows:30},504,72,1000).rows,36);
assert.equal(monitor.dimensions(0,999).rows,180);
const particles=products.window.SpaceWxParticles;
const bulletin=':Created: 2026 Sep 19 0014 UTC\n2026 09 17 -9.9e+04 -999 3.7e7 7.6e8 5.3e8\n2026 09 18 3.8e7 412 1.0e8 -9.9e+04 2.2e8';
const refm=particles.parseREFM(bulletin);
assert.equal(refm.issued,'2026-09-19T00:14:00.000Z');
assert.equal(refm.rows[0].observed,null);
assert.equal(refm.rows[0].wind,null);
assert.equal(refm.latest.forecast[0].day,'2026-09-19');
assert.equal(refm.latest.forecast[2].day,'2026-09-21');
assert.equal(refm.latest.forecast[1].value,null);
assert.equal(particles.refmSeries(refm)[1].y[1],null);
assert.throws(()=>particles.parseREFM('Service unavailable'),/No dated/);
const sepRows=particles.parseSEP({sep_forecast_submission:{issue_time:'2026-09-19T05:03:58Z',model:{short_name:'UMASEP-10'},forecasts:[{species:'proton',energy_channel:{min:10,max:-1,units:'MeV'},prediction_window:{start_time:'2026-09-19T05:00:13Z',end_time:'2026-09-19T07:00:13Z'},all_clear:{threshold:10,threshold_units:'pfu',all_clear_boolean:true}}]}});
assert.equal(sepRows[0].flux,null); // all-clear is not zero intensity or zero probability
assert.equal(sepRows[0].allClear,true);
assert.equal(sepRows[0].energy,'≥10 MeV');
assert.equal(particles.freshness(sepRows[0],Date.parse('2026-09-19T08:00Z')),'EXPIRED');
assert.equal(particles.freshness(sepRows[0],Date.parse('2026-09-19T06:00Z')),'Within valid window');
assert.equal(particles.freshness(sepRows[0],Date.parse('2026-09-19T04:00Z')),'Upcoming valid time');
assert.doesNotMatch(html,/CONFIGURE \+ RUN/);
// Every Monitor catalog click must take the toggle route before pane assignment.
const desk=scripts.find(([,a])=>a.includes('id="fdDeskScript"'))[2];
const choose=desk.match(/  function openProduct\(key, pane\) \{[\s\S]*?\n  \}/)[0];
const calls=[];const deskContext=vm.createContext({state:{preset:'monitor',monitorTiles:[{id:'product:realtime.imf',kind:'product',key:'realtime.imf'}]},removeMonitorTile:id=>calls.push(['remove',id]),addMonitorTile:key=>calls.push(['add',key])});
vm.runInContext(choose,deskContext);
deskContext.openProduct('realtime.imf');deskContext.openProduct('solar.cycle');
assert.deepEqual(calls,[['remove','product:realtime.imf'],['add','solar.cycle']]);

// Exercise the recurrence inspector's per-hole sign QA, including degraded HMI.
const recurrence=scripts.find(([,a])=>a.includes('id="fdRecurrenceCompareScript"'))[2];
const selectionCode=recurrence.match(/  function selectHole\(pane, hole\) \{[\s\S]*?\n  \}/)[0];
const selection=vm.createContext({rc:{selected:null,cursor:{lat:0,lon:0},refHoles:[]},holesFor:()=>[],analogMatch:()=>null});
vm.runInContext(selectionCode,selection);
selection.selectHole('current',{uid:'CH01'});
assert.equal(selection.rc.selected.uid,'CH01');
selection.selectHole('current',{uid:'CH01'});
assert.equal(selection.rc.selected,null);
assert.equal(selection.rc.cursor,null);
selection.selectHole('reference',{uid:'CH01'});
selection.selectHole('current',{uid:'CH01'});
assert.equal(selection.rc.selected.pane,'current');
const footprintCode=recurrence.match(/  function holeFootprint\(h, pane, cls\) \{[\s\S]*?\n  \}/)[0];
const footprint=vm.createContext({contourAllowed:p=>p==='current',chState:()=>({measured:{}}),window:{CHHSSScience:{diskTransform:()=>({left:-10,top:-20,width:120,height:140})}},ringToPath:()=>''});
vm.runInContext(footprintCode,footprint);
const outline={rasterContours:[[[10,20],[30,20],[30,40]]]};
assert.match(footprint.holeFootprint(outline,'current','is-selected'),/M2.000,8.000L26.000,8.000L26.000,36.000Z/);
assert.equal(footprint.holeFootprint(outline,'reference',''),'');
assert.equal(footprint.holeFootprint({...outline,reviewOnly:true},'current',''),'');
assert.equal(footprint.holeFootprint({width:30,lat:10,lon:10},'current',''),'');
const signCode=recurrence.match(/  function measuredHoleSign\(h,ch\) \{[\s\S]*?\n  \}/)[0];
const holeContext=vm.createContext({Date});vm.runInContext(signCode,holeContext);
const magnetic={hmiPolarity:{numeric:true},sourceTimeVerified:true,sourceTime:new Date().toISOString(),registeredPack:{polarity:{degraded:true}}};
const region={polarity:1,polarityEvidence:{fluxImbalance:.6,meanBr:2,nValid:100,nMasked:110,validMaskedPixelFraction:.91,temporalAgreement:true}};
assert.equal(holeContext.measuredHoleSign(region,magnetic),1);
assert.equal(holeContext.measuredHoleSign({...region,polarityEvidence:{...region.polarityEvidence,temporalAgreement:false}},magnetic),null);
const fixture = JSON.parse(fs.readFileSync('chhss-data/feed.json'));
// Repeatable ingestion tests at the actual fixture acquisition time. Separate
// stale checks below advance the clock without relabeling the observation.
class Clock extends Date {static now() {return Date.parse(fixture.current.availableAt)+60000;}}
const context = vm.createContext({window: {crypto: webcrypto}, crypto: webcrypto,
  document: {readyState: 'loading', addEventListener() {}, dispatchEvent() {}, querySelector() {return null;}, getElementById() {return null;}},
  CustomEvent: class {}, AbortController, URL, location: {href: 'file:///Downloads/dashboard.html'}, Date:Clock, setTimeout, clearTimeout});
for (const id of ['chHssScienceCore', 'chhssDataClient', 'fdChHssEngine']) {
  const script = scripts.find(([, attributes]) => attributes.includes(`id="${id}"`));
  assert.ok(script, id);
  vm.runInContext(script[2], context);
}
(async () => {
  // Feed-change scheduling is exercised in the browser; keep this VM focused
  // on real engine contract/diagnostic functions without mounting a fake DOM.
  context.window.SpaceWxChHss.refresh=()=>{};
  const feed = structuredClone(fixture);
  feed.generatedAt = new Clock(Clock.now()).toISOString();
  const before = structuredClone(feed);
  await context.window.CHHSSData.validate(feed);
  assert.equal(feed.current.measured.mask.length, 512*512);
  assert.equal(feed.current.observationTime, before.current.observationTime);
  const bad = structuredClone(before);
  bad.current.measured.maskRuns[0] = 1-bad.current.measured.maskRuns[0];
  await assert.rejects(context.window.CHHSSData.validate(bad), /checksum/);
  const overflow = structuredClone(before);
  overflow.current.measured.maskRuns = [0, 1024*1024*1024];
  await assert.rejects(context.window.CHHSSData.validate(overflow), /run value or length/);
  const report = JSON.parse(fs.readFileSync('docs/validation/2024-q1.json'));
  await context.window.CHHSSData.validate({...structuredClone(before), verification: report});
  const audit=context.window.SpaceWxChHss.audit;
  const geometry=audit.registeredGeometry(feed.current);
  const withRGB=structuredClone(feed.current);withRGB.preview.compositeUrl='data:image/png;base64,RGB';
  assert.equal(audit.registeredGeometry(withRGB).compositeUrl,withRGB.preview.compositeUrl);
  const withoutRGB=structuredClone(feed.current);delete withoutRGB.preview.compositeUrl;
  assert.equal(audit.registeredGeometry(withoutRGB).compositeUrl,'');
  assert.ok(geometry.aiaEligibility.active);
  assert.ok(geometry.aiaEligibility.passCondition);
  assert.ok(geometry.hmiPolarity.numeric);
  assert.match(audit.renderAiaDiagnostics(geometry), /Active — registered AIA/);
  assert.match(audit.renderAiaDiagnostics(geometry), /AIA FITS acquisition provenance/);
  assert.doesNotMatch(audit.renderAiaDiagnostics(geometry), /SUVI fallback used/);
  const quality=audit.validateDataset({...geometry,sourceTime:geometry.time}).items;
  assert.equal(quality.find(q=>q.id==='aia').status,'pass');
  assert.notEqual(quality.find(q=>q.id==='hmi').status,'fail');
  const weak=structuredClone(feed.current.polarity);
  for(const k of ['E','M','W'])weak.sector[k].polarity=null;
  const weakResult=context.window.CHHSSScience.polarityRecord(weak);
  assert.equal(weakResult.numeric,true);
  assert.equal(weakResult.ok,false);
  const degraded=structuredClone(feed.current.polarity);
  degraded.degraded=true;degraded.sector.M.temporalAgreement=false;
  assert.equal(context.window.CHHSSScience.polarityRecord(degraded).sector.M.polarity,null);
  assert.equal(context.window.CHHSSScience.sciencePack(feed.current,{now:Clock.now()+7*3600000}).ok,false);
  const rows=Array.from({length:18},(_,i)=>({time_tag:`2026-08-05T${String(i).padStart(2,'0')}:00:00Z`,speed:450}));
  assert.equal(audit.persistenceAtValidTime({rows},'2026-09-01T12:00:00Z'),450);
  assert.equal(audit.persistenceAtValidTime({rows:rows.slice(1)},'2026-09-01T12:00:00Z'),null);
  const data=context.window.CHHSSData;
  // A rejected AIA mask must still allow independently validated OMNI data.
  const requests=[];
  context.fetch=async url=>{requests.push(new URL(url));return {ok:true,headers:{get(){return null;}},text:async()=>JSON.stringify(new URL(url).pathname.endsWith('recurrence.json')?before.recurrence:bad)};};
  await data.refresh(true);
  assert.equal(requests.length,2);
  assert.ok(requests.every(url=>url.searchParams.get('_chhss')===String(Clock.now())));
  assert.equal(data.getState().url,data.defaultURL);
  assert.equal(data.current(),null);
  assert.ok(data.persistenceRows().length>0);
  assert.match(data.getState().error,/checksum/);
  context.fetch=async()=>({ok:true,headers:{get(){return null;}},text:async()=>JSON.stringify(before)});
  await data.refresh(true);
  assert.ok(data.current());
  const retained=data.current().observationTime;
  const older=structuredClone(before);
  older.generatedAt=new Clock(Clock.now()-60000).toISOString();
  context.fetch=async()=>({ok:true,headers:{get(){return null;}},text:async()=>JSON.stringify(older)});
  await data.refresh(true);
  assert.equal(data.getState().feed.generatedAt,before.generatedAt);
  assert.equal(data.getState().error,'');
  assert.match(data.getState().notice,/retaining newer snapshot/);
  context.fetch=async()=>{throw Error('offline');};
  await data.refresh(true);
  assert.equal(data.current().observationTime,retained);
  assert.ok(data.persistenceRows().length>0);
  const duplicate=structuredClone(before.recurrence);duplicate.rows.push(duplicate.rows[0]);
  assert.throws(()=>data.validateRecurrence(duplicate),/duplicate/);
  console.log(`All ${scripts.length} scripts parse; registered AIA/HMI, independent OMNI, daily coverage, checksum, quality, stale and last-good gates pass.`);
})().catch(error => {console.error(error); process.exitCode=1;});

// Resizing one edge locks the other dimension; saved v2 heights are unchanged.
assert.equal(monitor.normalize([{kind:'visual',key:'helio',cols:8,rows:12,layoutVersion:2}],()=>true)[0].rows,36);
assert.equal(monitor.resize({cols:12,rows:30},504,72,1000,'height').cols,12);
assert.equal(monitor.resize({cols:12,rows:30},504,72,1000,'width').rows,30);
assert.equal(monitor.resize({cols:24,rows:30},0,-12,1000,'height').rows,29);
const protonInput=[{time_tag:'2026-09-19T05:00:00Z',energy:'>=10 MeV',flux:2},{time_tag:'2026-09-19T05:20:00Z',energy:'>=10 MeV',flux:-999},{time_tag:'2026-09-19T05:00:00Z',energy:'>=50 MeV',flux:.1},{time_tag:'invalid',energy:'>=50 MeV',flux:100}];
const proton10=particles.parseProtons(protonInput,10);
assert.equal(proton10.length,3); // Insert a real gap across an observation outage.
assert.equal(proton10[1].flux,null);
assert.equal(proton10[2].flux,null);
assert.equal(particles.parseProtons(protonInput,50)[0].flux,.1);
const protonChart=particles.protonChart({goesProtons:{payload:protonInput}},24,Date.parse('2026-09-19T06:00Z'));
assert.equal(protonChart.traces.length,2);
assert.equal(protonChart.traces[1].name,'GOES ≥50 MeV');
assert.equal(protonChart.traces[0].x.length,3); // No fabricated forecast samples.
const dose=products.window.SpaceWxNAIRAS;
const fullGrid={altitudeKm:20,unit:'mSv/h',sourceTime:'2026-09-19T04:00:00Z',latitudes:Array.from({length:181},(_,i)=>i-90),longitudes:Array.from({length:360},(_,i)=>i),values:Array(65160).fill(.01)};
fullGrid.values[0]=.02;fullGrid.values[180*360]=.03;
assert.equal(dose.valid(fullGrid),true);
assert.equal(dose.point(fullGrid,-90,0).rate,.02);
assert.equal(dose.point(fullGrid,90,360).rate,.03);
assert.equal(dose.point(fullGrid,60,-100).longitude,-100);
assert.equal(dose.point(fullGrid,91,0),null);
assert.equal(dose.status({...fullGrid,sourceTime:'2026-09-06T20:15:00Z'},'forecast',Date.parse('2026-09-19T06:00Z')).warning,true);
assert.match(dose.status(fullGrid,'forecast',Date.parse('2026-09-19T06:00Z')).text,/validity interval not supplied/);
assert.equal(dose.status(fullGrid,'nowcast',Date.parse('2026-09-19T06:00Z')).warning,false);
assert.equal(dose.status(fullGrid,'nowcast',Date.parse('2026-09-19T08:00Z')).warning,true);
const north=dose.polarGrid(fullGrid,1,2),south=dose.polarGrid(fullGrid,-1,2);
assert.equal(north.z[90][90],.06); // 2 h at .03 mSv/h
assert.equal(south.z[90][90],.04); // 2 h at .02 mSv/h
assert.equal(north.z[0][0],null); // Outside hemisphere, never fake zero.
assert.equal(north.customdata[90][90][0],90);
assert.equal(south.customdata[90][90][0],-90);
assert.equal(dose.valid({...fullGrid,unit:'µSv/h'}),false);
console.log('Adaptive-card, raw proton and NAIRAS contracts passed');
