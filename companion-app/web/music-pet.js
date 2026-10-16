'use strict';
(() => {
  const canvas=document.querySelector('#pet-canvas'),audio=document.querySelector('#music-audio');
  if(!canvas||!audio)return;
  const bubble=document.createElement('aside');bubble.className='pet-music';bubble.hidden=true;bubble.setAttribute('aria-label','小祥音乐播放器');
  const summary=document.createElement('button');summary.type='button';summary.className='pet-music-summary';summary.setAttribute('aria-expanded','false');
  const panel=document.createElement('div');panel.id='pet-music-controls';panel.className='pet-music-controls';panel.hidden=true;summary.setAttribute('aria-controls',panel.id);
  const row=document.createElement('div');row.className='pet-music-buttons';
  function button(text,action){const b=document.createElement('button');b.type='button';b.textContent=text;b.addEventListener('click',action);row.append(b);return b;}
  button('上一首',()=>window.XYMusic?.previous());const toggle=button('暂停',()=>window.XYMusic?.toggle());button('下一首',()=>window.XYMusic?.next());
  const volumeLabel=document.createElement('label');volumeLabel.textContent='音量';const volume=document.createElement('input');volume.type='range';volume.min='0';volume.max='1';volume.step='0.05';volume.value=String(audio.volume);volume.setAttribute('aria-label','音乐音量');volume.addEventListener('input',()=>{audio.volume=Number(volume.value);audio.muted=false;});audio.addEventListener('volumechange',()=>{volume.value=audio.muted?'0':String(audio.volume);});volumeLabel.append(volume);
  const choose=document.createElement('button');choose.type='button';choose.className='pet-music-choose';choose.textContent='选歌 / 搜索';choose.addEventListener('click',()=>{document.querySelector('#workspace-open')?.click();document.querySelector('#music-search')?.focus();});panel.append(row,volumeLabel,choose);bubble.append(summary,panel);document.body.append(bubble);
  summary.addEventListener('click',()=>{if(!panel.hidden){choose.click();panel.hidden=true;}else panel.hidden=false;summary.setAttribute('aria-expanded',String(!panel.hidden));position();});
  let timer=0;
  function position(){if(bubble.hidden)return;const r=canvas.getBoundingClientRect();if(!r.width||!r.height){bubble.style.visibility='hidden';return;}bubble.style.visibility='visible';const width=bubble.offsetWidth,height=bubble.offsetHeight;const preferred=r.right-width*.3;const left=preferred+width>innerWidth-8?r.left-width+20:preferred;bubble.style.left=Math.max(8,Math.min(left,innerWidth-width-8))+'px';bubble.style.top=Math.max(8,Math.min(r.top+r.height*.18,innerHeight-height-8))+'px';}
  function follow(){position();timer=setTimeout(follow,120);}
  window.addEventListener('xy:music-state',event=>{const s=event.detail||{};summary.textContent=(s.playing?'♫ ':'Ⅱ ')+s.title+(s.artist?' — '+s.artist:'');summary.title=summary.textContent;toggle.textContent=s.playing?'暂停':'播放';bubble.hidden=!s.title;clearTimeout(timer);if(!bubble.hidden)follow();});
  window.addEventListener('pagehide',()=>clearTimeout(timer));window.XYMusic?.state();
})();
