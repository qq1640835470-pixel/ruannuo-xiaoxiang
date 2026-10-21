'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require('C:/Users/16408/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const base=process.argv[2];if(!base)throw new Error('Run through test_learning_ui.py: isolated DB required');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1280,height:900}}),errors=[],confirmCalls=[];let malformed=false,failed=false,loseReceipt=false,failWrite=false;
  page.on('dialog',d=>d.accept());page.on('pageerror',e=>errors.push(e.message));
  const today=new Date().toLocaleDateString('sv-SE'),end=new Date();end.setDate(end.getDate()+1);const tomorrow=end.toLocaleDateString('sv-SE');
  const req={course:'电路分析',scope:'节点法与直流电路',start_date:today,deadline:tomorrow,daily_minutes:120,level:'尚不清楚'};
  const plan={requirements:req,title:'两天电路复习',outcome:'写出解题过程与疑问',tasks:[{title:'复习节点法',content:'回看已有笔记',date:today,minutes:40,outcome:'列出方程',kind:'review'},{title:'练习节点法',content:'用已有例题练习',date:tomorrow,minutes:50,outcome:'保留解题过程',kind:'practice'}]};
  const html=fs.readFileSync(path.join(__dirname,'web/index.html'),'utf8').replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi,'').replace('</body>','<script src="/app.js"></script><script src="/learning-model-settings.js"></script><script src="/learning.js"></script></body>');
  await page.route('**/*',async route=>{
   const u=new URL(route.request().url()),body=route.request().postDataJSON();
   if(u.pathname==='/')return route.fulfill({contentType:'text/html',body:html});
   if(u.pathname==='/api/state')return route.fulfill({json:{tasks:[],messages:[],settings:{provider:'gemini',model:'fixture',api_generation_enabled:true}}});
   if(u.pathname==='/api/learning/generate'){
    if(failed)return route.fulfill({status:400,json:{error:'模型失败，未生成计划'}});
    if(malformed)return route.fulfill({status:400,json:{error:'模型数据无效'}});
    return route.fulfill({json:body.stage==='analyze'?{requirements:{...req,scope:'',level:''},questions:['具体范围是什么？','基础如何？'],model:{provider:'fixture',returned_model:'synthetic'}}:{plan,model:{provider:'fixture',returned_model:'synthetic'}}});
   }
   if(u.pathname==='/api/learning/confirm'){
    confirmCalls.push(body);
    if(failWrite)return route.fulfill({status:500,json:{error:'数据库写入失败'}});
    if(loseReceipt){loseReceipt=false;await route.fetch();return route.abort('failed');}
    return route.continue();
   }
   if(u.pathname.startsWith('/api/learning/')||u.pathname.startsWith('/api/tasks/')||u.pathname.startsWith('/api/progress/'))return route.continue();
   if(u.pathname.startsWith('/api/'))return route.fulfill({json:{}});
   return route.continue();
  });
  await page.context().request.get(base+'/');
  await page.goto(base+'/');await page.locator('[data-page=learning]').click();
  const status=page.locator('#learning-status');
  async function library(){await page.locator('#learning-saved').click();if(!await page.locator('.learning-plan').evaluate(n=>n.open))await page.locator('.learning-plan>summary').click();}
  await page.locator('#learning-new').click();
  await page.locator('#learning-request').fill('我想两天复习电路，每天两小时');await page.locator('#learning-input button').click();await status.filter({hasText:'需求分析完成'}).waitFor();
  assert.equal(await page.locator('[name=scope]').inputValue(),'');assert.match(await page.locator('#learning-questions').textContent(),/范围/);
  await page.locator('[name=scope]').fill(req.scope);await page.locator('[name=level]').fill(req.level);
  async function generate(){await page.locator('#learning-requirements button').click();await status.filter({hasText:'草稿已生成'}).waitFor();}
  await generate();assert.equal(await page.locator('#learning-draft fieldset').count(),2);
  await page.getByRole('button',{name:'取消草稿',exact:true}).click();assert.equal(confirmCalls.length,0);
  assert.match(await page.locator('#learning-plans').textContent(),/还没有/);
  await generate();
  await page.locator('#learning-draft input').first().fill('已编辑的电路复习');
  await page.reload();await page.locator('#learning-draft').waitFor({state:'visible'});assert.equal(await page.locator('#learning-draft input').first().inputValue(),'已编辑的电路复习');
  failWrite=true;await page.getByRole('button',{name:'确认保存',exact:true}).click();await status.filter({hasText:'数据库写入失败'}).waitFor();assert.equal(await page.locator('#learning-draft input').first().isDisabled(),false);assert.equal(await page.locator('.learning-plan').count(),0);failWrite=false;
  loseReceipt=true;await page.getByRole('button',{name:'确认保存',exact:true}).click();await status.filter({hasText:'回执不明'}).waitFor();
  assert.equal(await page.locator('#learning-draft input').first().isDisabled(),true);
  await page.reload();assert.equal(await page.locator('#learning-draft input').first().isDisabled(),true);
  await page.getByRole('button',{name:'确认保存',exact:true}).click();await status.filter({hasText:'计划已保存'}).waitFor();await page.waitForFunction(()=>!document.querySelector('#learning-page').hasAttribute('aria-busy'));await library();
  assert.equal(confirmCalls[1].request_id,confirmCalls[2].request_id);assert.equal(await page.locator('.learning-plan').count(),1);
  await page.locator('#learning-plans [data-task-entry] button').first().click();let cards=page.locator('#learning-task-workspace .learning-task');
  await cards.first().getByRole('button',{name:'开始',exact:true}).click();await page.waitForFunction(()=>document.querySelector('#learning-task-workspace .learning-task').textContent.includes('进行中'));
  let form=cards.first().locator('.learning-progress');await form.locator('input').fill('35');await form.locator('textarea').fill('会列方程，计算仍困难');await form.getByRole('button',{name:'记录本次学习'}).click();await status.filter({hasText:'学习记录已保存'}).waitFor();await page.waitForFunction(()=>!document.querySelector('#learning-page').hasAttribute('aria-busy'));
  assert.match(await cards.first().textContent(),/实际 35/);
  await cards.first().getByRole('button',{name:'完成',exact:true}).click();await page.waitForFunction(()=>document.querySelector('#learning-plans').textContent.includes('完成 1 / 2'));
  // The remaining open task can be deferred through the existing state API.
  await library();await page.locator('.learning-plan > details').nth(1).locator('[data-task-entry] button').click();
  const open=page.locator('#learning-task-workspace .learning-task');await open.locator('details').filter({has:page.locator('summary',{hasText:'延期任务'})}).locator('summary').click();await open.locator('form.learning-actions input').fill(tomorrow);await open.getByRole('button',{name:'延期',exact:true}).click();await status.filter({hasText:'延期已保存'}).waitFor();await page.waitForFunction(()=>!document.querySelector('#learning-page').hasAttribute('aria-busy'));assert.match(await open.textContent(),/已延期/);
  await library();const doneGroup=page.locator('.learning-plan > details').nth(2);await doneGroup.locator('summary').first().click();await doneGroup.locator('[data-task-entry] button').click();
  const done=page.locator('#learning-task-workspace .learning-task');await done.locator('details > summary').filter({hasText:'学习记录'}).click();await done.getByRole('button',{name:'更正此记录'}).click();
  const correction=done.locator('.learning-record form');await correction.locator('input').fill('25');await correction.locator('textarea').fill('更正：实际25分钟');await correction.getByRole('button',{name:'保存更正'}).click();await status.filter({hasText:'学习记录已更正'}).waitFor();await page.waitForFunction(()=>!document.querySelector('#learning-page').hasAttribute('aria-busy'));
  assert.match(await page.locator('#learning-plans').textContent(),/累计实际 25/);
  await library();await page.getByRole('button',{name:'编辑此计划'}).click();await page.locator('#learning-draft input').first().fill('同一目标修改');await page.getByRole('button',{name:'确认保存',exact:true}).click();await status.filter({hasText:'计划已保存'}).waitFor();await page.waitForFunction(()=>!document.querySelector('#learning-page').hasAttribute('aria-busy'));
  assert.equal(await page.locator('.learning-plan').count(),1);assert.match(await page.locator('#learning-plans').textContent(),/累计实际 25/);assert.match(await page.locator('#learning-plans').textContent(),/完成 1 \/ 2/);
  await page.reload();await page.locator('.learning-plan').waitFor({state:'attached'});assert.equal(await page.locator('.learning-plan').count(),1);assert.match(await page.locator('#learning-plans').textContent(),/同一目标修改/);
  await page.locator('#learning-new').click();failed=true;await page.locator('#learning-requirements button').click();await status.filter({hasText:'模型失败'}).waitFor();assert.equal(await page.locator('#learning-draft').isVisible(),false);
  failed=false;malformed=true;await page.locator('#learning-requirements button').click();await status.filter({hasText:'数据无效'}).waitFor();assert.equal(await page.locator('.learning-plan').count(),1);
  await page.locator('[data-page=chat]').click();assert.equal(await page.locator('#chat-page').isVisible(),true);assert.equal(await page.locator('#learning-page').isVisible(),false);
  await page.locator('[data-page=plan]').click();assert.equal(await page.locator('#plan-page').isVisible(),true);
  await page.locator('[data-page=learning]').click();await page.locator('.learning-plan').waitFor({state:'attached'});
  await page.setViewportSize({width:390,height:844});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  const shot=path.join(__dirname,'artifacts/learning-mvp-fixture.png');await page.screenshot({path:shot,fullPage:true});
  assert.deepEqual(errors,[]);console.log('Learning UI passed: analyze, clarify, edit, cancel, draft reload, lost receipt retry, confirm, start, complete, defer, progress, correction, saved edit, reload, model failures, navigation, 390px; synthetic models, isolated HTTP/SQLite. Screenshot: '+shot);
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
