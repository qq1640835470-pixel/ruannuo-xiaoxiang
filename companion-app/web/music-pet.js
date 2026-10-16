'use strict';
(() => {
  const canvas=document.querySelector('#pet-canvas'),audio=document.querySelector('#music-audio');
  if(!canvas||!audio)return;
  let preference={visible:true,hidePaused:false};
  try{const saved=JSON.parse(localStorage.getItem('xy.music-bubble')||'{}');preference.visible=saved.visible!==false;preference.hidePaused=saved.hidePaused===true;}catch{}
  const bubble=document.createElement('aside');bubble.className='pet-music';bubble.hidden=true;bubble.setAttribute('aria-label','小祥音乐播放器');
  const summary=document.createElement('button');summary.type='button';summary.className='pet-music-summary';summary.setAttribute('aria-expanded','false');
  const close=document.createElement('button');close.type='button';close.className='pet-music-close';close.textContent='×';close.setAttribute('aria-label','关闭音乐气泡，可在音乐页重新打开');
  const panel=document.createElement('div');panel.id='pet-music-controls';panel.className='pet-music-controls';panel.hidden=true;summary.setAttribute('aria-controls',panel.id);
  const row=document.createElement('div');row.className='pet-music-buttons';
  function button(text,action){const b=document.createElement('button');b.type='button';b.textContent=text;b.addEventListener('click',action);row.append(b);return b;}
  button('上一首',()=>window.XYMusic?.previous());const toggle=button('暂停',()=>window.XYMusic?.toggle());button('下一首',()=>window.XYMusic?.next());
  const volumeLabel=document.createElement('label');volumeLabel.textContent='音量';const volume=document.createElement('input');volume.type='range';volume.min='0';volume.max='1';volume.step='0.05';volume.value=String(audio.volume);volume.setAttribute('aria-label','音乐音量');volume.addEventListener('input',()=>{audio.volume=Number(volume.value);audio.muted=false;});audio.addEventListener('volumechange',()=>{volume.value=audio.muted?'0':String(audio.volume);});volumeLabel.append(volume);
  const choose=document.createElement('button');choose.type='button';choose.className='pet-music-choose';choose.textContent='选歌 / 搜索';choose.addEventListener('click',()=>window.XYWorkspace?.open('music'));panel.append(row,volumeLabel,choose);bubble.append(summary,panel,close);document.body.append(bubble);
  summary.addEventListener('click',()=>{panel.hidden=!panel.hidden;summary.setAttribute('aria-expanded',String(!panel.hidden));position();});
  const preferences=document.createElement('div');preferences.className='music-bubble-preferences';
  function checkbox(text,key){const label=document.createElement('label'),input=document.createElement('input');input.type='checkbox';input.checked=preference[key];input.addEventListener('change',()=>{preference[key]=input.checked;save();});label.append(input,document.createTextNode(text));preferences.append(label);return input;}
  const visible=checkbox('显示宠物音乐气泡','visible');checkbox('暂停时隐藏气泡','hidePaused');document.querySelector('#workspace-music')?.append(preferences);
  close.addEventListener('click',()=>{preference.visible=false;visible.checked=false;save();});
  let timer=0,state={};
  function save(){try{localStorage.setItem('xy.music-bubble',JSON.stringify(preference));}catch{}update();}
  function overlap(a,b){return a.left<b.right+8&&a.right>b.left-8&&a.top<b.bottom+8&&a.bottom>b.top-8;}
  function position(){
    if(bubble.hidden)return;
    const r=canvas.getBoundingClientRect();if(!r.width||!r.height){bubble.style.visibility='hidden';return;}
    bubble.style.visibility='visible';
    const width=bubble.offsetWidth,height=bubble.offsetHeight,pad=8;
    const obstacles=Array.from(document.querySelectorAll('#pet-bubble:not(.is-resting), .pet-controls, .pet-mode-panel[open], .pet-menu, #settings-drawer:not([hidden])')).filter(node=>!node.hidden&&node.getClientRects().length).map(node=>node.getBoundingClientRect());
    const candidates=[[r.right+pad,r.top],[r.left-width-pad,r.top],[r.left,r.bottom+pad],[r.left,r.top-height-pad],[pad,pad],[innerWidth-width-pad,pad],[pad,innerHeight-height-pad],[innerWidth-width-pad,innerHeight-height-pad]];
    for(const rect of obstacles)candidates.push([rect.right+pad,r.top],[rect.left-width-pad,r.top],[r.left,rect.bottom+pad],[r.left,rect.top-height-pad]);
    let best=null,bestScore=Infinity;
    for(const [x,y] of candidates){const left=Math.max(pad,Math.min(x,innerWidth-width-pad)),top=Math.max(pad,Math.min(y,innerHeight-height-pad));const candidate={left,top,right:left+width,bottom:top+height};let score=Math.abs(left-r.right)+Math.abs(top-r.top);for(const rect of obstacles)if(overlap(candidate,rect))score+=100000+Math.max(0,Math.min(candidate.right,rect.right)-Math.max(left,rect.left))*Math.max(0,Math.min(candidate.bottom,rect.bottom)-Math.max(top,rect.top));if(score<bestScore){best=candidate;bestScore=score;}}
    if(best){bubble.style.left=best.left+'px';bubble.style.top=best.top+'px';}
  }
  function follow(){position();timer=setTimeout(follow,120);}
  function update(){const s=state;summary.textContent=(s.playing?'♫ ':'已暂停 · ')+(s.title||'')+(s.artist?' — '+s.artist:'');summary.title=summary.textContent;toggle.textContent=s.playing?'暂停':'播放';bubble.hidden=!s.title||!preference.visible||(preference.hidePaused&&!s.playing);clearTimeout(timer);if(!bubble.hidden)follow();}
  window.addEventListener('xy:music-state',event=>{state=event.detail||{};update();});
  window.addEventListener('resize',position);window.addEventListener('pagehide',()=>clearTimeout(timer));window.XYMusic?.state();
})();
