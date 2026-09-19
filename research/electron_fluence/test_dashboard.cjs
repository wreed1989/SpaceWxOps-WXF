const fs=require('fs'),vm=require('vm'),assert=require('assert'),path=require('path');
const source=fs.readFileSync(path.join(__dirname,'dashboard.js'),'utf8');
const canonical=fs.readFileSync(path.join(__dirname,'../../SpaceWxOps_Coronal_Hole_HSS_Outlook.html'),'utf8');
assert.strictEqual(canonical.match(/<script id="wxfElectronProduct">\n([\s\S]*?)\n<\/script>/)[1],source,'Canonical script must match reviewed source');
const context={window:{},document:{getElementById:()=>null}};vm.createContext(context);vm.runInContext(source,context);
const product=context.window.SpaceWxElectronExperiment;
const fixture=JSON.parse(fs.readFileSync(path.join(__dirname,'../../chhss-data/electron-fluence.json'),'utf8'));
assert(product.valid(fixture));
assert(!source.includes('4.8e8'));
assert(!source.includes('thresholds.severe'));
assert.deepStrictEqual(fixture.thresholds,{moderate:1.1e8});
if(fixture.status==='experimental'){
 assert(product.fresh(fixture,Date.parse(fixture.issuedAt)));
 assert(!product.fresh(fixture,Date.parse(fixture.dataAsOf)+3*3600000));
 const bad=structuredClone(fixture);bad.forecast[0].fluxLow=-1;assert(!product.valid(bad));
 const shifted=structuredClone(fixture);shifted.forecast[2].time=shifted.forecast[1].time;assert(!product.valid(shifted));
 for(const view of ['fluence','flux']){
  const c=product.chart(fixture,view);assert.strictEqual(c.layout.yaxis.range[0],0);
  assert(c.layout.hoverlabel.bgcolor==='#111e2b');
  assert(c.traces.every(t=>t.connectgaps!==true));
 }
 let overlayCalled=false;context.window.SpaceWxAlertStyle={thresholds:()=>[{value:9e8}],color:()=>'#abc',overlay:(key,max)=>{assert.strictEqual(key,'electron');assert(max>=9e8);overlayCalled=true;return{shapes:[],annotations:[]}}};
 product.chart(fixture,'fluence',true);assert(overlayCalled,'Configured alert thresholds must drive the forecast overlay');
 overlayCalled=false;const hidden=product.chart(fixture,'fluence',false);assert(!overlayCalled);assert.equal(hidden.layout.shapes.length,0,'Turning off Show threshold removes threshold overlays');
}
console.log('WXF browser contracts passed');

const huxtSource=fs.readFileSync(path.join(__dirname,'huxt_dashboard.js'),'utf8');
assert.strictEqual(canonical.match(/<script id="localHuxtProduct">\n([\s\S]*?)\n<\/script>/)[1],huxtSource);
const huxtContext={window:{},document:{getElementById:()=>null}};vm.createContext(huxtContext);vm.runInContext(huxtSource,huxtContext);
const huxtFixture=JSON.parse(fs.readFileSync(path.join(__dirname,'../../chhss-data/huxt-forecast.json'),'utf8'));
assert(huxtContext.window.SpaceWxLocalHUXt.valid(huxtFixture));
if(huxtFixture.status==='experimental'){
 const c=huxtContext.window.SpaceWxLocalHUXt.chart(huxtFixture);assert.equal(c.traces.length,2);assert.equal(c.layout.yaxis.range[0],0);assert.equal(c.layout.hoverlabel.bgcolor,'#111e2b');
 const bad=structuredClone(huxtFixture);bad.rows[0].cmeSpeed=-1;assert(!huxtContext.window.SpaceWxLocalHUXt.valid(bad));
}
if(fixture.candidate){assert(product.valid(fixture.candidate));assert.equal(fixture.candidate.role,'shadow candidate');}
console.log('Local HUXt numerical plot and candidate contracts passed');
