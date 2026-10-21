'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require('C:/Users/16408/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const base=process.argv[2];if(!base)throw new Error('Use the isolated Python runner');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1280,height:900}}),errors=[],writes=[];
  let loseGenerate=true,loseSubmit=true;
  page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());
  const html=fs.readFileSync(path.join(__dirname,'web/index.html'),'utf8').replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi,'').replace('</body>','<script src="/app.js"></script><script src="/learning-model-settings.js"></script><script src="/learning.js"></script><script src="/learning-checks.js"></script></body>');
  await page.route('**/*',async route=>{
   const req=route.request(),u=new URL(req.url());
   if(u.pathname==='/')return route.fulfill({contentType:'text/html',body:html});
   if(u.pathname==='/api/state')return route.fulfill({json:{tasks:[],messages:[],settings:{provider:'openrouter',model:'fixture/model',api_generation_enabled:true}}});
   if(u.pathname==='/api/learning/checks'&&req.method()==='POST'){
    writes.push(req.postDataJSON());
    if(loseGenerate){loseGenerate=false;await route.fetch();return route.abort('failed');}
   }
   if(u.pathname.endsWith('/submit')){
    writes.push(req.postDataJSON());
    if(loseSubmit){loseSubmit=false;await route.fetch();return route.abort('failed');}
   }
   if(u.pathname.startsWith('/api/learning/')||u.pathname.startsWith('/api/tasks/'))return route.continue();
   if(u.pathname.startsWith('/api/'))return route.fulfill({json:{}});
   return route.continue();
  });
  await page.context().request.get(base+'/');await page.goto(base+'/');await page.locator('[data-page=learning]').click();
  await page.locator('#learning-saved').click();await page.locator('.learning-plan>summary').first().click();await page.locator('#learning-plans [data-task-entry] button').first().click();
  await page.locator('#learning-task-workspace .learning-task').first().getByRole('button',{name:'检验学习成果',exact:true}).click();
  assert.match(await page.locator('#check-selection').textContent(),/所选任务/);
  await page.locator('#check-generate button').click();await page.locator('#check-pending button').first().waitFor();
  await page.waitForFunction(()=>!document.querySelector('#learning-checks').hasAttribute('aria-busy'));
  await page.reload();await page.locator('#check-pending button').first().waitFor();
  await page.waitForFunction(()=>!document.querySelector('#learning-checks').hasAttribute('aria-busy'));
  await page.getByRole('button',{name:'核对同一请求',exact:true}).click();await page.locator('#check-current fieldset').first().waitFor();
  assert.equal(writes[0].request_id,writes[1].request_id);assert.equal(await page.locator('#check-current fieldset').count(),3);
  assert.doesNotMatch(await page.locator('#check-current').textContent(),/参考答案：/);
  await page.locator('[data-question="1"] input').first().check();await page.locator('[data-question="2"] input').last().check();await page.locator('[data-question="3"] textarea').fill('先选择参考节点，再列方程');
  await page.locator('#check-evaluate').check();await page.getByRole('button',{name:'提交答案并保存结果',exact:true}).click();
  await page.waitForFunction(()=>!document.querySelector('#learning-checks').hasAttribute('aria-busy'));
  assert.equal(await page.locator('#check-current textarea').first().isDisabled(),true);
  await page.reload();await page.getByRole('button',{name:'核对同一请求',exact:true}).waitFor();
  await page.waitForFunction(()=>!document.querySelector('#learning-checks').hasAttribute('aria-busy'));
  await page.getByRole('button',{name:'核对同一请求',exact:true}).click();await page.locator('#check-status').filter({hasText:'结果已保存'}).waitFor();
  assert.equal(writes[2].request_id,writes[3].request_id);
  assert.match(await page.locator('#check-current').textContent(),/客观题：1 \/ 2/);assert.match(await page.locator('#check-current').textContent(),/遗漏定义/);
  const first=page.locator('#check-current fieldset').first();await first.locator('summary').click();await first.locator('select').selectOption('uncertain');await first.locator('textarea').fill('参考解释需要核对教材');await first.getByRole('button',{name:'保存评价更正',exact:true}).click();
  await page.locator('#check-current').getByText('用户更正：未可靠评价 · 参考解释需要核对教材',{exact:true}).waitFor();
  await page.reload();await page.locator('#learning-checks>summary').click();await page.locator('#check-current').getByText('用户更正：未可靠评价 · 参考解释需要核对教材',{exact:true}).waitFor();
  assert.equal(await page.locator('#check-history .learning-record').count(),1);
  assert.match(await page.locator('#learning-plans').textContent(),/完成 0 \/ 2/);
  await page.locator('#check-history').getByRole('button',{name:'删除测验记录',exact:true}).click();await page.locator('#check-history').getByText('暂无检验记录。',{exact:true}).waitFor();
  const cleared=await page.evaluate(()=>JSON.parse(localStorage.getItem('xiaoxiang-learning-check-pending-v1')));assert.equal(cleared.activeId,undefined);assert.deepEqual(cleared.answers,{});
  await page.reload();await page.locator('#learning-checks>summary').click();await page.locator('#check-history').getByText('暂无检验记录。',{exact:true}).waitFor();assert.equal(await page.locator('#check-current fieldset').count(),0);
  await page.locator('#check-topic-mode').click();await page.locator('#check-topic').fill('节点法');await page.locator('#check-generate button').click();await page.locator('#check-current fieldset').first().waitFor();
  assert.equal(writes.at(-1).topic,'节点法');assert.equal(writes.at(-1).task_id,undefined);
  await page.setViewportSize({width:390,height:844});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),true);
  await page.getByRole('button',{name:'刷新检验历史',exact:true}).click();await page.waitForFunction(()=>!document.querySelector('#learning-checks').hasAttribute('aria-busy'));
  await page.screenshot({path:path.join(__dirname,'artifacts/learning-checks-fixture.png'),fullPage:true});
  assert.deepEqual(errors,[]);console.log('Learning checks UI passed: selection, real temporary HTTP/SQLite, lost receipts, answers, feedback, corrections, reload, delete, topic, 390px.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
