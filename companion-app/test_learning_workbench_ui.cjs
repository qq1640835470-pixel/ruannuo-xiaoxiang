'use strict';
const assert=require('node:assert/strict'),path=require('node:path');
const {chromium}=require('C:/Users/16408/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const [base,id]=process.argv.slice(2);
if(!base?.startsWith('http://127.0.0.1:')||!id)throw Error('Use isolated workbench fixture');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
  const context=await browser.newContext({viewport:{width:1280,height:900}});let page=await context.newPage();
  const errors=[],posts=[];let accept=true,loseProgress=true,loseSearch=true,loseSave=true,loseCheck=true;
  context.on('page',p=>{p.on('pageerror',e=>errors.push(e.message));p.on('dialog',d=>accept?d.accept():d.dismiss());});
  page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>accept?d.accept():d.dismiss());
  await context.route('**/*',async route=>{
   const req=route.request(),u=new URL(req.url());if(u.origin!==base)return route.abort('blockedbyclient');
   if(req.method()==='POST')posts.push({path:u.pathname,body:req.postDataJSON()});
   if(u.pathname===`/api/tasks/${id}/progress`&&req.method()==='POST'&&loseProgress){loseProgress=false;await route.fetch();return route.abort('failed');}
   if(u.pathname==='/api/learning/resources/search'&&loseSearch){loseSearch=false;await route.fetch();return route.abort('failed');}
   if(u.pathname==='/api/learning/resources/save'&&loseSave){loseSave=false;await route.fetch();return route.abort('failed');}
   if(u.pathname==='/api/learning/checks'&&req.method()==='POST'&&loseCheck){loseCheck=false;await route.fetch();return route.abort('failed');}
   return route.continue();
  });
  const open=async()=>{await page.goto(base+'/#learning');await page.locator('#learning-today [data-task-entry]').first().waitFor();};
  const settle=()=>page.waitForFunction(()=>!document.querySelector('#learning-page').hasAttribute('aria-busy'));
  const count=p=>posts.filter(r=>r.path===p).length;
  const get=p=>page.evaluate(async p=>(await fetch(p)).json(),p);
  await open();
  assert.equal(await page.locator('#learning-today [data-task-entry]').count(),2);
  assert.match(await page.locator('#learning-today [data-task-entry]').first().innerText(),/昨日学习任务/);
  assert.equal(await page.locator('#learning-page form:visible').count(),0);
  await page.locator(`#learning-today [data-task-entry="${id}"] button`).click();await settle();
  const card=()=>page.locator(`#learning-task-workspace [data-task-id="${id}"]`);
  assert.match(await card().innerText(),/回顾参考节点与节点电压/);
  await page.locator('#learning-task-resources a').filter({hasText:'节点法合成讲义'}).waitFor();
  assert.doesNotMatch(await page.locator('#learning-task-resources').innerText(),/其他任务资源/);
  const saved=(await get('/api/learning/plans')).plans[0],task=saved.tasks.find(t=>t.id===id);
  assert.equal(count('/api/learning/resources/search'),0);assert.equal(count('/api/learning/checks'),0);
  for(const [label,status] of [['开始','active'],['暂停','paused'],['继续学习','active'],['暂停','paused']]){
   await card().getByRole('button',{name:label,exact:true}).click();await settle();assert.equal((await get('/api/tasks/'+id)).status,status);
   assert.match(await page.locator('#learning-task-feedback').innerText(),/已保存并核对/);
  }
  await card().locator('.learning-progress input').fill('17');await card().locator('.learning-progress textarea').fill('合成学习收获');
  await card().getByRole('button',{name:'记录本次学习',exact:true}).click();await settle();
  await page.reload();await card().waitFor();await settle();
  await page.getByRole('button',{name:'重试待核学习记录',exact:true}).click();await settle();
  const progress=await get('/api/tasks/'+id+'/progress');assert.equal(progress.progress.length,1);assert.equal(progress.progress[0].minutes,17);
  const records=posts.filter(r=>r.path===`/api/tasks/${id}/progress`);assert.equal(records[0].body.request_id,records[1].body.request_id);
  await card().getByRole('button',{name:'查找更多相关资源',exact:true}).click();await settle();
  assert.equal(await page.locator('#resources-course').inputValue(),saved.requirements.course);
  assert.equal(await page.locator('#resources-topic').inputValue(),task.learning.content);
  assert.equal(await page.locator('#resources-level').inputValue(),saved.requirements.level);
  assert.equal(await page.locator('#resources-task').inputValue(),id);
  assert.equal(count('/api/learning/resources/preview'),0);assert.equal(count('/api/learning/resources/search'),0);
  await page.locator('#resources-form button').click();await page.locator('#resources-preview button').waitFor();
  accept=false;await page.locator('#resources-preview button').click();await page.waitForFunction(()=>!document.querySelector('#learning-resources').hasAttribute('aria-busy'));
  assert.equal(count('/api/learning/resources/search'),0);
  accept=true;await page.locator('#resources-preview button').click();await page.locator('#resources-recover').waitFor();
  await page.locator('#resources-recover').click();await page.locator('.resource-choice').first().waitFor();
  assert.equal(count('/api/learning/resources/search'),1);
  await page.locator('.resource-choice').first().check();await page.locator('#resources-save').click();await page.locator('#resources-recover').waitFor();
  await page.reload();await card().waitFor();await page.locator('#resources-recover').click();await page.waitForFunction(()=>!document.querySelector('#learning-resources').hasAttribute('aria-busy'));
  assert.equal(await page.locator('#resources-task').inputValue(),id);assert.equal(count('/api/learning/resources/save'),1);
  assert.equal(posts.find(r=>r.path==='/api/learning/resources/save').body.task_id,id);
  assert.ok((await get('/api/learning/resources?task_id='+id)).resources.length>1);
  await card().getByRole('button',{name:'检验学习成果',exact:true}).click();await settle();
  assert.match(await page.locator('#check-selection').innerText(),/复习节点法/);assert.equal(await page.locator('#check-topic').isVisible(),false);
  accept=false;await page.locator('#check-generate button').click();await page.waitForFunction(()=>!document.querySelector('#learning-checks').hasAttribute('aria-busy'));
  assert.equal(count('/api/learning/checks'),0);
  accept=true;await page.locator('#check-generate button').click();await page.getByRole('button',{name:'核对同一请求',exact:true}).waitFor();
  await page.reload();await card().waitFor();await page.getByRole('button',{name:'核对同一请求',exact:true}).click();await page.locator('#check-current fieldset').first().waitFor();
  const checks=posts.filter(r=>r.path==='/api/learning/checks');assert.equal(checks.length,2);assert.equal(checks[0].body.request_id,checks[1].body.request_id);assert.equal(checks[0].body.task_id,id);
  assert.equal((await get('/api/learning/checks')).checks.length,1);
  await page.locator('#check-current [data-question="1"] input').first().check();
  await page.close();page=await context.newPage();await open();await card().waitFor();
  await page.locator('#learning-checks>summary').click();await page.locator('#check-current fieldset').first().waitFor();assert.equal(await page.locator('#check-current [data-question="1"] input').first().isChecked(),true);
  assert.equal((await get('/api/tasks/'+id)).status,'paused');assert.equal((await get('/api/tasks/'+id+'/progress')).progress.length,1);
  await page.locator('#learning-checks>summary').click();await page.locator('#learning-page').evaluate(n=>n.scrollTop=0);
  await page.screenshot({path:path.join(__dirname,'artifacts/learning-workbench-wide.png')});
  await page.setViewportSize({width:600,height:800});await page.locator('#learning-page').evaluate(n=>n.scrollTop=0);
  assert.ok(await page.locator('#learning-today').isVisible());assert.equal(await page.locator('#learning-create').evaluate(n=>n.open),false);
  assert.ok(await page.locator('#learning-page').evaluate(n=>n.scrollWidth<=n.clientWidth+1));
  await page.screenshot({path:path.join(__dirname,'artifacts/learning-workbench-narrow.png')});
  assert.deepEqual(errors,[]);
  console.log('Workbench Edge passed: today/overdue, task/resources, no automatic search, state/readback, record/search/save/check lost receipts, same request recovery, answers and context after reopening, 600px layout.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
