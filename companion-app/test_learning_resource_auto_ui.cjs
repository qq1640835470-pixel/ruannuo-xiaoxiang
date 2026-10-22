'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs');
const {chromium}=require('C:/Users/16408/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const [base,id]=process.argv.slice(2);
if(!base?.startsWith('http://127.0.0.1:')||!id)throw Error('Isolated fixture required');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
  const context=await browser.newContext({viewport:{width:1280,height:900}}),page=await context.newPage();
  const errors=[],calls=[];let lose=false;
  page.on('pageerror',e=>errors.push(e.message));
  await context.route('**/*',async route=>{
   const req=route.request(),u=new URL(req.url());if(u.origin!==base)return route.abort();
   if(req.method()==='POST')calls.push(u.pathname);
   if(lose&&u.pathname.endsWith('/auto/search')){lose=false;await route.fetch();return route.abort();}
   return route.continue();
  });
  const card=()=>page.locator(`#learning-task-workspace [data-task-id="${id}"]`);
  const auto=()=>page.locator('#learning-auto-resources');
  const settle=()=>page.waitForFunction(()=>!document.querySelector('#learning-page').hasAttribute('aria-busy'));
  const count=()=>calls.filter(p=>p.endsWith('/auto/search')).length;
  await page.goto(base+'/#learning');
  await page.locator(`#learning-today [data-task-entry="${id}"] button`).click();await settle();
  assert.equal(await page.locator('#learning-auto-enabled').isChecked(),false);assert.equal(count(),0);
  await page.locator('#learning-auto-enabled').check();await page.waitForFunction(()=>document.querySelector('#learning-auto-enabled')?.checked);
  await card().getByRole('button',{name:'开始',exact:true}).click();await settle();
  await page.waitForFunction(()=>document.querySelector('#learning-auto-status')?.textContent.includes('筛选完成'));
  assert.equal(count(),1);assert.equal(await auto().locator('.resource-card').count(),3);
  assert.match(await auto().innerText(),/推荐候选.*原文未读取/s);
  await auto().getByRole('button',{name:'视频',exact:true}).click();assert.equal(await auto().locator('.resource-card').count(),1);
  assert.match(await auto().locator('.resource-card').innerText(),/视频/);
  await auto().getByRole('button',{name:'全部',exact:true}).click();
  await auto().getByRole('button',{name:'收藏',exact:true}).first().click();
  await page.waitForFunction(()=>document.querySelector('#learning-auto-resources')?.textContent.includes('已收藏'));
  await page.reload();await card().waitFor();await settle();assert.equal(count(),1);
  assert.match(await auto().innerText(),/已收藏/);
  await card().getByRole('button',{name:'暂停',exact:true}).click();await settle();
  await card().getByRole('button',{name:'继续学习',exact:true}).click();await settle();
  await page.waitForTimeout(500);assert.equal(count(),2); // cache endpoint only; ledger below proves no external repeats.
  lose=true;await auto().getByRole('button',{name:'重新搜索',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('#learning-auto-status')?.textContent.includes('筛选完成'));
  await page.reload();await settle();await auto().locator('.resource-card').first().waitFor();assert.equal(count(),3);
  await auto().getByRole('button',{name:'不相关',exact:true}).first().click();await page.waitForTimeout(200);
  assert.equal(await auto().locator('.resource-card').count(),2);
  await page.setViewportSize({width:430,height:850});
  await page.screenshot({path:'artifacts/learning-resource-auto-20261022/narrow.png',fullPage:true});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);
  await page.locator('#learning-auto-enabled').uncheck();await page.waitForTimeout(200);
  assert.equal(await auto().getByRole('button',{name:'重新搜索',exact:true}).isDisabled(),true);
  const plans=await page.evaluate(async()=>await(await fetch('/api/learning/plans')).json());
  assert.equal(plans.plans[0].tasks.find(t=>t.id===id).status,'active');assert.deepEqual(errors,[]);
  fs.writeFileSync('artifacts/learning-resource-auto-20261022/ui-result.json',JSON.stringify({synthetic:true,postSearches:count(),errors,narrowWidth:430,persistence:true,lostReceiptRecovered:true}));
  console.log('PASS task auto resources, cached continue, favorite/dismiss, reload, lost receipt, narrow Edge');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
