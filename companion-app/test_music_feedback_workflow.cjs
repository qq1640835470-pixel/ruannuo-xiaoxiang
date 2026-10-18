'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require('C:/Users/16408/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const A='11111111-1111-4111-8111-111111111111',B='22222222-2222-4222-8222-222222222222';
(async()=>{
  const browser=await chromium.launch({channel:'msedge',headless:true});
  try{
    const page=await browser.newPage(),errors=[],calls=[],receipts=new Map();let blockAll=false,testFail=false;
    let target={thread_id:A,label:'fixture A',enabled:true,configured:true,cli_available:true};
    await page.addInitScript(()=>{
      if(!crypto.randomUUID)crypto.randomUUID=()=>Array.from(crypto.getRandomValues(new Uint32Array(4)),n=>n.toString(16).padStart(8,'0')).join('');
      Object.defineProperty(HTMLMediaElement.prototype,'paused',{get(){return this._paused!==false;}});
      HTMLMediaElement.prototype.play=async function(){this._paused=false;this.dispatchEvent(new Event('play'));};
      HTMLMediaElement.prototype.pause=function(){this._paused=true;this.dispatchEvent(new Event('pause'));};HTMLMediaElement.prototype.load=function(){};
    });
    page.on('pageerror',e=>errors.push(e.message));
    const root=path.join(__dirname,'web'),html=fs.readFileSync(path.join(root,'index.html'),'utf8').replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi,'').replace('</body>','<script src="/app.js"></script><script src="/feedback-target.js"></script><script src="/workspace-tools.js"></script></body>');
    const tracks=[1,2,3].map(id=>({id,name:'钢琴'+id,artists:''}));
    await page.route('**/*',route=>{
      const url=new URL(route.request().url()),body=route.request().postDataJSON(),method=route.request().method();
      if(url.pathname.startsWith('/api/'))calls.push({path:url.pathname,body,method});
      if(url.pathname==='/api/state')return route.fulfill({json:{tasks:[],messages:[],settings:{provider:'gemini',model:'fixture',api_generation_enabled:true}}});
      if(url.pathname==='/api/local/status')return route.fulfill({json:{preferences:{},permissions:[]}});
      if(url.pathname==='/api/feedback-target'){
        if(method==='PATCH')target={...target,...body};return route.fulfill({json:target});
      }
      if(url.pathname==='/api/feedback'||url.pathname==='/api/feedback/test'){
        const receipt={id:body.id,target_thread_id:body.target_thread_id,target_label:target.label,status:testFail?'unknown':'queued',detail:'fixture receipt '+body.target_thread_id};receipts.set(body.id,receipt);
        return route.fulfill(testFail?{status:503,json:{error:'fixture timeout'}}:{json:receipt});
      }
      if(url.pathname.startsWith('/api/feedback/'))return route.fulfill({json:receipts.get(url.pathname.split('/').at(-1))||{status:'unknown',detail:'unknown'}});
      if(url.pathname==='/api/chat')return route.fulfill({json:{reply:'已请求音乐队列。',music:{tracks,play_id:1},provider:'local',model:'本地工具路由'}});
      if(url.pathname==='/api/music/url')return route.fulfill({json:blockAll||url.searchParams.get('id')==='1'?{available:false}:{available:true,url:'http://workflow-fixture.local/audio.mp3'}});
      if(url.pathname.startsWith('/api/'))return route.fulfill({json:{}});
      if(url.pathname==='/')return route.fulfill({contentType:'text/html',body:html});
      const file=path.join(root,url.pathname.slice(1));if(fs.existsSync(file)&&fs.statSync(file).isFile())return route.fulfill({path:file});return route.fulfill({body:''});
    });
    await page.goto('http://workflow-fixture.local/');await page.waitForFunction(()=>window.XYMusic&&window.XYFeedbackTarget?.snapshot());
    await page.locator('#chat-input').fill('随便播放几首钢琴曲');await page.locator('#send-button').click();
    await page.waitForFunction(()=>document.querySelector('#music-status').textContent==='钢琴2');
    assert.equal(await page.locator('#music-list .music-track').count(),3);
    await page.evaluate(()=>document.querySelector('#music-audio').dispatchEvent(new Event('ended')));
    await page.waitForFunction(()=>document.querySelector('#music-status').textContent==='钢琴3');
    blockAll=true;const before=calls.filter(c=>c.path==='/api/music/url').length;await page.evaluate(()=>window.XYMusic.next());
    assert.equal(calls.filter(c=>c.path==='/api/music/url').length-before,3);assert.match(await page.locator('#music-status').textContent(),/没有取得可播放音源/);
    await page.locator('#settings-open').click();await page.evaluate(()=>document.querySelector('#feedback-target-settings').open=true);
    await page.locator('#feedback-thread').fill(B);await page.locator('#feedback-target-label').fill('fixture B');await page.locator('#feedback-target-save').click();
    await page.waitForFunction(()=>window.XYFeedbackTarget.snapshot().thread_id==='22222222-2222-4222-8222-222222222222');
    assert.equal(await page.locator('#feedback-target-save').isEnabled(),true);await page.locator('#settings-close').click();
    await page.locator('#feedback-button').click();assert.match(await page.locator('#feedback-target-display').textContent(),new RegExp(B));
    await page.locator('#feedback-content').fill('合成正式反馈');await page.locator('#feedback-send').click();
    await page.waitForFunction(()=>document.querySelector('#feedback-status').textContent.includes('fixture receipt'));
    assert.equal(calls.find(c=>c.path==='/api/feedback'&&c.method==='POST').body.target_thread_id,B);
    await page.locator('#feedback-close').click();await page.locator('#settings-open').click();await page.evaluate(()=>document.querySelector('#feedback-target-settings').open=true);
    await page.locator('#feedback-target-test').click();await page.waitForFunction(()=>document.querySelector('#feedback-test-status').textContent.includes('fixture receipt'));
    assert.equal(calls.filter(c=>c.path==='/api/feedback/test').length,1);
    testFail=true;await page.locator('#feedback-target-test').click();await page.waitForFunction(()=>document.querySelector('#feedback-target-test').textContent==='核对测试回执');
    const testCount=calls.filter(c=>c.path==='/api/feedback/test').length;
    await page.locator('#feedback-target-test').click();await page.waitForFunction(()=>!document.querySelector('#feedback-target-test').disabled);
    assert.equal(calls.filter(c=>c.path==='/api/feedback/test').length,testCount,'unknown test must not be resent');
    await page.reload();await page.waitForFunction(()=>window.XYFeedbackTarget?.snapshot());assert.equal(calls.filter(c=>c.path==='/api/feedback/test').length,testCount);
    assert.deepEqual(errors,[]);console.log('PASS styles/feedback UI: chat queue, restricted-track skip, bounded exhaustion, target save/display, formal/test target receipts, unknown no replay.');
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
