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
// Alert edits use the same live rule object for Monitor and model plots.
const configured={proton:{yellow:10,red:40,purple:1000},proton50:{red:10},electron:{yellow:1.1e8,red:4.8e8}};
const styleContext=vm.createContext({window:{},state:{rules:configured},isLightTheme:()=>false,readableThresholdColor:c=>c});
for(const name of ['transparentize','alertLevelFromRule','particleThresholds','particleAlertColor','particleThresholdOverlay','particleRange','particleLinearAxis','hoverLabelStyle']){
  vm.runInContext(html.match(new RegExp('      function '+name+'\\([^]*?\\n      \\}'))[0],styleContext);
}
products.window.SpaceWxAlertStyle={thresholds:styleContext.particleThresholds,color:styleContext.particleAlertColor,overlay:styleContext.particleThresholdOverlay,axis:styleContext.particleLinearAxis,range:styleContext.particleRange,hover:styleContext.hoverLabelStyle};

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
assert.equal(north.z[180][180],.06); // 2 h at .03 mSv/h
assert.equal(south.z[180][180],.04); // 2 h at .02 mSv/h
assert.equal(north.z[0][0],null); // Outside hemisphere, never fake zero.
assert.equal(north.customdata[180][180][0],90);
assert.equal(south.customdata[180][180][0],-90);
assert.equal(dose.valid({...fullGrid,unit:'µSv/h'}),false);
console.log('Adaptive-card, raw proton and NAIRAS contracts passed');

const highProtons=protonInput.map(r=>({...r,flux:r.energy==='>=10 MeV'?100:20}));
let styled=particles.protonChart({goesProtons:{payload:highProtons}},24,Date.parse('2026-09-19T06:00Z'));
assert.ok(styled.layout.shapes.some(s=>s.yref==='y'&&s.y0===40&&s.type==='line'));
assert.ok(styled.layout.shapes.some(s=>s.yref==='y2'&&s.y0===10&&s.type==='line'));
assert.ok(!styled.layout.shapes.some(s=>s.yref==='y2'&&s.y0===40));
configured.proton.yellow=25;configured.proton50.red=5;configured.electron.yellow=8e7;
styled=particles.protonChart({goesProtons:{payload:highProtons}},24,Date.parse('2026-09-19T06:00Z'));
assert.ok(styled.layout.shapes.some(s=>s.yref==='y'&&s.y0===25));
assert.ok(styled.layout.shapes.some(s=>s.yref==='y2'&&s.y0===5));
let refmChart=particles.refmChart(refm);
assert.equal(refmChart.traces[1].marker.color[0],'#facc15');
assert.equal(refmChart.traces[1].y[1],null);
assert.ok(refmChart.layout.annotations.some(a=>a.y===8e7));
configured.electron.yellow=2e8;
refmChart=particles.refmChart(refm);
assert.equal(refmChart.traces[1].marker.color[0],'#38bdf8');
assert.ok(refmChart.layout.shapes.some(s=>s.y0===2e8));
assert.equal(styleContext.particleAlertColor('proton50',5),'#ef4444');
configured.proton.red=20; // Existing settings allow arbitrary threshold ordering.
assert.equal(styleContext.particleThresholdOverlay('proton',200).shapes.find(s=>s.type==='rect'&&s.y0===25).fillcolor,'rgba(239,68,68,0.065)');
assert.doesNotMatch(desk,/Alternate Panel|"ALT"/);

// Each independent catalog panel can render without activating the legacy tab.
const renderCalls=[];
const renderContext=vm.createContext({currentValues:()=>({live:true}),renderShiftSolarWind:v=>renderCalls.push(['wind',v.live])});
for(const suffix of ['Xray','Proton','Epam','ElectronFlux','ElectronFluence','Ap','Timeline'])renderContext['renderShift'+suffix]=()=>renderCalls.push([suffix]);
vm.runInContext(html.match(/      function renderCatalogObservations\(keys\) \{[\s\S]*?\n      \}/)[0],renderContext);
renderContext.renderCatalogObservations(['brief.imf','brief.speed','brief.density','brief.xray','brief.proton','brief.epam','brief.electron-flux']);
assert.deepEqual(renderCalls,[['wind',true],['Xray'],['Proton'],['Epam'],['ElectronFlux']]);

