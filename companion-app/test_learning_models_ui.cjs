'use strict';
const assert=require('node:assert/strict');
const {chromium}=require('C:/Users/16408/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const base=process.argv[2];if(!base?.startsWith('http://127.0.0.1:'))throw Error('Isolated fixture only');
const learning='vendor/independent-learning',other='vendor/other-chat';
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
  const page=await browser.newPage(),errors=[],dialogs=[],requests=[];let swap=false,lose=false;
  page.on('pageerror',e=>errors.push(e.message));
  page.on('dialog',async d=>{dialogs.push(d.message());if(swap){swap=false;await page.request.patch(base+'/api/settings',{data:{learning_model_config:{mode:'independent',provider:'openrouter',model:other}}});}await d.accept();});
  await page.context().request.get(base+'/');
  await page.route('**/api/learning/generate',async route=>{requests.push(route.request().postDataJSON());if(lose){lose=false;await route.fetch();return route.abort('failed');}return route.continue();});
  await page.goto(base+'/#learning');await page.locator('#learning-model-current').filter({hasText:'跟随聊天'}).waitFor();
  await page.locator('#settings-open').click();await page.locator('#model-center summary').click();await page.locator('#model-center-search').fill(learning);
  let card=page.locator(`[data-model-id="${learning}"]`);await card.getByRole('button',{name:'收藏',exact:true}).click();
  await card.getByRole('button',{name:'用作学习模型（再保存设置）',exact:true}).click();
  assert.equal(await page.locator('#model-select').inputValue(),'openrouter');assert.equal(await page.locator('#chat-model-id').inputValue(),'fixture/learning-034');
  assert.equal(await page.locator('#learning-model-mode').inputValue(),'independent');
  assert.equal((await (await page.request.get(base+'/api/settings')).json()).learning_model_config.mode,'follow');
  await page.locator('#save-settings').click();await page.locator('#settings-save-status').filter({hasText:'设置已保存'}).waitFor();
  await page.locator('#model-center-search').fill(other);await page.locator(`[data-model-id="${other}"]`).getByRole('button',{name:'用作聊天模型（再保存设置）',exact:true}).click();
  await page.locator('#save-settings').click();await page.locator('#settings-save-status').filter({hasText:'设置已保存'}).waitFor();
  let s=await (await page.request.get(base+'/api/settings')).json();assert.equal(s.chat_models.openrouter,other);assert.equal(s.learning_selection.model,learning);
  await page.locator('#settings-close').click();await page.locator('#learning-model-evidence').locator('..').locator('summary').click();await page.locator('#learning-model-evidence').filter({hasText:'候选'}).waitFor();
  // A successful response is lost: reload must recover the same request with no second generation.
  await page.locator('#learning-new').click();lose=true;await page.locator('#learning-request').fill('合成节点法要求');await page.locator('#learning-input button').click();
  await page.locator('#learning-generation-pending').filter({hasText:'回执待核'}).waitFor();
  await page.reload();await page.getByRole('button',{name:'核对同一学习生成请求',exact:true}).click();
  await page.locator('#learning-status').filter({hasText:'已恢复同一请求结果'}).waitFor();assert.deepEqual(requests[0],requests[1]);
  await page.locator('#learning-checks>summary').click();await page.locator('#check-topic').fill('节点法');await page.locator('#check-generate button[type=submit]').click();await page.locator('#check-current').filter({hasText:'请求 '+learning+' → 返回 '+learning}).waitFor();
  assert(dialogs.some(d=>d.includes(learning)));assert.doesNotMatch(await page.locator('#learning-model-evidence').textContent(),/本机已验证/);
  // Change settings in a different client between confirmation preview and actual submission.
  swap=true;await page.locator('#check-generate button[type=submit]').click();await page.locator('#check-status').filter({hasText:'学习模型选择已变化'}).waitFor();
  await page.reload();await page.locator('#learning-model-current').filter({hasText:other}).waitFor();
  await page.locator('#settings-open').click();await page.locator('.settings-group > summary').filter({hasText:'学习模型'}).click();await page.locator('#learning-model-follow').click();await page.locator('#save-settings').click();await page.locator('#settings-save-status').filter({hasText:'设置已保存'}).waitFor();
  s=await (await page.request.get(base+'/api/settings')).json();assert.equal(s.learning_model_config.mode,'follow');assert.equal(s.learning_selection.model,other);
  const center=await (await page.request.get(base+'/api/models/center')).json();assert(center.preferences.favorites.includes(learning));assert(center.preferences.recent.includes(learning));
  await page.request.patch(base+'/api/settings',{data:{provider:'local'}});await page.reload();
  await page.locator('#learning-model-current').filter({hasText:'local / auto'}).waitFor();
  await page.locator('#settings-open').click();await page.locator('.settings-group > summary').filter({hasText:'学习模型'}).click();await page.locator('#local-model-selection').selectOption('qwen3-4b-q4_k_m');
  await page.locator('#learning-model-summary').filter({hasText:'local / qwen3-4b-q4_k_m'}).waitFor();
  let local=(await (await page.request.get(base+'/api/settings')).json()).learning_selection;
  await page.locator('#local-model-selection').selectOption('qwen3-8b-q4_k_m');
  await page.locator('#learning-model-summary').filter({hasText:'local / qwen3-8b-q4_k_m'}).waitFor();
  await page.locator('#local-model-selection').selectOption('qwen3-4b-q4_k_m');
  await page.locator('#learning-model-summary').filter({hasText:'local / qwen3-4b-q4_k_m'}).waitFor();
  assert((await (await page.request.get(base+'/api/settings')).json()).learning_selection.revision>local.revision);
  await page.locator('#settings-close').click();await page.setViewportSize({width:390,height:844});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);assert.deepEqual(errors,[]);
  console.log('Independent learning models Edge passed: distinct chat/learning choices, saved summaries/evidence, favorite/recent, lost analysis receipt/reload, exact requested/returned quiz IDs, stale consent blocked, restore follow, 390px.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
