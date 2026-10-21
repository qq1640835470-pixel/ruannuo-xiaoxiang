'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require('C:/Users/16408/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const base=process.argv[2];if(!base)throw new Error('Use the isolated Python runner');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1280,height:900}}),errors=[],generated=[],saved=[];let loseGenerate=false,loseSave=false,failSave=false;
  page.on('dialog',d=>d.accept());page.on('pageerror',e=>errors.push(e.message));
  const html=fs.readFileSync(path.join(__dirname,'web/index.html'),'utf8').replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi,'').replace('</body>','<script src="/app.js"></script><script src="/learning-model-settings.js"></script><script src="/learning.js"></script><script src="/learning-checks.js"></script><script src="/learning-adjustments.js"></script></body>');
  await page.route('**/*',async route=>{
   const req=route.request(),u=new URL(req.url());
   if(u.pathname==='/')return route.fulfill({contentType:'text/html',body:html});
   if(u.pathname==='/api/state')return route.fulfill({json:{tasks:[],messages:[],settings:{provider:'openrouter',model:'fixture/model',api_generation_enabled:true}}});
   if(u.pathname==='/api/learning/adjustments/generate'){
    generated.push(req.postDataJSON());if(loseGenerate){loseGenerate=false;await route.fetch();return route.abort('failed');}
   }
   if(u.pathname==='/api/learning/adjustments/confirm'){
    saved.push(req.postDataJSON());if(failSave)return route.fulfill({status:500,json:{error:'临时模拟数据库失败'}});
    if(loseSave){loseSave=false;await route.fetch();return route.abort('failed');}
   }
   if(u.pathname.startsWith('/api/learning/')||u.pathname.startsWith('/api/tasks/'))return route.continue();
   if(u.pathname.startsWith('/api/'))return route.fulfill({json:{}});
   return route.continue();
  });
  await page.context().request.get(base+'/');await page.goto(base+'/');await page.locator('[data-page=learning]').click();
  const status=page.locator('#adjustment-status'),area=page.locator('#learning-adjustments');
  const getPlans=async()=>page.evaluate(async()=>await (await fetch('/api/learning/plans')).json());
  const before=await getPlans(),goalId=before.plans[0].goal.id,done=before.plans[0].tasks.find(t=>t.status==='done');
  async function open(){await page.locator('#learning-saved').click();if(!await page.locator('.learning-plan').evaluate(n=>n.open))await page.locator('.learning-plan>summary').click();await page.getByRole('button',{name:'调整学习计划',exact:true}).click();await status.filter({hasText:'请选择本次分析依据'}).waitFor();}
  async function preview(note='依据所选记录补充练习'){
   await area.getByLabel('选择当前目标、原计划安排与完成标记（调整必需）',{exact:true}).check();
   await area.getByLabel('另包含待开始、进行中、暂停及延期任务的详细状态',{exact:true}).check();
   const fields=page.locator('#adjustment-selection fieldset');await fields.nth(0).getByLabel(/25分钟/).check();await fields.nth(1).locator('input').first().check();await page.locator('#adjustment-note').fill(note);
   await page.getByRole('button',{name:'预览将发送的所选资料',exact:true}).click();await status.filter({hasText:'仅完成资料预览'}).waitFor();
   assert.match(await page.locator('#adjustment-preview').textContent(),/SELECTED_NOTE/);assert.doesNotMatch(await page.locator('#adjustment-preview').textContent(),/UNSELECTED_PRIVATE_NOTE/);
  }
  async function generate(){await page.locator('#adjustment-preview input[type=checkbox]').check();await page.getByRole('button',{name:'确认资料并生成调整草稿',exact:true}).click();await page.waitForFunction(()=>!document.querySelector('#learning-adjustments').hasAttribute('aria-busy'));}
  await open();assert.equal(await page.locator('#adjustment-selection input[type=checkbox]:checked').count(),0);
  await preview();assert.equal(generated.length,0);await generate();await status.filter({hasText:'已生成调整建议'}).waitFor();
  assert.match(await page.locator('#adjustment-comparison').textContent(),/保持不变（已完成，锁定）/);assert.match(await page.locator('#adjustment-comparison').textContent(),/建议取消/);assert.match(await page.locator('#adjustment-comparison').textContent(),/建议新增/);
  assert.deepEqual(await getPlans(),before);
  await page.getByRole('button',{name:'取消调整草稿',exact:true}).click();await status.filter({hasText:'调整草稿已取消'}).waitFor();assert.deepEqual(await getPlans(),before);
  await preview();loseGenerate=true;await generate();await page.waitForFunction(()=>!document.querySelector('#learning-adjustments').hasAttribute('aria-busy'));
  await page.reload();await page.getByRole('button',{name:'核对同一调整请求',exact:true}).waitFor();await page.waitForFunction(()=>!document.querySelector('#learning-adjustments').hasAttribute('aria-busy'));
  await page.getByRole('button',{name:'核对同一调整请求',exact:true}).click();await status.filter({hasText:'已生成调整建议'}).waitFor();assert.equal(generated[1].request_id,generated[2].request_id);
  const first=page.locator('#adjustment-draft [data-change="0"]');await first.getByLabel('建议分钟',{exact:true}).fill('30');assert.match(await page.locator('#adjustment-comparison').textContent(),/30分钟/);
  failSave=true;await page.getByRole('button',{name:'确认保存调整',exact:true}).click();await status.filter({hasText:'临时模拟数据库失败'}).waitFor();assert.deepEqual(await getPlans(),before);failSave=false;
  loseSave=true;await page.getByRole('button',{name:'确认保存调整',exact:true}).click();await page.waitForFunction(()=>!document.querySelector('#learning-adjustments').hasAttribute('aria-busy'));
  assert.equal(await first.getByLabel('建议分钟',{exact:true}).isDisabled(),true);
  await page.reload();await page.getByRole('button',{name:'核对同一调整请求',exact:true}).waitFor();await page.waitForFunction(()=>!document.querySelector('#learning-adjustments').hasAttribute('aria-busy'));
  await page.getByRole('button',{name:'核对同一调整请求',exact:true}).click();await status.filter({hasText:'已实际保存'}).waitFor();assert.equal(saved[1].request_id,saved[2].request_id);
  const after=await getPlans();assert.equal(after.plans.length,1);assert.equal(after.plans[0].goal.id,goalId);assert.deepEqual(after.plans[0].tasks.find(t=>t.id===done.id),done);assert.equal(after.plans[0].tasks.length,4);assert.equal(after.plans[0].tasks.filter(t=>t.status==='cancelled').length,1);
  assert.match(await page.locator('#adjustment-history').textContent(),/已实际保存/);
  for(const note of ['模拟无效','模拟预算不足']){
   await open();await preview(note);await generate();await status.filter({hasText:'未生成调整草稿'}).waitFor();assert.deepEqual(await getPlans(),after);
  }
  await open();await preview();await generate();await status.filter({hasText:'已生成调整建议'}).waitFor();
  await page.evaluate(async()=>{const plans=await (await fetch('/api/learning/plans')).json();const task=plans.plans[0].tasks.find(t=>!['done','cancelled'].includes(t.status));await fetch('/api/tasks/'+task.id,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:'active',request_id:crypto.randomUUID()})});});
  await page.getByRole('button',{name:'确认保存调整',exact:true}).click();await status.filter({hasText:'计划已变化'}).waitFor();
  await page.setViewportSize({width:390,height:844});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),true);
  await page.locator('#adjustment-comparison').scrollIntoViewIfNeeded();await page.screenshot({path:path.join(__dirname,'artifacts/learning-adjustments-fixture.png'),fullPage:true});
  await page.getByRole('button',{name:'取消调整草稿',exact:true}).click();await status.filter({hasText:'调整草稿已取消'}).waitFor();
  assert.deepEqual(errors,[]);console.log('Learning adjustment UI passed: explicit evidence, preview/consent, comparisons/edit, cancel, lost generate/save receipts, rollback message, reload/history, model/budget failures, conflict, 390px.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