// Wheel events over a plot move the page; modifier gestures remain untouched.
const scrollArea={scrollTop:500,clientHeight:800};let prevented=0,stopped=0;
const wheelContext=vm.createContext({stage:{closest:()=>scrollArea}});
vm.runInContext(desk.match(/  function scrollMonitorPage\(event\) \{[\s\S]*?\n  \}/)[0],wheelContext);
const wheel={target:{closest:()=>true},deltaY:-100,deltaMode:0,preventDefault:()=>prevented++,stopPropagation:()=>stopped++};
wheelContext.scrollMonitorPage(wheel);assert.equal(scrollArea.scrollTop,400);
wheelContext.scrollMonitorPage({...wheel,deltaY:2,deltaMode:1});assert.equal(scrollArea.scrollTop,432);
wheelContext.scrollMonitorPage({...wheel,deltaY:1,deltaMode:2});assert.equal(scrollArea.scrollTop,1232);
for(const modifier of ['ctrlKey','metaKey','shiftKey'])wheelContext.scrollMonitorPage({...wheel,[modifier]:true});
wheelContext.scrollMonitorPage({...wheel,target:{closest:()=>false}});
assert.equal(scrollArea.scrollTop,1232);assert.equal(prevented,3);assert.equal(stopped,3);
vm.runInContext(scripts.find(([,a])=>a.includes('id="productFlow"'))[2],products);
assert.equal(products.window.SpaceWxProductFlow.rowsForContent(54,600,30),54);
assert.equal(products.window.SpaceWxProductFlow.rowsForContent(54,1400,30),120);
console.log('Live alert rules, independent catalog rendering, wheel routing and disclosure layout passed');

// Hard zero floor, quiet 0–15 flux range, proportional headroom, and opaque hovers.
assert.deepEqual(Array.from(protonChart.layout.yaxis.range),[0,15]);
assert.deepEqual(Array.from(protonChart.layout.yaxis2.range),[0,15]);
assert.equal(protonChart.layout.yaxis.minallowed,0);
assert.equal(protonChart.layout.yaxis.type,'linear');
assert.deepEqual(Array.from(styleContext.particleRange([null,NaN,-999,0,12])),[0,15]);
assert.deepEqual(Array.from(styleContext.particleRange([20])),[0,25]);
assert.deepEqual(Array.from(styled.layout.yaxis.range),[0,125]);
assert.ok(!protonChart.layout.shapes.some(s=>s.y0===40)); // Thresholds cannot stretch a quiet plot.
assert.ok(styled.layout.annotations.every(a=>!/(red|yellow|purple)/i.test(a.text)));
assert.equal(styleContext.hoverLabelStyle().bgcolor,'#111820');
assert.equal(protonChart.layout.hoverlabel.bgcolor,'#111820');
assert.equal(particles.parseProtons([{time_tag:'2026-09-19T05:00Z',energy:'>=10 MeV',flux:0}],10)[0].flux,0);
assert.equal(refmChart.layout.yaxis.type,'linear');
assert.equal(refmChart.layout.yaxis.range[0],0);
assert.equal(refmChart.layout.yaxis.minallowed,0);
assert.ok(refmChart.layout.yaxis.range[1]>=2.2e8*1.25);
assert.equal(traces[1].name,'13-Month SSN Avg');
assert.equal(traces[4].name,'Predicted SSN');
assert.match(traces[3].hovertemplate,/Predicted SSN Range:/);
assert.deepEqual(Array.from(traces[3].customdata[0]),[0,13.6]);
assert.equal(traces[2].hoverinfo,'skip');
const mapChart=dose.chart(fullGrid,2,false,{lat:60,lon:-100});
assert.equal(mapChart.traces[0].z.length,361);
assert.equal(mapChart.traces[0].coloraxis,mapChart.traces[4].coloraxis);
assert.ok(mapChart.layout.coloraxis.cmax>=.06);
assert.equal(mapChart.layout.coloraxis.colorbar.orientation,'h');
assert.ok(mapChart.traces.some(t=>t.marker?.symbol==='circle-open'));
assert.equal(mapChart.layout.hoverlabel.bgcolor,'#102534');

