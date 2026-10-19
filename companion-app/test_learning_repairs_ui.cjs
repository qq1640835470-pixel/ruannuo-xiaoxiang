'use strict';
const assert=require('node:assert/strict');
const {chromium}=require('C:/Users/16408/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const base=process.argv[2];if(!base?.startsWith('http://127.0.0.1:'))throw Error('Isolated fixture only');
(async()=>{const browser=await chromium.launch({channel:'msedge',headless:true});try{
 const page=await browser.newPage(),errors=[];let writes=0;page.on('dialog',d=>d.accept());page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/api/tasks/*',route=>{if(route.request().method()==='PATCH')writes++;return route.continue();});
 await page.context().request.get(base+'/');await page.goto(base+'/#learning');
 const task=page.locator('#learning-plans .learning-task').first();await task.getByRole('button',{name:'开始',exact:true}).click();
 await page.locator('#learning-current').filter({hasText:'复习节点法'}).waitFor();assert.equal(await page.locator('.learning-task.is-active').count(),1);assert.equal(writes,1);
 await task.getByRole('button',{name:'开始',exact:true}).click();await page.locator('#learning-status').filter({hasText:'未重复写入'}).waitFor();assert.equal(writes,1);
 await page.locator('#learning-current').getByRole('button',{name:'暂停学习',exact:true}).click();await page.locator('#learning-current').waitFor({state:'hidden'});
 const get=async url=>(await page.context().request.get(base+url)).json();let plan=(await get('/api/learning/plans')).plans[0];assert.equal(plan.tasks.find(t=>t.learning.kind==='review').status,'paused');assert.equal(plan.tasks.reduce((n,t)=>n+t.progress.length,0),0);
 async function answer(){
  const cards=page.locator('#check-current fieldset');await cards.first().waitFor();
  for(let i=0;i<await cards.count();i++){const card=cards.nth(i);if(await card.locator('input[type=radio]').count())await card.locator('input[type=radio]').first().check();else await card.locator('textarea').fill('参考要点');}
  await page.locator('#check-current form button[type=submit]').click();await page.locator('#check-status').filter({hasText:'结果已保存'}).waitFor();
 }
 await task.getByRole('button',{name:'检验学习成果',exact:true}).click();await page.locator('#check-generate button').click();await answer();
 for(const topic of ['零状态响应','一阶RC电路','电容充放电']){
  await page.locator('#check-topic-mode').click();await page.locator('#check-topic').fill(topic);await page.locator('#check-generate button').click();
  await page.locator('#check-status').filter({hasText:'尚未提交答案'}).waitFor();await answer();
 }
 const history=(await get('/api/learning/checks')).checks;assert.equal(history.length,4);assert.equal(history.filter(c=>c.task_id==='').length,3);assert.ok(history.every(c=>c.status==='submitted'));
 assert.deepEqual(errors,[]);console.log('P0 production-page passed: start/readback/highlight/current session/pause/no duplicate write/no inferred minutes, task and 3 topics, submit/grade/history.');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
