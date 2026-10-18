'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),assert=require('node:assert/strict');
const {chromium}=require('C:/Users/16408/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{
  const browser=await chromium.launch({channel:'msedge',headless:true});
  try{
    const page=await browser.newPage({viewport:{width:1280,height:800}}),errors=[],sent=[],uploaded=new Map();let messages=[],fail=false;
    page.on('pageerror',e=>errors.push(e.message));
    await page.addInitScript(()=>{if(!crypto.randomUUID)crypto.randomUUID=()=>Array.from(crypto.getRandomValues(new Uint32Array(4)),n=>n.toString(16).padStart(8,'0')).join('');});
    const root=path.join(__dirname,'web'),html=fs.readFileSync(path.join(root,'index.html'),'utf8').replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi,'').replace('</body>','<script src="/app.js"></script><script src="/chat-attachments.js"></script><script src="/chat-history.js"></script></body>');
    const png=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jLMsAAAAASUVORK5CYII=','base64');
    await page.route('**/*',route=>{
      const url=new URL(route.request().url()),body=route.request().postDataJSON();
      if(url.pathname==='/api/state')return route.fulfill({json:{tasks:[],messages,settings:{provider:'gemini',model:'fixture',api_generation_enabled:true},connectors:[]}});
      if(url.pathname==='/api/messages')return route.fulfill({json:{messages,has_more:false}});
      if(url.pathname==='/api/chat/attachments'){
        if(body.name.endsWith('.pdf'))return route.fulfill({status:400,json:{error:'暂不支持PDF'}});
        const raw=Buffer.from(body.base64,'base64'),id=crypto.createHash('sha256').update(body.name).update(raw).digest('hex');
        const file={id,name:body.name,size:raw.length,kind:body.name.endsWith('.png')?'image':'text'};uploaded.set(id,file);return route.fulfill({json:file});
      }
      if(url.pathname.startsWith('/api/chat/attachments/'))return route.fulfill({contentType:'image/png',body:png});
      if(url.pathname==='/api/chat/receipt')return route.fulfill({json:{status:'not_received'}});
      if(url.pathname==='/api/chat'){
        sent.push(body);if(fail)return route.fulfill({status:503,json:{error:'fixture offline'}});
        const attachments=(body.attachment_ids||[]).map(id=>uploaded.get(id));messages.push({role:'user',content:body.text,attachments},{role:'assistant',content:'已根据附件回答。',provider:'gemini',model:'fixture'});
        return route.fulfill({json:{reply:'已根据附件回答。',provider:'gemini',model:'fixture',request_id:body.client_request_id,actions:[]}});
      }
      if(url.pathname.startsWith('/api/'))return route.fulfill({json:{}});
      if(url.pathname==='/')return route.fulfill({contentType:'text/html',body:html});
      const file=path.join(root,url.pathname.slice(1));if(fs.existsSync(file)&&fs.statSync(file).isFile())return route.fulfill({path:file});
      return route.fulfill({status:404,body:''});
    });
    await page.goto('http://attachments-fixture.local/');await page.waitForFunction(()=>window.XYAttachments);
    await page.locator('#chat-files').setInputFiles({name:'资料.txt',mimeType:'text/plain',buffer:Buffer.from('合成资料42')});
    await page.waitForFunction(()=>window.XYAttachments.snapshot().length===1);
    assert.match(await page.locator('.chat-attachment-tip').first().textContent(),/当前对话模型/);
    await page.getByRole('button',{name:'移除 资料.txt',exact:true}).click();assert.equal(sent.length,0);
    await page.locator('#chat-files').setInputFiles([{name:'资料.txt',mimeType:'text/plain',buffer:Buffer.from('合成资料42')},{name:'图片.png',mimeType:'image/png',buffer:png}]);
    await page.waitForFunction(()=>window.XYAttachments.snapshot().length===2);
    assert.equal(await page.locator('#chat-attachment-list img').count(),1);
    await page.locator('#send-button').click();await page.waitForFunction(()=>document.querySelector('#chat-attachment-list').childElementCount===0);
    assert.equal(sent[0].attachment_ids.length,2);assert.equal(sent[0].text,'请帮我看看这些附件。');assert.equal(await page.locator('.message.user .chat-attachment-link').count(),2);
    await page.reload();await page.waitForFunction(()=>document.querySelectorAll('.message.user .chat-attachment-link').length===2);
    await page.locator('#history-open').click();await page.waitForFunction(()=>document.querySelectorAll('#history-results .chat-attachment-link').length===2);await page.locator('#history-close').click();
    await page.locator('#chat-files').setInputFiles({name:'scan.pdf',mimeType:'application/pdf',buffer:Buffer.from('%PDF')});
    await page.waitForFunction(()=>document.querySelector('#chat-attachment-status').textContent.includes('暂不支持PDF'));
    await page.locator('#chat-files').setInputFiles({name:'重试.md',mimeType:'text/plain',buffer:Buffer.from('retry fixture')});await page.waitForFunction(()=>window.XYAttachments.snapshot().length===1);
    fail=true;await page.locator('#chat-input').fill('总结这个文件');await page.locator('#send-button').click();
    await page.waitForFunction(()=>localStorage.getItem('xy.chat.pending'));
    const pending=await page.evaluate(()=>JSON.parse(localStorage.getItem('xy.chat.pending')));assert.equal(pending.attachments.length,1);
    await page.reload();await page.waitForFunction(()=>window.XYAttachments.snapshot().length===1);
    fail=false;await page.locator('#chat-recover').click();await page.waitForFunction(()=>!localStorage.getItem('xy.chat.pending'));
    assert.equal(sent.at(-1).client_request_id,pending.id);assert.deepEqual(sent.at(-1).attachment_ids,pending.attachments.map(f=>f.id));
    assert.equal(await page.locator('#chat-attachment-list').textContent(),'');
    await page.setViewportSize({width:390,height:844});
    await page.locator('#chat-files').setInputFiles({name:'长文件名用于检查窄屏布局.txt',mimeType:'text/plain',buffer:Buffer.from('narrow screen fixture')});await page.waitForFunction(()=>window.XYAttachments.snapshot().length===1);
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    fs.mkdirSync(path.join(__dirname,'artifacts'),{recursive:true});await page.screenshot({path:path.join(__dirname,'artifacts/chat-attachments-390.png')});
    assert.deepEqual(errors,[]);
    console.log('PASS chat attachments UI: select/remove/preview, file-only sending, stored history, unsupported types, pending reload/recovery and narrow layout.');
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