// Live satellite screening never treats stale/missing/partial coverage as nominal.
products.document.addEventListener=()=>{};
vm.runInContext(scripts.find(([,a])=>a.includes('id="satelliteRiskScene"'))[2],products);
const risk=products.window.SpaceWxSatelliteRisk;
const now=Date.parse('2026-09-19T06:00Z'),time=new Date(now).toISOString();
let policyValues;
const policy=values=>{policyValues=values;return Object.fromEntries(['LEO','MEO','GEO','HEO'].map(o=>[o,values.proton>=10?[{level:2}]:[]]));};
const samples={ap:{value:5,time},proton:{value:2,time},electron:{value:2e7,time,coverageOK:true,protonCheckOK:true}};
let riskModel=risk.derive({samples},now,policy);
assert.equal(riskModel.complete,true);assert.equal(risk.label(riskModel,'LEO'),'Below triggers');
riskModel=risk.derive({samples:{...samples,proton:{value:100,time}}},now,policy);
assert.equal(risk.label(riskModel,'GEO'),'Trigger 2 · partial');
riskModel=risk.derive({samples:{...samples,electron:{value:2e7,time,coverageOK:false},proton:{value:100,time}}},now,policy);
assert.equal(riskModel.complete,false);assert.equal(risk.label(riskModel,'GEO'),'Trigger 2 · partial');assert.ok(Number.isNaN(policyValues.electron));
riskModel=risk.derive({samples:{...samples,electron:{value:2e7,time,coverageOK:false}}},now,policy);
assert.equal(risk.label(riskModel,'GEO'),'Incomplete');
riskModel=risk.derive({samples},now+5*3600000,policy);
assert.equal(risk.label(riskModel,'GEO'),'Unavailable');assert.ok(Number.isNaN(policyValues.proton));
assert.equal(risk.label(risk.derive({samples,archive:true},now,policy),'GEO'),'Unavailable');
assert.equal(risk.derive({samples:{ap:{value:-1,time},proton:{value:20,time:'invalid'},electron:{value:1e8,time:new Date(now+3600000).toISOString()}}},now,policy).anyFresh,false);
const coverageContext=vm.createContext({timeOf:r=>r.time_tag,toNumber:v=>v==null?NaN:Number(v)});
vm.runInContext(html.match(/      function electronCoverageHours\(rows, windowEnd\) \{[^]*?\n      \}/)[0],coverageContext);
const coverageRows=Array.from({length:289},(_,i)=>({time_tag:new Date(now-i*300000).toISOString(),flux:0}));
assert.equal(coverageContext.electronCoverageHours(coverageRows),24);
assert.equal(coverageContext.electronCoverageHours(coverageRows.slice(0,100)),8.25);
assert.ok(coverageContext.electronCoverageHours(coverageRows.filter((_,i)=>i<100||i>140))<23);
console.log('Particle bounds, tooltip contrast, solar cycle labels, polar maps and satellite freshness passed');

// Ap represents a three-hour interval; its end is not a future observation.
const runningAp={value:12,time:'2026-09-19T06:00Z',validThrough:'2026-09-19T09:00Z'};
assert.equal(risk.derive({samples:{ap:runningAp}},now+3600000,policy).samples.ap.fresh,true);
assert.equal(risk.derive({samples:{ap:runningAp}},now+8*3600000,policy).samples.ap.fresh,false);
vm.runInContext(html.match(/      function riskContributorThreshold\([^]*?\n      \}/)[0],styleContext);
assert.equal(styleContext.riskContributorThreshold('proton_flux_10',10),25);
assert.equal(styleContext.riskContributorThreshold('electron_fluence',1.1e8),2e8);

