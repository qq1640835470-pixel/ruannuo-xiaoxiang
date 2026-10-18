'use strict';
const fs=require('node:fs'),assert=require('node:assert/strict');
const {chromium}=require('C:/Users/16408/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const base=process.argv[2];if(!base)throw Error('Use test_openrouter_ui.py (isolated data required)');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
  const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  const html=fs.readFileSync('web/index.html','utf8').replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi,'').replace('</body>','<script src="/app.js"></script><script src="/model-settings.js"></script></body>');
  await page.route('**/*',async route=>{
   const u=new URL(route.request().url());
   if(u.origin!==base)return route.abort();
   if(u.pathname==='/')return route.fulfill({contentType:'text/html',body:html});
   if(u.pathname==='/api/state'){
    const r=await page.request.get(base+'/api/state');return route.fulfill({json:await r.json()});
   }
   if(u.pathname==='/api/settings'||u.pathname==='/api/models')return route.continue();
   if(u.pathname.startsWith('/api/'))return route.fulfill({json:{}});
   return route.continue();
  });
  await page.context().request.get(base+'/');await page.goto(base+'/');await page.locator('#connection-status').filter({hasText:'已连接本机服务'}).waitFor();
  await page.locator('#settings-open').click();await page.locator('#model-select').selectOption('openrouter');
  await page.locator('#openrouter-settings').waitFor({state:'visible'});
  await page.locator('#catalog-refresh').click();await page.waitForFunction(()=>document.querySelector('#chat-model-id option[value="vendor/test-model:free"]'));
  assert.match(await page.locator('#chat-model-id').textContent(),/Friendly name.*vendor\/test-model:free/);
  await page.locator('#chat-model-id').selectOption('vendor/test-model:free');await Promise.all([page.waitForResponse(r=>r.url().endsWith('/api/settings') && r.request().method()==='PATCH').then(async r=>assert.equal(r.status(),200,await r.text())),page.locator('#save-settings').click()]);
  await page.locator('#settings-save-status').filter({hasText:'设置已保存'}).waitFor();
  await page.reload();await page.locator('#connection-status').filter({hasText:'已连接本机服务'}).waitFor();await page.locator('#settings-open').click();assert.equal(await page.locator('#model-select').inputValue(),'openrouter');
  await page.waitForFunction(()=>document.querySelector('#chat-model-id').value==='vendor/test-model:free');
  await page.locator('#openrouter-model-id').fill('Display Name');await page.locator('#openrouter-use-model').click();assert.match(await page.locator('#openrouter-model-status').textContent(),/格式无效/);
  await page.locator('#openrouter-model-id').fill('vendor/manual-model');await page.locator('#openrouter-use-model').click();
  await Promise.all([page.waitForResponse(r=>r.url().endsWith('/api/settings') && r.request().method()==='PATCH').then(async r=>assert.equal(r.status(),200,await r.text())),page.locator('#save-settings').click()]);await page.locator('#settings-save-status').filter({hasText:'设置已保存'}).waitFor();
  const settings=await (await page.request.get(base+'/api/state')).json();assert.equal(settings.settings.chat_models.openrouter,'vendor/manual-model');assert.equal(settings.settings.provider,'openrouter');
  assert.equal(await page.evaluate(()=>Object.keys(localStorage).some(k=>/key|credential/i.test(k))),false);
  await page.setViewportSize({width:390,height:844});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  assert.deepEqual(errors,[]);console.log('OpenRouter settings UI passed: discovery, labels/IDs, save/reload, manual ID validation, narrow screen; isolated DB and mock HTTP.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
