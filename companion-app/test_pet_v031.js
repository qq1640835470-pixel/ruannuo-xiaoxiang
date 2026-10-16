"use strict";
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const M=require('./web/pet-motion.js'),P=require('./web/pet-physics.js');
let state={times:[]};
for(let n=0;n<10;n++){state=M.recordPat(state,n*700);assert.equal(state.triggered,false,'1–10 touches never sulk');}
state=M.recordPat(state,7000);assert.equal(state.triggered,true,'11 continuous quick touches sulk');
for(let n=1;n<22;n++){state=M.recordPat(state,7000+n*700);assert.equal(state.triggered,false,'15s cooldown');}
state=M.recordPat(state,22400);assert.equal(state.triggered,true,'cooldown ends');
state={times:[]};for(let n=0;n<11;n++)state=M.recordPat(state,n*801);assert.equal(state.triggered,false,'slow touches do not accumulate');
state={times:[]};for(let n=0;n<10;n++)state=M.recordPat(state,n*100);state=M.recordPat(state,1801);assert.equal(state.triggered,false,'gap resets streak');
state={times:[]};for(let n=0;n<10;n++)state=M.recordPat(state,n*800);state=M.recordPat(state,8000);assert.equal(state.triggered,true,'inclusive 8s / 800ms boundary');
const size={width:148,height:181},view={width:1280,height:720},rect={left:6,right:1274,top:6,bottom:714};
for(const edge of ['left','right','top','bottom']){
  const point=P.placement({id:'window-edge:'+edge,mode:'peek',edge,point:{x:600,y:350},rect},size,view);
  assert.ok(edge==='left'?point.x<0:edge==='right'?point.x+size.width>view.width:edge==='top'?point.y<0:point.y+size.height>view.height,'window peek actually crosses viewport '+edge);
  const result=P.dockBounds(point,size,view,{id:'window-edge:'+edge,mode:'peek',edge});assert.deepEqual(result,point);
}
assert.equal(M.activity(12,false),'idle');assert.equal(M.activity(23,false),'idle');assert.equal(M.activity(12,false,'auto',{activity:'lunch'}),'lunch');assert.equal(M.activity(2,true),'music');assert.equal(M.activity(12,false,'happy'),'happy');
const assets=path.join(__dirname,'web/assets/pet/live2d'),catalog=JSON.parse(fs.readFileSync(path.join(assets,'manifest.json')));
assert.equal(catalog.models.length,5);
for(const info of catalog.models){
  const file=path.join(__dirname,'web',info.url),model=JSON.parse(fs.readFileSync(file)),refs=model.FileReferences;
  assert.equal(model.Version,3);assert.equal(refs.Expressions.length,28);assert.equal(Object.keys(refs.Motions).length,64);
  for(const ref of [refs.Moc,...refs.Textures,...refs.Expressions.map(x=>x.File),...Object.values(refs.Motions).flat().map(x=>x.File),refs.Physics])assert.ok(fs.statSync(path.join(path.dirname(file),ref)).size>0,ref);
}
assert.ok(!fs.readFileSync(path.join(__dirname,'web/companion.js'),'utf8').includes('turnAwayUntil'));
console.log('Pet 0.3.1: rapid pat thresholds/cooldown, 4 actual window edge placements, explicit-context/music states and 5 model reference closures passed.');
