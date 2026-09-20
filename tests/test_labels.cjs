const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const code=fs.readFileSync('scripts/dashboard_labels.js','utf8');
const html=fs.readFileSync('SpaceWxOps_Coronal_Hole_HSS_Outlook.html','utf8');
assert.equal(html.match(/<script id="deskLabelPresentation">([^]*?)<\/script>/)[1].trim(),code.trim());
const context=vm.createContext({window:{}});vm.runInContext(code,context);const labels=context.window.SpaceWxLabels;
assert.equal(labels.format('Particle & flare history'),'Particle & Flare History');
assert.equal(labels.format('Latitude · north +'),'Latitude: N(+) S(-)');
assert.equal(labels.format('Longitude · west +'),'Longitude: W(+) E(-)');
const scientific='F10.7 · mSv/h · 2 MeV · nT · 1.1e+8 · HUXt · PyCAT · pfu · Kp · ap60';
assert.equal(labels.format(scientific),scientific);
assert.equal(labels.format('i'),'i');
// Native selects must retain their values even when the option has no explicit value attribute.
const attrs={},option={tagName:'OPTION',textContent:'Current · default',closest:()=>null,getAttribute:k=>attrs[k]??null,setAttribute:(k,v)=>attrs[k]=v,get value(){return attrs.value??this.textContent;}};
labels.apply(option);assert.equal(option.value,'Current · default');assert.equal(attrs.label,'Current · Default');
assert.equal(option.textContent,'Current · default');labels.apply(option);assert.equal(option.value,'Current · default');
console.log('Label formatting preserves units, notation, acronyms and native option values');