// Belt shading follows a fresh GEO electron sample, independently of Ap and
// 24-hour fluence. Preview data must remain detached from the live telemetry.
const beltInput={samples:structuredClone(samples),electronFlux:{value:80,time}};
const liveBelt=risk.beltState(beltInput,risk.derive(beltInput,now,policy),'live',now);
assert.equal(liveBelt.loadingKnown,true);
const loadedInput={...beltInput,electronFlux:{value:8000,time}};
assert.ok(risk.beltState(loadedInput,risk.derive(loadedInput,now,policy),'live',now).intensity>liveBelt.intensity);
const staleFlux={...beltInput,electronFlux:{value:8000,time:new Date(now-21*60000).toISOString()}};
assert.equal(risk.beltState(staleFlux,risk.derive(staleFlux,now,policy),'live',now).loadingKnown,false);
const contam={...beltInput,samples:{...samples,proton:{value:10,time}}};
assert.equal(risk.beltState(contam,risk.derive(contam,now,policy),'live',now).contaminated,true);
assert.equal(risk.beltState(contam,risk.derive(contam,now,policy),'live',now).loadingKnown,false);
const noProton={...beltInput,samples:{ap:samples.ap,electron:samples.electron}};
assert.equal(risk.beltState(noProton,risk.derive(noProton,now,policy),'live',now).loadingKnown,false);
assert.equal(risk.beltState({...beltInput,archive:true},risk.derive({...beltInput,archive:true},now,policy),'live',now).loadingKnown,false);
const scenarios=Object.fromEntries(['quiet','storm','recovery'].map(mode=>{const s=risk.previewSnapshot(mode,now);return [mode,risk.beltState(s,risk.derive(s,now,policy),mode,now)];}));
assert.ok(scenarios.storm.inner<scenarios.quiet.inner); // Inward extension.
assert.ok(scenarios.storm.outer<scenarios.quiet.outer); // Outer-edge compression.
assert.ok(scenarios.storm.intensity<scenarios.quiet.intensity); // Dropout, not automatic storm loading.
assert.ok(scenarios.recovery.intensity>scenarios.quiet.intensity);
assert.ok(scenarios.recovery.outer>scenarios.storm.outer);
assert.equal(risk.previewSnapshot('live',now),null);
assert.equal(beltInput.electronFlux.value,80);
assert.equal(beltInput.samples.proton.value,2);
assert.ok(Math.abs(Math.hypot(...risk.orbitPoint('GEO',1.2))-6.61)<1e-9);
assert.ok(Math.abs(Math.hypot(...risk.orbitPoint('MEO',1.2))-4.17)<1e-9);
assert.ok(Math.abs(Math.hypot(...risk.orbitPoint('HEO',0))-1.15)<1e-9);
assert.ok(Math.abs(Math.hypot(...risk.orbitPoint('HEO',Math.PI))-7.2)<1e-9);
assert.ok(Math.abs(Math.hypot(...risk.beltPoint(4,.2,.6))-4*Math.cos(.2)**2)<1e-9);
for(const mode of ['Quiet','Storm','Recovery']){
 assert.ok(risk.markup().includes('Preview: '+mode));
 assert.ok(scripts.find(([,a])=>a.includes('id="spaceWxHeliosphereEngine"'))[2].includes('Preview: '+mode));
}
assert.doesNotMatch(html,/Preview: (quiet|storm|recovery)/);
console.log('Belt geometry, energy proxy, proton contamination gate and isolated scenarios passed');

// Particle populations respond to the matching fresh measurement, not an
// unrelated activity score. Solar protons never masquerade as trapped protons.
const densityFor=input=>risk.beltState(input,risk.derive(input,now,policy),'live',now);
const lowParticles=risk.particleCounts(liveBelt),highParticles=risk.particleCounts(densityFor(loadedInput));
assert.ok(highParticles.electrons>lowParticles.electrons);
assert.ok(highParticles.electronTracers>lowParticles.electronTracers);
const protonSurge={...beltInput,samples:{...samples,proton:{value:1000,time}}};
const surgeParticles=risk.particleCounts(densityFor(protonSurge));
assert.ok(surgeParticles.solarProtons>lowParticles.solarProtons);
assert.equal(surgeParticles.inner,lowParticles.inner);
assert.equal(surgeParticles.electronTracers,0); // Potential contamination.
assert.ok(surgeParticles.electrons>0); // Unknown is a reference, not no belt.
const geomagneticOnly={...beltInput,samples:{...samples,ap:{value:150,time}}};
assert.deepEqual(risk.particleCounts(densityFor(geomagneticOnly)),lowParticles);
const oldProton={...beltInput,samples:{...samples,proton:{value:1000,time:new Date(now-21*60000).toISOString()}}};
assert.equal(risk.particleCounts(densityFor(oldProton)).solarProtons,0);
assert.equal(risk.particleCounts(densityFor({...protonSurge,archive:true})).solarProtons,0);
const noFlux=densityFor({...beltInput,electronFlux:{value:0,time},samples:{...samples,proton:{value:0,time}}});
assert.equal(noFlux.loadingKnown,true);
assert.equal(risk.particleCounts(noFlux).solarProtons,0);
assert.ok(risk.particleCounts(noFlux).electrons<lowParticles.electrons);
for(const flux of [0,.2,8,80,1000,10000,1e20]){
 const particles=risk.particleCounts(densityFor({...beltInput,electronFlux:{value:flux,time}}));
 assert.ok(particles.electrons>=0&&particles.electrons<=5200);
 assert.ok(particles.electronTracers>=0&&particles.electronTracers<=80);
}
assert.ok(risk.particleCounts(scenarios.storm).electrons<risk.particleCounts(scenarios.quiet).electrons);
assert.ok(risk.particleCounts(scenarios.recovery).electrons>risk.particleCounts(scenarios.quiet).electrons);
const sceneScript=scripts.find(([,a])=>a.includes('id="satelliteRiskScene"'))[2];
assert.doesNotMatch(sceneScript,/cutaway|for\(const lon of \[\.18,1\.22\]\)/i);
assert.match(risk.markup(),/aria-label="About radiation belts and satellite effects"[^>]*>i<\/button>/);
for(const topic of ['Surface charging:','Internal charging:','Single-event effects:','Why the risks differ by orbit','Satellite Drag']){
 assert.ok(topic==='Satellite Drag'?html.includes(topic):risk.markup().includes(topic));
}
console.log('Complete belts, measurement-driven particle counts and orbit-aware charging explainer passed');

