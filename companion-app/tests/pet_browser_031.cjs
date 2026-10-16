"use strict";
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require('C:/Users/16408/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const ROOT=path.resolve(__dirname,'..');
const original=fs.readFileSync(path.join(ROOT,'web/index.html'),'utf8');
const pet=original.match(/<section id="sakiko-companion"[\s\S]*?<\/section>/)[0];
const html=`<!DOCTYPE html><html><head><meta charset="utf-8"><link rel="stylesheet" href="/styles.css"></head><body><div class="app-shell"><aside class="sidebar">${pet}<button id="pet-home" hidden>召回</button></aside><main><div class="topbar"></div><form id="chat-form"></form></main></div><script>window.api=async()=>({pet_ai_enabled:false,api_generation_enabled:false});</script><script src="/pet-motion.js"></script><script src="/pet-physics.js"></script><script src="/pet-world.js"></script><script src="/companion.js"></script></body></html>`;
(async()=>{
  const browser=await chromium.launch({channel:'msedge',headless:true});
  const page=await browser.newPage({viewport:{width:1280,height:800}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/pet-fixture-031',route=>route.fulfill({contentType:'text/html',body:html}));
  await page.goto('http://127.0.0.1:18764/pet-fixture-031');
  await page.waitForFunction(()=>document.querySelector('#sakiko-companion')?.dataset.ready==='true'&&document.querySelector('#pet-renderer'));
  assert.equal(await page.locator('#pet-renderer').inputValue(),'chibi');
  await page.locator('.pet-mode-panel summary').click();
  for(const activity of ['lunch','sleepy','music','happy','surprised']){
    await page.locator('#pet-activity').selectOption(activity);
    await page.waitForFunction(value=>document.querySelector('#sakiko-companion').dataset.activity===value,activity);
    if(activity==='music')await page.screenshot({path:path.join(ROOT,'web/assets/pet/qa-chibi-music.png')});
  }
  await page.locator('#pet-activity').selectOption('auto');
  await page.evaluate(()=>window.dispatchEvent(new CustomEvent('xy:music-state',{detail:{playing:true,title:'本机测试曲目',artist:'测试'}})));
  await page.waitForFunction(()=>document.querySelector('#sakiko-companion').dataset.activity==='music');
  for(let i=0;i<10;i++)await page.locator('#pet-pat').click();
  assert.equal(await page.locator('#sakiko-companion').getAttribute('data-sulking'),'false');
  await page.locator('#pet-pat').click();assert.equal(await page.locator('#sakiko-companion').getAttribute('data-sulking'),'true');
  assert.equal(await page.locator('#sakiko-companion').getAttribute('data-turning-away'),'true');
  for(const edge of ['left','right','top','bottom']){
    await page.evaluate(edge=>{localStorage.setItem('xy.pet.world',JSON.stringify({free:true,x:.4,y:.4,dock:{id:'window-edge:'+edge,edge,mode:'peek',fraction:.5,yFraction:.5}}));},edge);
    await page.reload();await page.waitForFunction(()=>document.querySelector('#sakiko-companion')?.dataset.ready==='true');
    const geometry=await page.locator('.pet-stage').evaluate(el=>{const r=el.getBoundingClientRect();return {x:r.x,y:r.y,right:r.right,bottom:r.bottom,clip:el.style.clipPath,width:innerWidth,height:innerHeight};});
    assert.ok(edge==='left'?geometry.x<0:edge==='right'?geometry.right>geometry.width:edge==='top'?geometry.y<0:geometry.bottom>geometry.height,edge);
    assert.ok(geometry.clip.includes('inset'),edge+' viewport clip');
    await page.screenshot({path:path.join(ROOT,'web/assets/pet/qa-edge-'+edge+'.png')});
  }
  await page.evaluate(()=>localStorage.removeItem('xy.pet.world'));await page.reload();
  await page.waitForSelector('#pet-renderer',{state:'attached'});await page.locator('.pet-mode-panel summary').click();
  if(fs.existsSync(path.join(ROOT,'web/assets/pet/vendor/live2dcubismcore.min.js'))){
    await page.locator('#pet-renderer').selectOption('live2d');
    await page.waitForFunction(()=>document.querySelector('#sakiko-companion').dataset.live2dReady==='true',{timeout:45000});
    assert.equal(await page.locator('#pet-costume option').count(),5);assert.equal(await page.locator('#pet-expression option').count(),28);assert.equal(await page.locator('#pet-motion option').count(),64);
    await page.locator('#pet-expression').selectOption('exp_smile01');await page.locator('#pet-play-motion').click();
    await page.screenshot({path:path.join(ROOT,'web/assets/pet/qa-live2d.png')});
    for(const outfit of ['010_live_01','010_school_summer_hs_1st','010_school_winter_hs_1st','010_school_winter_jhs']){
      await page.locator('#pet-costume').selectOption(outfit);
      await page.waitForFunction(value=>document.querySelector('#sakiko-companion').dataset.live2dCostume===value,outfit);
      await page.locator('#pet-expression').selectOption('exp_shy01');await page.locator('#pet-motion').selectOption('mtn_bye01_C');await page.locator('#pet-play-motion').click();
    }
    console.log('Actual Cubism renderer: 5 costumes loaded, expression/motion controls exercised.');
    await page.locator('#pet-renderer').selectOption('chibi');assert.equal(await page.locator('#sakiko-companion').getAttribute('data-renderer'),'chibi');
  }
  assert.deepEqual(errors,[]);console.log('Browser pet fixture passed: real Q sprite, activities, music event, 11 pats and actual clipped viewport docking.');
  await browser.close();
})().catch(error=>{console.error(error);process.exit(1);});
