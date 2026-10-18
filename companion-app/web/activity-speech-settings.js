"use strict";
(() => {
  const host=document.querySelector('#settings-drawer .drawer-body');
  if(!host)return;
  const section=document.createElement('details');section.id='activity-settings';
  section.innerHTML=`<summary>应用使用与免费语音</summary>
    <label><input type="checkbox" id="activity-enabled">记录前台程序名称与时长</label>
    <p>仅本机保存14天；每5秒采样。不读取窗口文字、截图或键盘内容，不上传模型。</p>
    <p id="activity-current" role="status"></p><div id="activity-today"></div>
    <p id="fish-status" role="status"></p><button type="button" id="fish-retry">重新验证免费语音</button>
    <label>朗读语言 <select id="speech-language"><option value="auto">原文（不翻译）</option><option value="zh">中文／普通话</option><option value="ja">日语</option><option value="yue">粤语</option><option value="en">英语</option></select></label>
    <p>选目标语言后，点击对话中的“生成语音”：先在本机翻译，再将译文发给Fish。每次处理前600字；口音受音色影响，粤语需试听核对。</p>
    <p id="speech-progress" role="status"></p><details id="speech-preview" hidden><summary>本次朗读文本</summary><p id="speech-text"></p></details>
    <label><input type="checkbox" id="fish-idle">闲聊后播放免费语音</label>
    <p>每15分钟最多一次闲聊：文本使用本地模型；Fish只用已核实免费型号。没有免费资格时暂停，不切换付费。</p>`;
  host.append(section);
  const enabled=section.querySelector('#activity-enabled'),current=section.querySelector('#activity-current'),today=section.querySelector('#activity-today'),voiceStatus=section.querySelector('#fish-status');
  let loading=false;
  async function refresh(){
    if(loading)return;loading=true;
    try{
      const data=await api('/api/activity/status');enabled.checked=data.enabled;
      current.textContent=data.error||(!data.enabled?'监测已暂停。':`当前程序：${data.current?.app||'unknown'} · 系统闲置 ${Math.floor(data.current?.idle_seconds||0)} 秒`);
      today.replaceChildren();
      for(const row of (data.today||[]).slice(0,12)){
        const line=document.createElement('p');line.textContent=`${row.app}：${Math.round(row.foreground_seconds/60)} 分钟（其中闲置 ${Math.round(row.idle_seconds/60)} 分钟）`;today.append(line);
      }
    }catch(e){current.textContent=e.message;}finally{loading=false;}
  }
  enabled.addEventListener('change',async()=>{enabled.disabled=true;try{await api('/api/activity/settings',{method:'POST',body:JSON.stringify({enabled:enabled.checked})});}catch(e){current.textContent=e.message;}finally{enabled.disabled=false;await refresh();}});
  async function speechStatus(){try{const data=await api('/api/speech/status');voiceStatus.textContent=data.last_error||(data.free_valid?`Fish免费型号已确认，期限至${data.free_until}；${data.account_verified?'本账号已验证成功。':'首次生成时验证账号。'}`:'免费期限需重新核实，已暂停。');}catch(e){voiceStatus.textContent=e.message;}}
  section.querySelector('#fish-retry').addEventListener('click',async()=>{
    const button=section.querySelector('#fish-retry');button.disabled=true;
    try{await api('/api/speech/retry',{method:'POST',body:'{}'});await api('/api/speech',{method:'POST',body:JSON.stringify({text:'你好，我在这里。',trigger:'manual'})});}catch(e){voiceStatus.textContent=e.message;}finally{button.disabled=false;await speechStatus();}
  });
  const idle=section.querySelector('#fish-idle');idle.checked=localStorage.getItem('xy.fish-idle')!=='off';
  const language=section.querySelector('#speech-language'),progress=section.querySelector('#speech-progress'),preview=section.querySelector('#speech-preview'),spokenText=section.querySelector('#speech-text');
  try{const saved=localStorage.getItem('xy.speech-language');if(Array.from(language.options).some(o=>o.value===saved))language.value=saved;}catch{}
  language.addEventListener('change',()=>{stop();try{localStorage.setItem('xy.speech-language',language.value);}catch{}preview.hidden=true;progress.textContent='';});
  idle.addEventListener('change',()=>localStorage.setItem('xy.fish-idle',idle.checked?'on':'off'));
  section.addEventListener('toggle',()=>{if(section.open){refresh();speechStatus();}});
  setInterval(()=>{if(section.open&&!document.hidden)refresh();},5000);
  let active=null;
  function stop(){
    if(!active)return;
    const old=active;active=null;old.controller.abort();old.audio?.pause();
    if(old.button){old.button.textContent='▷ 生成语音';old.button.setAttribute('aria-pressed','false');}
    const button=document.querySelector('#speech-stop');if(button)button.hidden=true;
    if(old.music)window.XYMusic?.setDucked(false);
    progress.textContent='已停止。';
  }
  async function speak(text,button,trigger='manual'){
    text=text.replaceAll('*','').replace(/(?<![A-Za-z0-9_])xy(?![A-Za-z0-9_])/gi,'叉歪');
    if(!text.trim())return;
    const target=language.value;
    if(active?.text===text&&active.language===target){stop();return;}
    stop();const item={text,language:target,button,controller:new AbortController()};active=item;
    preview.hidden=true;progress.textContent=target==='auto'?'正在生成语音…':`正在本机翻译为${language.selectedOptions[0].textContent}并生成语音…`;
    if(button){button.textContent='■ 停止生成';button.setAttribute('aria-pressed','true');}
    const globalStop=document.querySelector('#speech-stop');if(globalStop)globalStop.hidden=false;
    try{
      const result=await api('/api/speech',{method:'POST',signal:item.controller.signal,body:JSON.stringify({text:text.slice(0,600),trigger,language:target})});
      if(active!==item)return;if(!result.url){stop();progress.textContent=result.skipped==='cooldown'?'自动语音冷却中。':'本次未生成语音。';return;}
      spokenText.textContent=result.translated_text||'';preview.hidden=!spokenText.textContent;
      progress.textContent=(result.cached?'已读取本机语音缓存。':target==='auto'?'语音已生成。':'本机翻译及语音生成完成。');
      item.audio=new Audio(result.url);
      const music=document.querySelector('#music-audio');
      if(music&&window.XYMusic){item.music=music;window.XYMusic.setDucked(true);}
      item.audio.onended=()=>{if(active===item)stop();};item.audio.onerror=()=>{if(active===item){voiceStatus.textContent='音频播放失败，可点击生成语音重试。';stop();}};
      if(button)button.textContent='■ 停止语音';
      await item.audio.play();
    }catch(e){if(active===item){stop();if(e.name!=='AbortError'){progress.textContent=e.name==='NotAllowedError'?'浏览器暂未允许自动播放，点击对话中的生成语音即可。':e.message;voiceStatus.textContent=progress.textContent;}}}
  }
  window.XYSpeech={speak,stop};
  window.addEventListener('xy:companion-reply',event=>{if(idle.checked&&event.detail?.text&&!active)speak(event.detail.text,null,event.detail.trigger==='idle'?'idle':'manual');});
  window.addEventListener('beforeunload',stop);
})();
