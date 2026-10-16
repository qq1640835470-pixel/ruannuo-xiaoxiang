"use strict";
(() => {
  const section=document.querySelector('#location-settings');if(!section)return;
  const city=section.querySelector('#location-city'),message=section.querySelector('#location-status'),output=section.querySelector('#location-weather');
  const buttons=[...section.querySelectorAll('button')];
  let current={mode:'disabled',enabled:false},busy=false,generation=0,lastAutoAttempt=0;
  function render(value){
    current=value.location||value;
    message.textContent=current.enabled?`${current.label} · ${current.mode==='manual'?'手动城市':'设备粗略定位'}${current.timezone?' · '+current.timezone:''}${current.updated_at?' · 更新于 '+new Date(current.updated_at).toLocaleString('zh-CN'):''}`:'尚未启用位置。可以输入城市，也可以主动开启设备定位。';
    section.querySelector('#location-disable').disabled=busy||!current.enabled;
    window.dispatchEvent(new CustomEvent('xy:location',{detail:current}));
  }
  async function forecast(token=generation){
    if(!current.enabled)return;
    const value=await api('/api/location/weather');if(token!==generation)return;
    const data=value.weather||value;
    if(data.status!=='ok'){output.textContent=data.detail||'天气暂不可用，请稍后刷新。';return;}
    current.timezone=data.timezone;render(current);
    output.textContent=`${data.location}：${data.current.summary}，${data.current.temperature_2m}°C。\n${data.days.map(d=>`${d.date} ${d.summary}，${d.temperature_2m_min}–${d.temperature_2m_max}°C`).join('\n')}\n来源：Open-Meteo · ${data.timezone} · 查询于 ${new Date(data.queried_at).toLocaleString('zh-CN')}`;
    window.dispatchEvent(new CustomEvent('xy:weather',{detail:data}));
  }
  async function run(action){
    if(busy)return;busy=true;const token=++generation;buttons.forEach(b=>b.disabled=true);
    try{await action(token);}catch(e){message.textContent=e.message||'位置操作未完成，请稍后重试。';}
    finally{busy=false;buttons.forEach(b=>b.disabled=false);section.querySelector('#location-disable').disabled=!current.enabled;}
  }
  function coordinates(){
    if(!navigator.geolocation)return Promise.reject(new Error('当前浏览器不支持设备定位，请手动输入城市。'));
    return new Promise((resolve,reject)=>navigator.geolocation.getCurrentPosition(
      p=>resolve({latitude:Math.round(p.coords.latitude*100)/100,longitude:Math.round(p.coords.longitude*100)/100}),
      e=>reject(new Error(e.code===1?'定位未获授权。可在浏览器或系统设置中允许，也可以手动选择城市。':e.code===3?'定位超时，请重试或手动选择城市。':'暂时无法取得设备位置，请手动选择城市。')),
      {enableHighAccuracy:false,maximumAge:300000,timeout:12000}));
  }
  async function locate(token,automatic=false){
    message.textContent='正在向浏览器请求粗略位置…';
    const point=await coordinates();
    if(token!==generation)return;
    const value=await api('/api/location/update',{method:'POST',body:JSON.stringify({mode:'geolocation',...point,auto_refresh:true,automatic})});
    if(token!==generation)return;render(value);if(!value.ignored)await forecast(token);
  }
  section.querySelector('#location-enable').addEventListener('click',()=>run(token=>locate(token)));
  section.querySelector('#location-manual').addEventListener('click',()=>run(async token=>{
    if(!city.value.trim())throw new Error('先填入城市名称吧。');
    message.textContent='正在查找城市…';const value=await api('/api/location/update',{method:'POST',body:JSON.stringify({mode:'manual',city:city.value.trim()})});
    if(token!==generation)return;render(value);await forecast(token);
  }));
  section.querySelector('#location-refresh').addEventListener('click',()=>run(async token=>{
    if(!current.enabled)throw new Error('请先选择城市或启用设备定位。');
    if(current.mode==='geolocation')await locate(token);else await forecast(token);
  }));
  section.querySelector('#location-disable').addEventListener('click',()=>run(async()=>{
    const value=await api('/api/location/update',{method:'POST',body:JSON.stringify({mode:'disabled'})});render(value);output.textContent='';
  }));
  async function autoRefresh(){
    if(busy||document.hidden||current.mode!=='geolocation'||!current.auto_refresh)return;
    const now=Date.now(),updated=Date.parse(current.updated_at)||0;
    if(now-updated<1800000||now-lastAutoAttempt<1800000)return;
    lastAutoAttempt=now;
    try{if(!navigator.permissions||(await navigator.permissions.query({name:'geolocation'})).state!=='granted')return;}
    catch{return;}
    await run(token=>locate(token,true));
  }
  window.addEventListener('focus',autoRefresh);
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)autoRefresh();});
  setInterval(autoRefresh,1800000);
  api('/api/location/status').then(value=>{render(value);autoRefresh();}).catch(()=>{message.textContent='位置设置暂未连接，请稍后刷新页面。';});
})();
