"use strict";
const assert=require('node:assert/strict');
const M=require('./web/pet-motion.js');
const from={x:50,y:400},to={x:700,y:100};
assert.deepEqual(M.travel(from,to,0),from);
assert.deepEqual(M.travel(from,to,1),to);
let previous=from;
for(let i=1;i<=120;i++){
  const point=M.travel(from,to,i/120),weights=M.blend(i/120);
  assert.ok(point.x>=previous.x&&point.x<=to.x&&point.y<=previous.y&&point.y>=to.y,'release path must stay continuous and never overshoot the component');
  assert.ok(Math.abs(weights.previous+weights.current-1)<1e-12,'pose blend must not disappear at the midpoint');
  assert.ok(weights.compression>=0&&weights.compression<=.046,'landing squash stays subtle');previous=point;
}
const interrupted=M.travel(from,to,.37),newTarget={x:20,y:30};
assert.deepEqual(M.travel(interrupted,newTarget,0),interrupted,'grabbing a moving pet starts from its current position');
assert.deepEqual(M.travel(from,to,5),to,'late frames finish exactly at the target');
assert.deepEqual(M.travel(from,to,-1),from,'early frames cannot jump before the start');
assert.ok(M.blend(0).compression===0&&Math.abs(M.blend(1).compression)<1e-12);
assert.equal(M.pat(0),0);assert.equal(M.pat(2100),0);
assert.ok(Math.abs(M.pat(1500))<Math.abs(M.pat(100)),'pat recoil settles rather than shaking forever');
assert.equal(M.eyelid(200,190),0);
assert.ok(M.eyelid(95,190)>.99,'blink reaches a fully closed phase');
console.log('Pet transition checks passed: endpoints, interruption, no overshoot, blend visibility and subtle landing squash.');

const rail={left:0,right:222,top:0,bottom:900,width:222,height:900},petSize={width:148,height:181},viewport={width:1280,height:900};
const occupied=[{top:30,bottom:70},{top:100,bottom:200},{top:740,bottom:900}];
const standing=M.sidebarPosition(rail,{x:110,y:450},petSize,viewport,occupied);
assert.ok(standing&&standing.x>=6&&standing.x+petSize.width<=216);
assert.ok(standing.y>=208&&standing.y+petSize.height<=740,'sidebar release stays in the blank interval');
assert.equal(M.sidebarPosition(rail,{x:110,y:150},petSize,viewport,occupied),null,'navigation is not blank rail space');
assert.equal(M.sidebarPosition(rail,{x:400,y:450},petSize,viewport,occupied),null,'main area retains normal falling and docking');
assert.equal(M.sidebarPosition({...rail,right:100,width:100},{x:50,y:450},petSize,viewport,occupied),null,'narrow/mobile bars cannot hold the full pet');
for(let t=0;t<=72000;t+=13){const idle=M.idle(t);assert.ok(Math.abs(idle.lean)<=.022&&Math.abs(idle.bob)<=3&&idle.sway<=2);assert.ok(Math.abs(M.greet(t))<=1);}
assert.equal(M.idle(4200).kind,'breathe');assert.ok(M.idle(4200).bob===0);
assert.equal(M.greet(-1),0);assert.equal(M.greet(2000),0);
console.log('Pet idle, greeting and blank-sidebar standing checks passed.');

// All four destination corners stay inside the canvas during a pat/regrab.
for(const ratio of [1,2])for(const angle of [-.32,-.1,0,.1,.32]){
  const c=Math.cos(angle),s=Math.sin(angle),matrix={a:c,b:s,c:-s,d:c,e:180,f:220};
  const rect={x:-164,y:-210,width:328,height:410};
  const fit=M.containSprite(matrix,rect,360,440);
  for(const [x,y] of [[rect.x,rect.y],[rect.x+rect.width,rect.y],[rect.x,rect.y+rect.height],[rect.x+rect.width,rect.y+rect.height]]){
    const px=(fit.a*x+fit.c*y+fit.e)*ratio,py=(fit.b*x+fit.d*y+fit.f)*ratio;
    assert.ok(px>=6*ratio-1e-8&&px<=354*ratio+1e-8&&py>=6*ratio-1e-8&&py<=434*ratio+1e-8,'tilted sprites must keep a clear margin at DPR1 and DPR2');
  }
  assert.ok(Math.abs(fit.a*fit.d-fit.b*fit.c)>0,'containment never flattens the sprite');
}
console.log('Pet rotated sprite containment passed at DPR1 and DPR2.');
