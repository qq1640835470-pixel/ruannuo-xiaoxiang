"use strict";
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('web/app.js','utf8');
const nodes=new Map(),events=[],calls=[];
const make=(tag='',className='',text='')=>({tag,className,textContent:text,children:[],disabled:false,value:'',append(...x){this.children.push(...x);},addEventListener(name,fn){this[name]=fn;},focus(){},setAttribute(){}});
const state={messages:[],busy:false};let response={reply:'failed',error:'provider_failed',request_id:'abc123',execution:[{status:'failed'}]},fail=false;
const context=vm.createContext({state,Date,JSON,console,AbortController,setTimeout,clearTimeout,crypto:{randomUUID:()=>'01234567-89ab-cdef-0123-456789abcdef'},
  $:selector=>{if(!nodes.has(selector))nodes.set(selector,make());return nodes.get(selector);},el:make,
  window:{dispatchEvent:event=>events.push(event)},CustomEvent:class {constructor(type,options){this.type=type;this.detail=options.detail;}},
  renderMessages(){},error(){},refreshTasks:async()=>{},
  api:async(path,options)=>{calls.push({path,body:JSON.parse(options.body)});if(fail)throw Error('offline');return response;}
});
vm.runInContext(source.slice(source.indexOf('function retryState'),source.indexOf('function executionBlock')),context);
vm.runInContext(source.slice(source.indexOf('async function sendMessage'),source.indexOf('async function refreshTasks')),context);
const run=s=>vm.runInContext(s,context);
(async()=>{
  assert.equal(run(`chatRetry({content:'done'},'hello')`),null);
  const failed=run(`chatRetry({error:'failed',execution:[{status:'failed'}]},'hello')`);
  assert.equal(calls.length,0,'rendering a failed message cannot submit it');
  failed.children[0].click();await new Promise(resolve=>setImmediate(resolve));
  assert.equal(calls.length,1);assert.deepEqual(calls[0],{path:'/api/chat',body:{text:'hello',client_request_id:'0123456789abcdef0123456789abcdef'}});
  assert.equal(state.messages.at(-1).error,'provider_failed');assert.equal(state.messages.at(-1).request_id,'abc123');assert.equal(nodes.get('#chat-input').value,'hello','structured failure retains draft');
  state.busy=true;failed.children[0].click();assert.equal(calls.length,1,'repeat clicks while busy cannot duplicate submission');state.busy=false;
  for(const status of ['completed','requested','unknown','sending']){
    const box=run(`chatRetry({error:'failed',actions:[{status:'${status}'}]},'open app')`);
    assert.equal(box.children.some(x=>x.tag==='button'),false,'already executed or uncertain actions have no automatic retry');
  }
  fail=true;nodes.get('#chat-input').value='open app';await run('sendMessage()');assert.equal(nodes.get('#chat-input').value,'open app');assert.equal(nodes.get('#chat-input').disabled,false);assert.equal(state.busy,false);
  assert.equal(calls.length,2,'network failure is not retried automatically');
  console.log('Chat retry checks passed: explicit text resend, safe action guard, request metadata, busy deduplication, failed draft recovery, no automatic replay.');
})().catch(e=>{console.error(e);process.exitCode=1;});
