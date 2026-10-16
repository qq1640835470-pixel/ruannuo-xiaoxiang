"use strict";
const assert=require('node:assert/strict'),D=require('./web/daylight.js');
assert.equal(D.phase(0),'深夜');assert.equal(D.phase(6),'清晨');assert.equal(D.phase(10),'上午');assert.equal(D.phase(13),'午间');assert.equal(D.phase(16),'下午');assert.equal(D.phase(19),'傍晚');assert.equal(D.phase(23),'夜晚');
assert.deepEqual(D.palette(0),D.palette(24));assert.deepEqual(D.palette(-1),D.palette(23));
const rgb=h=>h.match(/[0-9a-f]{2}/gi).map(s=>parseInt(s,16));
for(let i=0;i<1440;i++){
 const a=D.palette(i/60),b=D.palette((i+1)/60);
 for(const key of ['sky','rail','accent']){
  assert.match(a[key],/^#[0-9a-f]{6}$/);assert.ok(rgb(a[key]).every((v,j)=>Math.abs(v-rgb(b[key])[j])<=1),'no hard color jump at a minute or phase boundary');
 }
}
assert.notEqual(D.palette(8).rail,D.palette(23).rail);
assert.ok(D.palette(12).glow>D.palette(0).glow,'night gradient is less bright than noon');
console.log('Time-theme checks passed: seven periods, midnight wrap, 1440 smooth minute boundaries and day/night difference.');
