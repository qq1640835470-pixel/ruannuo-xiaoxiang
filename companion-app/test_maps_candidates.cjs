'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require('C:/Users/16408/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{
  const browser=await chromium.launch({channel:'msedge',headless:true});
  try{
    const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
    const html=fs.readFileSync(path.join(__dirname,'web/map-workspace.html'),'utf8').replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi,'');
    await page.route('**/*',route=>{
      const url=new URL(route.request().url());
      if(url.pathname==='/api/maps/search')return route.fulfill({json:url.searchParams.get('q')==='legacy'?
        {results:[{name:'旧地点',address:'地址',longitude:114,latitude:22}],detail:'Photon'}:
        {coordinate_system:'GCJ-02',results:[{name:'测试大学(东校区)',address:'东区学院路1号',longitude:114.1,latitude:22.6,url:'https://uri.amap.com/marker?position=114.1%2C22.6'}],detail:'高德地点候选'}});
      return route.fulfill({contentType:'text/html',body:html});
    });
    await page.goto('http://maps-fixture.local/');
    await page.evaluate(()=>{
      window.markerCount=0;
      window.maplibregl={Map:class{addControl(){}on(){}resize(){}jumpTo(){}flyTo(){}},NavigationControl:class{},
        Marker:class{constructor(){window.markerCount++;}setLngLat(){return this;}setPopup(){return this;}addTo(){return this;}remove(){}},Popup:class{setDOMContent(){return this;}}};
    });
    await page.addScriptTag({path:path.join(__dirname,'web/map-workspace.js')});
    await page.locator('#query').fill('测试大学');await page.locator('#search button').click();
    await page.waitForFunction(()=>document.querySelector('#status').textContent==='高德地点候选');
    assert.equal(await page.locator('#map').isHidden(),true);assert.equal(await page.evaluate(()=>markerCount),0);
    assert.match(await page.locator('#results a').textContent(),/东区学院路1号/);
    assert.match(await page.locator('#results a').getAttribute('href'),/^https:\/\/uri\.amap\.com\/marker/);
    await page.locator('#query').fill('legacy');await page.locator('#search button').click();
    await page.waitForFunction(()=>document.querySelector('#status').textContent==='Photon');
    assert.equal(await page.locator('#map').isHidden(),false);assert.equal(await page.evaluate(()=>markerCount),1);
    assert.equal(await page.locator('#results a').count(),0);assert.deepEqual(errors,[]);
    console.log('PASS map candidates: official links and addresses; GCJ-02 never marked on WGS84 basemap; legacy markers preserved.');
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
