// Exercise the actual inline client against the published producer contract.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const {webcrypto} = require('node:crypto');
const html = fs.readFileSync('SpaceWxOps_Coronal_Hole_HSS_Outlook.html', 'utf8');
const scripts = [...html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/g)];
for (const [, , code] of scripts) new vm.Script(code);
const context = vm.createContext({window: {crypto: webcrypto}, crypto: webcrypto,
  document: {readyState: 'loading', addEventListener() {}, querySelector() {return null;}},
  URL, location: {href: 'https://example.test/'}, Date, setTimeout, clearTimeout});
for (const id of ['chHssScienceCore', 'chhssDataClient']) {
  const script = scripts.find(([, attributes]) => attributes.includes(`id="${id}"`));
  assert.ok(script, id);
  vm.runInContext(script[2], context);
}
(async () => {
  const feed = JSON.parse(fs.readFileSync('chhss-data/feed.json'));
  feed.generatedAt = new Date().toISOString();
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
  console.log(`All ${scripts.length} dashboard scripts parse; measured feed, report, checksum and size gates pass.`);
})().catch(error => {console.error(error); process.exitCode=1;});
