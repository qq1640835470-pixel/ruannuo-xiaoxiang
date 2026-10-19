'use strict';
const assert=require('node:assert/strict');
const {chromium}=require('C:/Users/16408/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const [base,id,mode,baselinePath]=process.argv.slice(2);
if(!base?.startsWith('http://127.0.0.1:'))throw Error('Isolated fixture only');
(async()=>{const browser=await chromium.launch({channel:'msedge',headless:true});try{
 const page=await browser.newPage({viewport:{width:1100,height:720}}),errors=[],patches=[];
 page.on('pageerror',e=>errors.push(e.message));
 if(mode==='--baseline')await page.route('**/learning.js*',route=>route.fulfill({path:baselinePath,contentType:'text/javascript'}));
 let hold=null,drop=false,badReceipt=false,badRead=false,readFailure=false;
 await page.route('**/api/tasks/'+id,async route=>{
  if(route.request().method()==='PATCH'){
   patches.push(route.request().postDataJSON());
   if(hold)await hold;
   if(drop){drop=false;await route.fetch();return route.abort('failed');}
   if(badReceipt){badReceipt=false;return route.fulfill({json:{ok:true,task:{id,status:'active'}}});}
   const r=await route.fetch();
   if(badRead){badRead=false;readFailure=true;}
   return route.fulfill({response:r});
  }
  if(readFailure){readFailure=false;return route.fulfill({status:503,json:{error:'合成回读失败'}});}
  return route.continue();
 });
 const get=async path=>(await page.context().request.get(base+path)).json();
 await page.goto(base+'/#learning');
 const card=page.locator(`#learning-plans [data-task-id="${id}"]`),feedback=page.locator('#learning-task-feedback');
 const click=label=>card.getByRole('button',{name:label,exact:true}).click();
 const settle=()=>page.waitForFunction(()=>!document.querySelector('#learning-page').hasAttribute('aria-busy'));
 await click('开始');await settle();assert.equal((await get('/api/tasks/'+id)).status,'active');
 await click('开始');await settle();assert.equal(patches.length,1);
 if(mode==='--failure'){
  await click('暂停');await settle();assert.match(await feedback.innerText(),/数据库写入失败/);
  assert.doesNotMatch(await feedback.innerText(),/任务已暂停/);
  assert.equal((await get('/api/tasks/'+id)).status,'active');
  await page.reload();await card.waitFor();await settle();assert.match(await feedback.innerText(),/数据库写入失败/);
  console.log('Edge real SQLite failure passed: rollback, explicit database error, no false success, feedback survives reload.');return;
 }
 if(mode==='--baseline'){
  await page.locator('#learning-current').getByRole('button',{name:'暂停学习',exact:true}).click();await settle();
  assert.equal((await get('/api/tasks/'+id)).status,'paused');
  const rect=await page.locator('#learning-status').boundingBox();
  assert.ok(rect.y+rect.height<0||rect.y>720,'old success text is outside viewport');
  assert.equal(await card.getByRole('button',{name:'继续学习',exact:true}).count(),0);
  console.log('Baseline reproduced: PATCH/commit/readback paused; feedback outside viewport; no resume entry.');return;
 }
 let release;hold=new Promise(resolve=>release=resolve);
 await page.locator('#learning-current').getByRole('button',{name:'暂停学习',exact:true}).click();
 await feedback.filter({hasText:'正在暂停…'}).waitFor();
 release();hold=null;await settle();await feedback.filter({hasText:'任务已暂停'}).waitFor();
 assert.equal((await get('/api/tasks/'+id)).status,'paused');
 assert.equal(await page.locator('#learning-current').isHidden(),true);
 assert.equal(await card.getByRole('button',{name:'继续学习',exact:true}).count(),1);
 const visible=await feedback.evaluate(n=>{const r=n.getBoundingClientRect();return r.top>=0&&r.bottom<=innerHeight;});assert.ok(visible);
 await page.locator('#learning-refresh').click();await settle();assert.match(await feedback.innerText(),/任务已暂停/);
 await page.reload();await card.waitFor();await settle();assert.match(await feedback.innerText(),/任务已暂停/);
 assert.equal((await get('/api/tasks/'+id)).status,'paused');await click('继续学习');await settle();
 assert.equal((await get('/api/tasks/'+id)).status,'active');await page.locator('#learning-current').waitFor();
 // A malformed success receipt must not turn into a success message.
 badReceipt=true;await click('暂停');await settle();assert.match(await feedback.innerText(),/未取得有效任务状态回执/);
 assert.equal((await get('/api/tasks/'+id)).status,'active');
 await page.getByRole('button',{name:'核对待处理任务状态',exact:true}).click();await settle();
 assert.equal((await get('/api/tasks/'+id)).status,'paused');
 assert.equal(patches.at(-1).request_id,patches.at(-2).request_id);
 await click('继续学习');await settle();
 // Commit succeeds, response disappears: retain exactly the same request across reload.
 drop=true;await click('暂停');await settle();assert.match(await feedback.innerText(),/未完成/);
 assert.equal((await get('/api/tasks/'+id)).status,'paused');const lost=patches.at(-1);
 await page.reload();await card.waitFor();await settle();
 await page.getByRole('button',{name:'核对待处理任务状态',exact:true}).click();await settle();
 assert.deepEqual(patches.at(-1),lost);assert.match(await feedback.innerText(),/任务已暂停/);
 await click('继续学习');await settle();
 badRead=true;await click('暂停');await settle();assert.match(await feedback.innerText(),/合成回读失败/);
 await page.getByRole('button',{name:'核对待处理任务状态',exact:true}).click();await settle();
 await click('继续学习');await settle();
 // Real backend rejection for terminal states; the terminal cards expose no mutating controls.
 await click('完成');await settle();assert.match(await feedback.innerText(),/任务已完成/);
 for(const status of ['active','paused']){const response=await page.context().request.patch(base+'/api/tasks/'+id,{data:{status,request_id:'terminal-'+status}});assert.equal(response.status(),400);}
 assert.equal(await card.getByRole('button',{name:/^(开始|继续学习|暂停|延期)$/}).count(),0);
 const plans=(await get('/api/learning/plans')).plans;const second=plans[0].tasks.find(t=>t.id!==id);
 const secondCard=page.locator(`#learning-plans [data-task-id="${second.id}"]`);await secondCard.getByRole('button',{name:'取消任务',exact:true}).click();await settle();
 assert.equal(await secondCard.getByRole('button',{name:/^(开始|继续学习|暂停|延期)$/}).count(),0);
 assert.equal((await get('/api/tasks/'+id+'/progress')).progress.length,1);
 assert.deepEqual(errors,[]);
 console.log('Task state Edge passed: processing, committed/readback pause/resume/done, visible sticky feedback/reload, same-state no write, malformed/lost receipts/same request, readback failure, terminal UI/API guards, original progress.');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
