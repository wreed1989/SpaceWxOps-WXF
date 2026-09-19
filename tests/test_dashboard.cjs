// Exercise the actual inline client against the published producer contract.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const {webcrypto} = require('node:crypto');
const html = fs.readFileSync('SpaceWxOps_Coronal_Hole_HSS_Outlook.html', 'utf8');
const scripts = [...html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/g)];
for (const [, , code] of scripts) new vm.Script(code);
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
  context.fetch=async()=>{throw Error('offline');};
  await data.refresh(true);
  assert.equal(data.current().observationTime,retained);
  assert.ok(data.persistenceRows().length>0);
  const duplicate=structuredClone(before.recurrence);duplicate.rows.push(duplicate.rows[0]);
  assert.throws(()=>data.validateRecurrence(duplicate),/duplicate/);
  console.log(`All ${scripts.length} scripts parse; registered AIA/HMI, independent OMNI, daily coverage, checksum, quality, stale and last-good gates pass.`);
})().catch(error => {console.error(error); process.exitCode=1;});
