'use strict';
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const nodes=new Map(),listeners={},events=[],calls=[],revoked=[];
class Node {
  constructor(){this.children=[];this.handlers={};this.value='';this.paused=true;this.ended=false;this.volume=1;this.attrs={};}
  addEventListener(name,fn){(this.handlers[name]??=[]).push(fn);}
  emit(name,event={}){for(const fn of this.handlers[name]||[])fn(event);}
  click(){this.emit('click');}
  focus(){this.focused=true;}
  showModal(){this.open=true;}
  append(...items){this.children.push(...items);}
  replaceChildren(...items){this.children=items;}
  setAttribute(k,v){this.attrs[k]=v;}
  removeAttribute(k){delete this.attrs[k];if(k==='src')this.src='';}
  getAttribute(k){return k==='src'?this.src:this.attrs[k];}
  pause(){this.paused=true;this.emit('pause');}
  async play(){this.paused=false;this.emit('play');}
  load(){this.emit('emptied');}
}
const select=s=>{if(!nodes.has(s))nodes.set(s,new Node());return nodes.get(s);};
const context=vm.createContext({console,document:{querySelector:select,createElement:()=>new Node(),documentElement:{style:{setProperty(){}},dataset:{}}},window:{addEventListener:(name,fn)=>{(listeners[name]??=[]).push(fn);},dispatchEvent:e=>{events.push(e);for(const fn of listeners[e.type]||[])fn(e);}},CustomEvent:class{constructor(type,options){this.type=type;this.detail=options?.detail;}},setTimeout,clearTimeout,URL:{createObjectURL:f=>'blob:'+f.name,revokeObjectURL:url=>revoked.push(url)},fetch:async path=>{calls.push(path);return {ok:true,json:async()=>path.includes('/url?')?{available:true,url:'https://m10.music.126.net/fixture.mp3'}:{preferences:{},permissions:[]}};}});
vm.runInContext(fs.readFileSync('web/workspace-tools.js','utf8'),context);
const dispatch=(type,detail)=>{for(const fn of listeners[type]||[])fn({detail});};const flush=()=>new Promise(r=>setImmediate(r));const latest=()=>events.filter(e=>e.type==='xy:music-state').at(-1).detail;
(async()=>{
  select('#music-files').emit('change',{target:{files:[{name:'local.mp3'}]}});assert.equal(select('#music-list').children.length,1);
  select('#music-list').children[0].emit('click');await flush();assert.equal(latest().playing,true);assert.equal(latest().title,'local.mp3');
  dispatch('xy:music-select',{id:42,name:'远程歌曲',artists:'歌手',remote:true});await flush();assert.equal(select('#music-list').children.length,2,'search selection preserves local files');assert.equal(latest().title,'远程歌曲');assert.equal(latest().artist,'歌手');assert.equal(latest().playing,true);assert(calls.some(p=>p==='/api/music/url?id=42'));
  await context.window.XYMusic.toggle();assert.equal(latest().playing,false);await context.window.XYMusic.toggle();assert.equal(latest().playing,true);
  await context.window.XYMusic.previous();assert.equal(latest().title,'local.mp3');assert.equal(revoked.length,0);
  dispatch('xy:music-queue',{tracks:[{id:55,name:'歌单',remote:true}],append:false});assert.equal(latest().title,'');assert.equal(latest().playing,false);assert.deepEqual(revoked,['blob:local.mp3']);
  select('#music-next').emit('click');await flush();assert.equal(latest().title,'歌单');
  context.document.body=new Node();context.innerWidth=1000;context.innerHeight=700;
  select('#pet-canvas').getBoundingClientRect=()=>({left:750,right:950,top:300,width:200,height:300});
  const make=context.document.createElement;context.document.createElement=()=>{const n=make();n.style={};n.offsetWidth=224;n.offsetHeight=100;return n;};
  context.setTimeout=()=>1;context.clearTimeout=()=>{};
  vm.runInContext(fs.readFileSync('web/music-pet.js','utf8'),context);
  const bubble=context.document.body.children[0],summary=bubble.children[0],panel=bubble.children[1];
  assert.equal(bubble.hidden,false);assert.equal(summary.textContent,'♫ 歌单');assert.equal(parseInt(bubble.style.left),546,'bubble stays inside viewport on right edge');
  summary.emit('click');assert.equal(panel.hidden,false);assert.equal(summary.attrs['aria-expanded'],'true');
  const volume=panel.children[1].children[0];volume.value='0.3';volume.emit('input');assert.equal(select('#music-audio').volume,0.3);
  summary.emit('click');assert.equal(panel.hidden,true);assert.equal(select('#workspace-dialog').open,true);assert.equal(select('#music-search').focused,true);
  await context.window.XYMusic.toggle();assert.equal(summary.textContent,'Ⅱ 歌单');assert.equal(panel.children[0].children[1].textContent,'播放');
  dispatch('xy:music-state',{playing:true,title:'<img onerror=bad>',artist:'artist'});assert.equal(summary.textContent,'♫ <img onerror=bad> — artist');assert.equal(summary.children.length,0,'metadata is text, never markup');
  console.log('Music queue checks passed: local/remote switching, search append, playback state, controls and URL cleanup.');
})().catch(e=>{console.error(e);process.exitCode=1;});