// The surface/internal distinction must hold in the real policy, not just in
// explanatory text. Storm activity screens drag only for LEO.
const policyContext=vm.createContext({Number,state:{rules:{}},scientific:String,fmt:String});
vm.runInContext(html.match(/      const RISK_RULES = \[[^]*?\n      \];/)[0]+'\n'+[
 'calculateSatelliteRisk','riskContributorThreshold','riskPhenomenonLabel','formatRiskThreshold'
].map(name=>html.match(new RegExp('      function '+name+'\\([^]*?\\n      \\}'))[0]).join('\n'),policyContext);
const loadedRisk=policyContext.calculateSatelliteRisk(5,.2,6e8);
assert.ok(loadedRisk.GEO.some(r=>r.risk==='Internal Charging'));
assert.ok(!Object.values(loadedRisk).flat().some(r=>r.risk==='Surface Charging'));
const stormRisk=policyContext.calculateSatelliteRisk(150,.2,1e7);
assert.ok(stormRisk.LEO.some(r=>r.risk==='Satellite Drag'));
assert.ok(stormRisk.GEO.some(r=>r.risk==='Surface Charging'));
assert.ok(!stormRisk.GEO.some(r=>r.risk==='Satellite Drag'||r.risk==='Internal Charging'));
policyContext.state.rules={electron:{yellow:7e8,red:8e8}};
assert.ok(!policyContext.calculateSatelliteRisk(5,.2,6e8).GEO.some(r=>r.risk==='Internal Charging'));
console.log('Surface/internal charging separation, LEO drag and saved-threshold policy passed');

// Screening is a highest-trigger classification, never a probability or dose.
policyContext.state.rules={ap:{yellow:32,red:56,purple:111},proton:{yellow:10,red:40,purple:1000},electron:{yellow:1.1e8,red:4.8e8}};
assert.equal(policyContext.calculateSatelliteRisk(56,0,0).LEO.find(r=>r.risk==='Satellite Drag').level,2);
assert.equal(policyContext.calculateSatelliteRisk(111,0,0).LEO.find(r=>r.risk==='Surface Charging').level,3);
assert.equal(policyContext.calculateSatelliteRisk(0,40,0).GEO.find(r=>r.risk==='Single Event Upsets').level,2);
assert.equal(policyContext.calculateSatelliteRisk(0,0,4.8e8).GEO.find(r=>r.risk==='Internal Charging').level,2);
assert.equal(Object.values(policyContext.calculateSatelliteRisk(NaN,NaN,NaN)).flat().length,0);
assert.ok(!Object.values(policyContext.calculateSatelliteRisk(150,2000,6e8)).flat().some(r=>/Dose|Cumulative/.test(r.risk)));
assert.ok(!policyContext.calculateSatelliteRisk(0,0,6e8).LEO.some(r=>r.risk==='Internal Charging'));
const policyFn=v=>policyContext.calculateSatelliteRisk(v.ap,v.proton,v.electron);
for(const mode of ['quiet','storm','recovery']){
 const snapshot=risk.previewSnapshot(mode,now),model=risk.derive(snapshot,now,policyFn);
 assert.equal(model.complete,true);
 assert.equal(model.levels.GEO,mode==='storm'?3:mode==='recovery'?2:0);
 assert.equal(model.levels.LEO,mode==='storm'?3:0);
}
const contaminatedModel=risk.derive(contam,now,policyFn);
assert.ok(Number.isNaN(contaminatedModel.values.electron));
assert.equal(contaminatedModel.complete,false);
assert.ok(!contaminatedModel.matrix.GEO.some(r=>r.risk==='Internal Charging'));
assert.equal(risk.beltState({...beltInput,electronFlux:{value:80,time:new Date(now-15*60000).toISOString()}},risk.derive(beltInput,now,policy),'live',now).loadingKnown,false);

