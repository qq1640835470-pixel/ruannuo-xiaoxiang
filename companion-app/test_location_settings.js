"use strict";
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('web/location-settings.js','utf8');
function create(initial={mode:'disabled',enabled:false},permission='granted'){
  let clock=Date.now(),geoCalls=0,current=initial;const nodes=new Map(),calls=[],listeners={};
  const node=()=>({textContent:'',value:'',disabled:false,addEventListener(name,fn){this[name]=fn;}});
  const select=s=>{if(!nodes.has(s))nodes.set(s,node());return nodes.get(s);};
  const section={querySelector:select,querySelectorAll:()=>['#location-enable','#location-manual','#location-refresh','#location-disable'].map(select)};
  const context=vm.createContext({Date:class extends Date{static now(){return clock;}},Math,JSON,Error,Promise,
    document:{hidden:false,querySelector:()=>section,addEventListener:(name,fn)=>{listeners[name]=fn;}},
    window:{dispatchEvent(){},addEventListener:(name,fn)=>{listeners[name]=fn;}},CustomEvent:class {},setInterval(fn){listeners.timer=fn;},
    navigator:{permissions:{query:async()=>({state:permission})},geolocation:{getCurrentPosition(success){geoCalls++;success({coords:{latitude:51.507451,longitude:-.127758}});}}},
    api:async(path,options)=>{const body=options&&JSON.parse(options.body);calls.push({path,body});if(path.endsWith('/status'))return current;
      if(path.endsWith('/update')){current={...body,enabled:body.mode!=='disabled',label:'Test city',updated_at:new Date(clock).toISOString()};return current;}
      return {status:'ok',location:'Test city',current:{summary:'cloudy',temperature_2m:15},days:[],timezone:'Europe/London',queried_at:new Date(clock).toISOString()};}
  });vm.runInContext(source,context);
  return {nodes,calls,listeners,geo:()=>geoCalls,advance:()=>{clock+=1801000;},click:id=>select(id).click(),flush:()=>new Promise(resolve=>setImmediate(resolve))};
}
(async()=>{
  const fresh=create();await fresh.flush();assert.equal(fresh.geo(),0);assert.deepEqual(fresh.calls.map(x=>x.path),['/api/location/status'],'startup cannot request GPS or public weather by default');
  fresh.click('#location-enable');await fresh.flush();assert.equal(fresh.geo(),1);const posted=fresh.calls.find(x=>x.body?.mode==='geolocation');assert.equal(posted.body.latitude,51.51);assert.equal(posted.body.longitude,-.13);
  fresh.advance();await fresh.listeners.focus();await fresh.flush();assert.equal(fresh.geo(),2,'focus refreshes expired authorized device location');
  fresh.nodes.get('#location-city').value='London';fresh.click('#location-manual');await fresh.flush();fresh.advance();await fresh.listeners.timer();assert.equal(fresh.geo(),2,'manual city disables automatic device updates');
  const stale={mode:'geolocation',enabled:true,label:'Saved device',auto_refresh:true,updated_at:'2020-01-01T00:00:00Z'};
  const prompting=create(stale,'prompt');await prompting.flush();assert.equal(prompting.geo(),0,'automatic refresh cannot trigger a new permission prompt');
  const denied=create(stale,'denied');await denied.flush();assert.equal(denied.geo(),0);
  console.log('Location UI checks passed: no default GPS, coarse request, authorized stale focus refresh, manual precedence, no automatic permission prompts.');
})().catch(e=>{console.error(e);process.exitCode=1;});
