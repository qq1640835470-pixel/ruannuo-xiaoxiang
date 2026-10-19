'use strict';
const assert=require('node:assert/strict'),path=require('node:path');
const {chromium}=require('C:/Users/16408/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const base=process.argv[2];if(!base?.startsWith('http://127.0.0.1:'))throw new Error('Use isolated reminder fixture');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1280,height:900}}),errors=[],starts=[];let failStart=false,loseStart=false;
  await page.context().request.get(base+'/');assert.equal((await (await page.context().request.get(base+'/api/acceptance-034')).json()).isolated_synthetic_fixture,true);
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/api/learning/reminders/action',async route=>{
    const body=route.request().postDataJSON();if(body.action==='start'){
     starts.push(body);if(failStart){failStart=false;return route.fulfill({status:500,json:{error:'模拟写入失败'}});}
     if(loseStart){loseStart=false;await route.fetch();return route.abort('failed');}
    }return route.continue();
  });
  await page.goto(base+'/');await page.locator('[data-page=learning]').click();
  await page.locator('#learning-review').getByText(/未知 \/ 未填写/).waitFor();assert.equal(await page.locator('#learning-reminder').isVisible(),false);
  await page.locator('#learning-reminder-settings summary').click();assert.equal(await page.locator('#reminder-enabled').isChecked(),false);
  await page.locator('#reminder-enabled').check();await page.locator('#reminder-settings-form button[type=submit]').click();
  await page.locator('#learning-reminder li').filter({hasText:'合成电路分析'}).waitFor();
  const api=async(url,body,method='POST')=>{const r=await page.context().request.fetch(base+url,{method,data:body,headers:{'Content-Type':'application/json'}});assert.equal(r.ok(),true,await r.text());return r.json();};
  const get=async url=>(await page.context().request.get(base+url)).json();
  const wake=async()=>{const response=page.waitForResponse(r=>r.url().endsWith('/api/learning/reminders/check'));await page.evaluate(()=>window.dispatchEvent(new Event('learning-open')));await response;await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(resolve)));};
  await page.locator('#learning-reminder').getByRole('button',{name:'15分钟后提醒',exact:true}).click();await page.locator('#reminder-status').filter({hasText:'已保存15分钟'}).waitFor();
  await api('/api/reminder-fixture/time',{minutes:14});await wake();assert.equal(await page.locator('#learning-reminder').isVisible(),false);
  await api('/api/reminder-fixture/time',{minutes:1});await wake();await page.locator('#learning-reminder').waitFor({state:'visible'});
  failStart=true;await page.locator('#learning-reminder').getByRole('button',{name:'开始学习',exact:true}).first().click();await page.locator('#reminder-status').filter({hasText:'模拟写入失败'}).waitFor();
  let saved=(await get('/api/learning/plans')).plans[0],task=saved.tasks.find(t=>t.learning.kind==='review');assert.equal(task.status,'pending');
  loseStart=true;await page.locator('#learning-reminder').getByRole('button',{name:'开始学习',exact:true}).first().click();await page.locator('#learning-reminder').getByRole('button',{name:'核对同一提醒操作'}).waitFor();
  await page.reload();await page.locator('#learning-reminder').getByRole('button',{name:'核对同一提醒操作'}).click();await page.locator('#reminder-status').filter({hasText:'已核对任务状态：进行中'}).waitFor();
  assert.equal(starts[1].request_id,starts[2].request_id);assert.equal((await get('/api/tasks/'+task.id)).status,'active');
  await page.waitForFunction(id=>document.activeElement?.dataset.taskId===id,task.id);
  await page.locator('#learning-reminder-settings summary').click();await page.locator('#reminder-pause').click();await page.locator('#reminder-status').filter({hasText:'今天已暂停'}).waitFor();
  await page.reload();await page.locator('#learning-reminder-settings summary').click();await page.locator('#reminder-pause-indicator').filter({hasText:'今天已暂停'}).waitFor();assert.equal(await page.locator('#learning-reminder').isVisible(),false);
  await api('/api/reminder-fixture/time',{days:1});await wake();await page.locator('#learning-reminder').waitFor({state:'visible'});
  // The old button must not write after an external task edit.
  await api('/api/tasks/'+task.id,{title:'已在其他入口修改',request_id:'edit-outside'},'PATCH');
  await page.locator('#learning-reminder').getByRole('button',{name:'开始学习',exact:true}).first().click();await page.locator('#reminder-status').filter({hasText:'任务已修改'}).waitFor();
  assert.equal((await get('/api/tasks/'+task.id)).title,'已在其他入口修改');
  // Remaining valid task is still aggregated; closing it never changes its status.
  await page.locator('#learning-reminder').getByRole('button',{name:'跳过 / 关闭'}).click();await page.locator('#learning-reminder').waitFor({state:'hidden'});
  await page.reload();await page.locator('#learning-review').waitFor();assert.equal(await page.locator('#learning-reminder').isVisible(),false);
  saved=(await get('/api/learning/plans')).plans[0];assert.equal(saved.tasks.find(t=>t.learning.kind==='practice').status,'pending');
  await api('/api/reminder-fixture/time',{days:1});await wake();await page.locator('#learning-reminder li').first().waitFor();
  await page.locator('#learning-reminder').getByRole('button',{name:'查看计划',exact:true}).first().click();await page.locator('#learning-reminder').waitFor({state:'hidden'});await page.waitForFunction(()=>document.querySelector('#learning-page').hidden===false);
  await page.setViewportSize({width:390,height:844});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  await page.screenshot({path:path.join(__dirname,'artifacts/learning-reminders-fixture.png'),fullPage:true});assert.deepEqual(errors,[]);
  console.log('Stage05 full-page UI passed: opt-in, summary unknown, snooze simulated clock, write failure, lost receipt/reload/same-ID verify, actual task focus, persistent day pause, edited-task rejection, aggregated dismiss, reload dedup, 390px; no model calls.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
