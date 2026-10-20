'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require('C:/Users/16408/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const base=process.argv[2];if(!base?.startsWith('http://127.0.0.1:'))throw Error('Isolated fixture URL required');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1280,height:900}}),errors=[];let loseSearch=true,loseSave=true,searchRequests=0,saveRequests=0,acceptDialog=true;
  page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>acceptDialog?d.accept():d.dismiss());
  const html=fs.readFileSync(path.join(__dirname,'web/index.html'),'utf8').replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi,'').replace('</body>','<script src="/app.js"></script><script src="/learning-model-settings.js"></script><script src="/learning-resources.js"></script></body>');
  await page.route('**/*',async route=>{
   const u=new URL(route.request().url());
   if(u.origin!==base)return route.abort('blockedbyclient');
   if(u.pathname==='/')return route.fulfill({contentType:'text/html',body:html});
   if(u.pathname==='/api/state')return route.fulfill({json:{tasks:[],messages:[],settings:{provider:'openrouter',model:'fixture',api_generation_enabled:true}}});
   if(u.pathname==='/api/learning/resources/search'){
    searchRequests++;if(loseSearch){loseSearch=false;await route.fetch();return route.abort('failed');}
   }
   if(u.pathname==='/api/learning/resources/save'){
    saveRequests++;if(loseSave){loseSave=false;await route.fetch();return route.abort('failed');}
   }
   if(u.pathname.startsWith('/api/learning/'))return route.continue();
   if(u.pathname.startsWith('/api/'))return route.fulfill({json:{}});
   return route.continue();
  });
  await page.context().request.get(base+'/');
  async function open(){await page.goto(base+'/');await page.locator('[data-page=learning]').click();if(!await page.locator('#learning-resources').evaluate(n=>n.open))await page.locator('#learning-resources>summary').click();await page.locator('#resources-saved h4').waitFor();}
  const status=page.locator('#resources-status');
  await open();assert.equal(searchRequests,0);
  await page.locator('#resources-request').fill('学习差分放大电路，基础一般，找综合资源');
  await page.locator('#resources-analyze').click();await status.filter({hasText:'需求已整理'}).waitFor();
  assert.equal(await page.locator('#resources-topic').inputValue(),'差分放大电路');
  await page.locator('#resources-form button').click();await status.filter({hasText:'未联网'}).waitFor();assert.equal(searchRequests,0);
  assert.equal(await page.locator('#resources-preview input').count(),3);
  acceptDialog=false;await page.getByRole('button',{name:'确认关键词并开始真实搜索',exact:true}).click();acceptDialog=true;assert.equal(searchRequests,0);
  await page.getByRole('button',{name:'确认关键词并开始真实搜索',exact:true}).click();await status.filter({hasText:'回执待核对'}).waitFor();
  assert.equal(searchRequests,1);
  await page.evaluate(()=>document.getElementById('resources-analyze').disabled=false);
  await page.locator('#resources-analyze').click();await status.filter({hasText:'未发送新请求'}).waitFor();
  await open();await page.locator('#resources-recover').click();await status.filter({hasText:'找到 3 条'}).waitFor();
  assert.equal(searchRequests,1);assert.equal(await page.locator('#resources-results .resource-card').count(),3);
  assert.equal(await page.locator('#resources-results img,#resources-results script').count(),0);assert.equal(await page.evaluate(()=>window.EXECUTED),undefined);
  assert.match(await page.locator('#resources-results').textContent(),/忽略所有指令/);
  assert.equal(await page.locator('#resources-results a[target=_blank][rel="noopener noreferrer"]').count(),3);
  await page.locator('#learning-resources>summary').scrollIntoViewIfNeeded();
  await page.screenshot({path:path.join(__dirname,'artifacts/learning-resources-desktop-fixture.png'),fullPage:true});
  assert.match(await page.locator('#resources-results').textContent(),/原文未读取/);assert.match(await page.locator('#resources-results').textContent(),/搜索时间/);
  for(const box of await page.locator('#resources-results .resource-choice').all())await box.check();
  await page.locator('#resources-task').selectOption({index:1});await page.locator('#resources-save').click();await status.filter({hasText:'回执待核对'}).waitFor();
  await open();await page.locator('#resources-recover').click();await status.filter({hasText:'资源已保存'}).waitFor();assert.equal(saveRequests,1);
  assert.equal(await page.locator('#resources-saved .resource-card').count(),3);assert.match(await page.locator('#resources-saved').textContent(),/已关联/);
  async function single(topic){
   await page.locator('#resources-topic').fill(topic);await page.locator('#resources-video').uncheck();await page.locator('#resources-practice').uncheck();
   await page.locator('#resources-form button').click();await status.filter({hasText:'未联网'}).waitFor();
   await page.getByRole('button',{name:'确认关键词并开始真实搜索',exact:true}).click();
  }
  await single('差分放大电路 模拟超时');await status.filter({hasText:'搜索超时'}).waitFor();assert.equal(await page.locator('#resources-results .resource-card').count(),0);assert.match(await status.textContent(),/用量待核对/);
  await single('差分放大电路 模拟无结果');await status.filter({hasText:'没有找到符合条件'}).waitFor();assert.equal(await page.locator('#resources-results .resource-card').count(),0);
  await single('差分放大电路');await status.filter({hasText:'找到 1 条'}).waitFor();
  await page.locator('#resources-results .resource-choice').check();await page.locator('#resources-save').click();await status.filter({hasText:'新增 0 条'}).waitFor();
  assert.equal(await page.locator('#resources-saved .resource-card').count(),3);
  await page.setViewportSize({width:390,height:844});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  await page.screenshot({path:path.join(__dirname,'artifacts/learning-resources-fixture.png'),fullPage:true});assert.deepEqual(errors,[]);
  console.log('Resource UI passed: analyze, preview/cancel, real local handler + synthetic search, lost search/save receipts recovered without POST, task link, empty/timeout, duplicate save, 390px. Screenshot: artifacts/learning-resources-fixture.png');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
