'use strict';
// Uses the full production page/scripts and real isolated handlers/adapters.
const assert=require('node:assert/strict'),path=require('node:path');
const {chromium}=require('C:/Users/16408/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const base=process.argv[2];if(!base?.startsWith('http://127.0.0.1:'))throw new Error('Use an isolated Fixture server');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1280,height:900}}),errors=[],writes=[];let losePlan=true,loseAdjustment=true;
  await page.context().request.get(base+'/');const marker=await page.context().request.get(base+'/api/acceptance-034');assert.equal(marker.ok(),true);assert.equal((await marker.json()).isolated_synthetic_fixture,true);
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/api/learning/confirm',async route=>{writes.push({kind:'plan',body:route.request().postDataJSON()});if(losePlan){losePlan=false;await route.fetch();return route.abort('failed');}return route.continue();});
  await page.route('**/api/learning/adjustments/confirm',async route=>{writes.push({kind:'adjust',body:route.request().postDataJSON()});if(loseAdjustment){loseAdjustment=false;await route.fetch();return route.abort('failed');}return route.continue();});
  await page.goto(base+'/');await page.waitForFunction(()=>document.querySelector('#model-select')?.value==='openrouter');
  await page.locator('#settings-open').click();await page.locator('#chat-model-id').waitFor({state:'visible'});assert.equal(await page.locator('#chat-model-id').inputValue(),'fixture/learning-034');await page.locator('#settings-close').click();
  await page.locator('[data-page=learning]').click();await page.locator('#learning-request').fill('合成节点法，两天，每天120分钟');await page.locator('#learning-input button').click();await page.locator('#learning-status').filter({hasText:'需求分析完成'}).waitFor();
  await page.locator('#learning-requirements button').click();await page.locator('#learning-status').filter({hasText:'草稿已生成'}).waitFor();
  await page.getByRole('button',{name:'确认保存',exact:true}).click();await page.locator('#learning-status').filter({hasText:'回执不明'}).waitFor();await page.reload();
  await page.getByRole('button',{name:'确认保存',exact:true}).waitFor();await page.getByRole('button',{name:'确认保存',exact:true}).click();await page.locator('#learning-status').filter({hasText:'计划已保存'}).waitFor();
  assert.equal(writes[0].body.request_id,writes[1].body.request_id);
  const get=path=>page.evaluate(async path=>await (await fetch(path)).json(),path);
  let saved=(await get('/api/learning/plans')).plans[0];const goalId=saved.goal.id,review=saved.tasks.find(t=>t.learning.kind==='review');
  let card=page.locator('.learning-task').filter({has:page.locator('h4',{hasText:'复习节点法'})}).first();
  await card.locator('.learning-progress input').fill('25');await card.locator('.learning-progress textarea').fill('节点电压定义练习。'.repeat(180)+'SELECTED_END');await card.getByRole('button',{name:'记录本次学习',exact:true}).click();await page.locator('#learning-status').filter({hasText:'学习记录已保存'}).waitFor();
  await page.request.post(base+`/api/tasks/${review.id}/progress`,{data:{request_id:'ui-unselected-note',minutes:9,note:'UNSELECTED_NOTE'}});
  await card.getByRole('button',{name:'完成',exact:true}).click();await page.locator('#learning-task-feedback').filter({hasText:'任务已完成'}).waitFor();
  if(!await page.locator('.learning-plan > details').nth(2).evaluate(node=>node.open))await page.locator('.learning-plan > details').nth(2).locator('summary').first().click();
  card=page.locator('.learning-task').filter({has:page.locator('h4',{hasText:'复习节点法'})}).first();await card.getByRole('button',{name:'检验学习成果',exact:true}).click();await page.locator('#check-generate button').click();await page.locator('#check-current fieldset').first().waitFor();
  await page.locator('#check-status').filter({hasText:'尚未提交答案'}).waitFor();
  await page.locator('#check-current [data-question="1"] input').first().check();await page.locator('#check-current [data-question="2"] input').last().check();await page.locator('#check-current [data-question="3"] textarea').fill('先选参考节点再列式');await page.locator('#check-evaluate').check();
  await page.getByRole('button',{name:'提交答案并保存结果',exact:true}).click();await page.locator('#check-status').filter({hasText:'结果已保存'}).waitFor();await page.locator('#check-current').getByText(/客观题：1 \/ 2/).waitFor();
  const check=(await get('/api/learning/checks')).checks[0];assert.equal(check.task_id,review.id);assert.equal(check.goal_id,goalId);
  const before=(await get('/api/learning/plans')).plans[0].tasks.find(t=>t.id===review.id);
  await page.getByRole('button',{name:'调整学习计划',exact:true}).click();await page.locator('#adjustment-status').filter({hasText:'请选择本次分析依据'}).waitFor();
  const area=page.locator('#adjustment-selection');await area.getByLabel('选择当前目标、原计划安排与完成标记（调整必需）',{exact:true}).check();await area.getByLabel('另包含待开始、进行中、暂停及延期任务的详细状态',{exact:true}).check();
  await area.locator('fieldset').nth(0).getByLabel(/25分钟/).check();await area.locator('fieldset').nth(1).locator('input').first().check();await page.locator('#adjustment-note').fill('只按所选记录微调');
  await page.getByRole('button',{name:'预览将发送的所选资料',exact:true}).click();await page.locator('#adjustment-status').filter({hasText:'仅完成资料预览'}).waitFor();const preview=await page.locator('#adjustment-preview').textContent();assert.match(preview,/SELECTED_END/);assert.doesNotMatch(preview,/UNSELECTED_NOTE/);
  await page.locator('#adjustment-preview input[type=checkbox]').check();await page.getByRole('button',{name:'确认资料并生成调整草稿',exact:true}).click();await page.locator('#adjustment-status').filter({hasText:'已生成调整建议'}).waitFor();assert.match(await page.locator('#adjustment-comparison').textContent(),/已完成，锁定/);
  await page.getByRole('button',{name:'确认保存调整',exact:true}).click();await page.waitForFunction(()=>!document.querySelector('#learning-adjustments').hasAttribute('aria-busy'));await page.reload();
  await page.getByRole('button',{name:'核对同一调整请求',exact:true}).waitFor();await page.waitForFunction(()=>!document.querySelector('#learning-adjustments').hasAttribute('aria-busy'));await page.getByRole('button',{name:'核对同一调整请求',exact:true}).click();await page.locator('#adjustment-status').filter({hasText:'已实际保存'}).waitFor();
  const adjustmentWrites=writes.filter(w=>w.kind==='adjust');assert.equal(adjustmentWrites[0].body.request_id,adjustmentWrites[1].body.request_id);
  const plans=(await get('/api/learning/plans')).plans;assert.equal(plans.length,1);assert.equal(plans[0].goal.id,goalId);assert.deepEqual(plans[0].tasks.find(t=>t.id===review.id),before);assert.deepEqual((await get('/api/learning/checks')).checks[0],check);
  await page.reload();await page.locator('.learning-plan').waitFor();await page.getByRole('button',{name:'调整学习计划',exact:true}).click();await page.locator('#adjustment-history').getByText(/已实际保存/).waitFor();
  await page.screenshot({path:path.join(__dirname,'artifacts/learning-system-034-full.png'),fullPage:true});assert.deepEqual(errors,[]);
  console.log('Full production-page integrated UI passed: settings, plan, lost receipts, progress/completion, quiz/feedback, selected-evidence adjustment, reload/history, no script errors.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
