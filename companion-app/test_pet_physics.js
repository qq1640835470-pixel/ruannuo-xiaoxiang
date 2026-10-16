"use strict";
const assert=require('node:assert/strict');
const P=require('./web/pet-physics.js');
const size={width:148,height:181},view={width:1280,height:720};
const composer={id:'composer',rect:{left:322,right:1182,top:565,bottom:675}};
const bar={id:'topbar',rect:{left:226,right:1280,top:0,bottom:112}};
let dock=P.chooseDock({x:700,y:562},size,[composer,bar],view);
assert.equal(dock.id,'composer');assert.equal(dock.mode,'sit');
assert.equal(P.placement(dock,size,view).y,565-181*.79);
assert.equal(P.chooseDock({x:700,y:562},size,[composer],view,true).mode,'peek');
dock=P.chooseDock({x:720,y:112},size,[bar],view);assert.equal(dock.mode,'hang');
dock=P.chooseDock({x:322,y:610},size,[composer],view);assert.equal(dock.mode,'peek');assert.equal(dock.edge,'left');
assert.equal(P.chooseDock({x:700,y:400},size,[composer],view),null);
assert.equal(P.chooseDock({x:700,y:675},size,[composer],view),null,'bottom hanging cannot extend outside window');
let target=P.landing({x:650,y:200},size,[composer],view);assert.equal(target.id,'composer');
target=P.landing({x:30,y:400},size,[composer],view);assert.equal(target.id,'window-floor');
for(const p of [{x:-800,y:-10},{x:9000,y:9000},{x:500,y:400}]){
  const b=P.bounded(p,size,view);assert.ok(b.x>=6&&b.y>=6);assert.ok(b.x+size.width<=view.width-6&&b.y+size.height<=view.height-6);
}
const small=P.bounded({x:900,y:800},size,{width:300,height:350});assert.equal(small.x,146);assert.equal(small.y,163);
console.log('Pet geometry checks passed: edge docking, hiding, fitting, falling and viewport bounds.');
