'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require('C:/Users/16408/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{
  const browser=await chromium.launch({channel:'msedge',headless:true});
  try{
    const page=await browser.newPage(),errors=[],calls=[];let slow=false,release;
    page.on('pageerror',e=>errors.push(e.message));
    const html=fs.readFileSync(path.join(__dirname,'web/index.html'),'utf8').replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi,'');
    await page.addInitScript(()=>{
      window.audioPlays=0;window.audioPauses=0;
      window.Audio=class{async play(){window.audioPlays++;}pause(){window.audioPauses++;}};
      window.api=async (url,options)=>{const r=await fetch(url,options),d=await r.json();if(!r.ok)throw Error(d.error);return d;};
    });
    await page.route('**/*',async route=>{
      const url=new URL(route.request().url());
      if(url.pathname==='/api/speech'){
        const body=route.request().postDataJSON();calls.push(body);
        if(slow)await new Promise(resolve=>release=resolve);
        return route.fulfill({json:{url:'/fixture.mp3',language:body.language,translated_text:body.language==='ja'?'こんにちは':'Hello'}}).catch(()=>{});
      }
      if(url.pathname.startsWith('/api/'))return route.fulfill({json:{free_valid:true,free_until:'2026-11-30',today:[]}});
      if(url.pathname==='/activity-speech-settings.js')return route.fulfill({path:path.join(__dirname,'web/activity-speech-settings.js')});
      if(url.pathname==='/'||url.pathname==='/index.html')return route.fulfill({contentType:'text/html',body:html.replace('</body>','<script src="/activity-speech-settings.js"></script></body>')});
      const file=path.join(__dirname,'web',url.pathname.slice(1));
      if(fs.existsSync(file)&&fs.statSync(file).isFile())return route.fulfill({path:file});
      return route.fulfill({body:''});
    });
    await page.goto('http://speech-fixture.local/');
    await page.evaluate(()=>{document.querySelector('#settings-drawer').hidden=false;document.querySelector('#activity-settings').open=true;});
    await page.locator('#speech-language').selectOption('ja');
    await page.evaluate(()=>window.XYSpeech.speak('**你好**'));
    assert.equal(calls.at(-1).language,'ja');assert.equal(calls.at(-1).text,'你好');
    assert.equal(await page.locator('#speech-text').textContent(),'こんにちは');assert.equal(await page.evaluate(()=>audioPlays),1);
    await page.locator('#speech-language').selectOption('en');assert.equal(await page.evaluate(()=>audioPauses),1);
    await page.reload();
    assert.equal(await page.locator('#speech-language').inputValue(),'en');
    await page.evaluate(()=>window.XYSpeech.speak('你好'));
    assert.equal(calls.at(-1).language,'en');assert.equal(await page.locator('#speech-text').textContent(),'Hello');
    await page.evaluate(()=>window.XYSpeech.stop());slow=true;
    await page.evaluate(()=>{window.pendingSpeech=window.XYSpeech.speak('稍后返回');});
    await page.waitForFunction(()=>document.querySelector('#speech-progress').textContent.includes('正在本机翻译'));
    for(let attempt=0;attempt<100&&!release;attempt++)await new Promise(resolve=>setTimeout(resolve,10));
    assert.equal(typeof release,'function');
    const played=await page.evaluate(()=>audioPlays);await page.evaluate(()=>window.XYSpeech.stop());release();
    await page.evaluate(()=>window.pendingSpeech);
    assert.equal(await page.evaluate(()=>audioPlays),played,'stopping translation prevents stale audio playback');
    assert.deepEqual(errors,[]);
    console.log('PASS multilingual speech UI: selection/persistence, translated preview, language requests, audio and cancellation.');
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