// Fluence integrates a clipped 24 h window in seconds. It never bridges a long
// outage, double-counts duplicate timestamps, or integrates negative sentinels.
coverageContext.byTime=(a,b)=>Date.parse(a.time_tag)-Date.parse(b.time_tag);
vm.runInContext(['electronFluenceRows','electronProtonWindowQuality'].map(name=>html.match(new RegExp('      function '+name+'\\([^]*?\\n      \\}'))[0]).join('\n'),coverageContext);
const fullFlux=Array.from({length:301},(_,i)=>({time_tag:new Date(now-(300-i)*300000).toISOString(),flux:100}));
assert.equal(coverageContext.electronFluenceRows(fullFlux).at(-1).fluence,8640000);
assert.equal(coverageContext.electronFluenceRows(fullFlux).at(-1).coverageHours,24);
const gapFlux=fullFlux.filter((_,i)=>i<100||i>130);
assert.ok(coverageContext.electronFluenceRows(gapFlux).at(-1).coverageHours<23);
assert.ok(Math.abs(coverageContext.electronFluenceRows(gapFlux).at(-1).fluence-100*coverageContext.electronFluenceRows(gapFlux).at(-1).coverageHours*3600)<1e-6);
assert.equal(coverageContext.electronFluenceRows([...fullFlux,fullFlux[50],{time_tag:time,flux:-99999}]).at(-1).fluence,8640000);
const ramp=[{time_tag:new Date(now-24*3600000-150000).toISOString(),flux:0},{time_tag:new Date(now-24*3600000+150000).toISOString(),flux:100},{time_tag:time,flux:100}];
assert.equal(coverageContext.electronFluenceRows(ramp).at(-1).fluence,11250); // Half of first trapezoid only; huge gap omitted.
const protonHistory=fullFlux.map(row=>({...row,flux:1}));
assert.equal(coverageContext.electronProtonWindowQuality(fullFlux,protonHistory).protonCheckOK,true);
const oldEvent=protonHistory.map((row,i)=>({...row,flux:i===200?10:1}));
const affected=coverageContext.electronProtonWindowQuality(fullFlux,oldEvent);
assert.equal(affected.protonCheckOK,false);
assert.match(affected.qualityReason,/Proton event/);
assert.equal(coverageContext.electronProtonWindowQuality(fullFlux,protonHistory.slice(30)).protonCheckOK,false);
assert.equal(coverageContext.electronProtonWindowQuality(fullFlux,protonHistory.slice(0,-4)).protonCheckOK,false); // Ends before electron window.
assert.equal(coverageContext.electronProtonWindowQuality([],[]).protonCheckOK,false);
const postEvent={...beltInput,samples:{...samples,electron:{...samples.electron,...affected}}};
assert.equal(risk.derive(postEvent,now,policyFn).samples.electron.fresh,false);
assert.equal(risk.beltState(postEvent,risk.derive(postEvent,now,policyFn),'live',now).loadingKnown,true); // Current flux can recover before the contaminated fluence window clears.
assert.doesNotMatch(html,/probability of Surface Charging|probability of Single Event Upsets|High SEU and Total Dose risk/);
console.log('Scientific screening, exact configured triggers, preview parity, contamination history and fluence integration passed');
