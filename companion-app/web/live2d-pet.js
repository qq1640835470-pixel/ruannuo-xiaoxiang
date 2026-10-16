"use strict";
/* Local Cubism rendering only. Imported card scripts and arbitrary URLs are never evaluated. */
(() => {
  const root=document.querySelector('#sakiko-companion'),stage=root?.querySelector('.pet-stage');
  if(!root||!stage)return;
  const panel=document.createElement('section');panel.id='pet-mode-panel';panel.className='pet-mode-panel';panel.hidden=true;panel.setAttribute('role','dialog');panel.setAttribute('aria-label','形象与小动作');
  panel.innerHTML='<div class="pet-mode-heading"><strong>形象与小动作</strong><button id="pet-menu-close" type="button" aria-label="关闭形象菜单">×</button></div><label>形象<select id="pet-renderer"><option value="chibi">Q版小祥 · 精灵动画</option><option value="live2d">原比例小祥 · Live2D</option></select></label><label class="pet-check"><input id="pet-auto" type="checkbox" checked> 自动表情与小动作</label><div id="pet-chibi-options"><label>小动作<select id="pet-activity"><option value="auto">自动 · 音乐与明确对话</option><option value="idle">安静站着</option><option value="lunch">小祥吃午餐</option><option value="sleepy">小祥困了</option><option value="music">戴耳机听歌</option><option value="happy">开心</option><option value="surprised">惊讶</option></select></label></div><div id="pet-live2d-options" hidden><label>衣装<select id="pet-costume"></select></label><label>尺寸 <output id="pet-size-value">100%</output><input id="pet-size" type="range" min="75" max="140" step="5" value="100"></label><label>表情<select id="pet-expression"></select></label><label>动作<select id="pet-motion"></select></label><button id="pet-play-motion" type="button">播放动作</button><button id="pet-reset-expression" type="button">恢复自动表情</button><p>可拖动、站在边缘、裁切探头。坐下与挂住目前仅Q版有专用画面。</p></div><label>鼠标指针<select id="pet-cursor"><option value="xiaoxiang">小小祥头像</option><option value="system">系统指针</option></select></label><p class="pet-mode-status" id="pet-mode-status" role="status">右键小祥，或聚焦后按 Shift+F10 打开。衣装由你选择。</p>';
  document.body.append(panel);root.dataset.renderer='chibi';
  const find=id=>panel.querySelector('#'+id),mode=find('pet-renderer'),costume=find('pet-costume'),expression=find('pet-expression'),motion=find('pet-motion'),status=find('pet-mode-status'),auto=find('pet-auto'),sizeInput=find('pet-size'),cursor=find('pet-cursor');
  const hitCanvas=root.querySelector('#pet-canvas');hitCanvas.setAttribute('aria-haspopup','dialog');hitCanvas.setAttribute('aria-controls',panel.id);hitCanvas.setAttribute('aria-expanded','false');hitCanvas.setAttribute('aria-keyshortcuts','Shift+F10');hitCanvas.title='右键小祥打开形象与小动作；键盘可按 Shift+F10';
  document.querySelector('#pet-hint').textContent+=' 右键小祥或聚焦后按Shift+F10打开形象与小动作。';
  const saved={};for(const [key,fallback] of Object.entries({auto:'true',size:'100',cursor:'xiaoxiang',renderer:'chibi',costume:''})){try{saved[key]=localStorage.getItem('xy.pet.'+key)||fallback;}catch{saved[key]=fallback;}}
  function remember(key,value){try{localStorage.setItem('xy.pet.'+key,String(value));}catch{}}
  function closeMenu(){panel.hidden=true;hitCanvas.setAttribute('aria-expanded','false');}
  function menuAt(x,y){panel.hidden=false;hitCanvas.setAttribute('aria-expanded','true');panel.style.left=Math.max(8,Math.min(x,innerWidth-panel.offsetWidth-8))+'px';panel.style.top=Math.max(8,Math.min(y,innerHeight-panel.offsetHeight-8))+'px';mode.focus();}
  hitCanvas.addEventListener('contextmenu',event=>{event.preventDefault();menuAt(event.clientX,event.clientY);});
  hitCanvas.addEventListener('keydown',event=>{if(event.key==='ContextMenu'||event.key==='F10'&&event.shiftKey){event.preventDefault();const r=hitCanvas.getBoundingClientRect();menuAt(r.right,r.top);}});
  panel.addEventListener('keydown',event=>{if(event.key==='Escape'){event.preventDefault();event.stopPropagation();closeMenu();hitCanvas.focus();}});
  find('pet-menu-close').addEventListener('click',()=>{closeMenu();hitCanvas.focus();});
  document.addEventListener('pointerdown',event=>{if(!panel.hidden&&!panel.contains(event.target)&&event.target!==hitCanvas)closeMenu();});
  window.addEventListener('resize',()=>{if(!panel.hidden){const r=panel.getBoundingClientRect();menuAt(r.x,r.y);}});
  auto.checked=saved.auto!=='false';sizeInput.value=String(Math.max(75,Math.min(140,Number(saved.size)||100)));cursor.value=saved.cursor==='system'?'system':'xiaoxiang';
  const cursorStyle=document.createElement('link');cursorStyle.rel='stylesheet';cursorStyle.href='/pet-cursor.css';document.head.append(cursorStyle);
  function applyCursor(){document.documentElement.dataset.petCursor=cursor.value;remember('cursor',cursor.value);}cursor.addEventListener('change',applyCursor);applyCursor();
  function applySize(){root.style.setProperty('--live2d-scale',Number(sizeInput.value)/100);find('pet-size-value').textContent=sizeInput.value+'%';remember('size',sizeInput.value);window.dispatchEvent(new CustomEvent('xy:pet-layout',{detail:{renderer:root.dataset.renderer}}));}sizeInput.addEventListener('input',applySize);applySize();
  const surface=document.createElement('canvas');surface.className='pet-live2d-canvas';surface.hidden=true;surface.setAttribute('aria-hidden','true');stage.append(surface);
  let manifest=null,app=null,model=null,loading=null,generation=0,modeActive=false,modelInfo=null,visibleBounds=null,manualOverride=false,lastAutoMotion=-Infinity,musicPlaying=false;
  const reduced=window.matchMedia('(prefers-reduced-motion: reduce)');
  function syncPlayback(){if(!app)return;if(modeActive&&!document.hidden&&root.dataset.quiet!=='true'&&root.dataset.motionPreference!=='quiet'&&!reduced.matches)app.start();else app.stop();}
  const names={angry:'生气',bsmile:'灿笑',cry:'含泪',idle:'平静',kime:'坚定',pale:'苍白',sad:'难过',serious:'认真',shadow:'阴影',shy:'害羞',smile:'微笑',surprised:'惊讶',upset:'不安',bye:'挥别',check:'查看',denial:'摇头',look:'张望',maskoff:'摘面具',nervous:'紧张',nod:'点头',question:'疑问',sadness:'失落',shame:'羞涩',stretch:'伸展',think:'思考',tear:'眼泪'};
  function label(value){const raw=value.replace(/^(exp_|mtn_|misc_)/,'').replace(/\.(exp|motion)3\.json$/,'');const match=raw.match(/^([a-z]+)(\d+)?(?:_([CLR]))?$/);if(!match)return raw;return (names[match[1]]||match[1])+(match[2]?' '+match[2]:'')+({C:' · 正面',L:' · 左倾',R:' · 右倾'}[match[3]]||'');}
  function options(select,values){select.replaceChildren(...values.map(value=>{const option=document.createElement('option');option.value=value;option.textContent=label(value);return option;}));}
  function script(url){return new Promise((resolve,reject)=>{const tag=document.createElement('script');tag.src=url;tag.onload=resolve;tag.onerror=()=>{tag.remove();reject(new Error('本机动画依赖未能读取'));};document.head.append(tag);});}
  async function dependencies(){
    if(!loading)loading=(async()=>{await script('/assets/pet/vendor/pixi.min.js');await script('/assets/pet/vendor/live2dcubismcore.min.js');await script('/assets/pet/vendor/cubism4.min.js');})();
    try{await loading;}catch(error){loading=null;throw error;}
  }
  async function catalog(){
    if(manifest)return manifest;
    const response=await fetch('/assets/pet/live2d/manifest.json');if(!response.ok)throw new Error('本机衣装目录未能读取');
    const data=await response.json();
    if(!Array.isArray(data.models)||data.models.some(item=>!/^\/assets\/pet\/live2d\/010_[a-z0-9_]+\/010_[a-z0-9_]+\.model3\.json$/.test(item.url)))throw new Error('模型路径无效');
    manifest=data;costume.replaceChildren(...data.models.map(info=>{const option=document.createElement('option');option.value=info.id;option.textContent=info.label;return option;}));if(data.models.some(info=>info.id===saved.costume))costume.value=saved.costume;return data;
  }
  function modelBounds(){
    const internal=model.internalModel,core=internal.coreModel;let left=Infinity,right=-Infinity,top=Infinity,bottom=-Infinity;
    for(let i=0;i<internal.getDrawableIDs().length;i++){
      if(core.getDrawableOpacity(i)<.01)continue;
      const bounds=internal.getDrawableBounds(i);left=Math.min(left,bounds.x);right=Math.max(right,bounds.x+bounds.width);top=Math.min(top,bounds.y);bottom=Math.max(bottom,bounds.y+bounds.height);
    }
    const transform=internal.localTransform;
    return {x:left*transform.a+transform.tx,y:top*transform.d+transform.ty,width:(right-left)*transform.a,height:(bottom-top)*transform.d};
  }
  function fit(){
    if(!model||!app)return;
    const r=stage.getBoundingClientRect();app.renderer.resize(r.width,r.height);const b=visibleBounds;
    const scale=Math.min(r.width/(b.width*1.10),r.height/(b.height*1.08));model.anchor.set(0);model.scale.set(scale);model.pivot.set(b.x+b.width/2,b.y+b.height);model.position.set(r.width/2,r.height*.97);app.render();
    root.dataset.live2dVisibleHeight=String(Math.round(b.height*scale));root.dataset.live2dVisibleWidth=String(Math.round(b.width*scale));
    window.dispatchEvent(new CustomEvent('xy:pet-layout',{detail:{renderer:'live2d',stage:r.toJSON()}}));
  }
  function animate(value){if(!model||!modelInfo)return;const selected=modelInfo.motions.find(name=>name===value);if(selected)Promise.resolve(model.motion(selected,0,3)).catch(()=>{status.textContent='这个动作未能播放，请换一个试试。';});}
  function expressionValue(value){if(model&&modelInfo?.expressions.includes(value))model.expression(value).then(ok=>{if(ok)root.dataset.live2dExpression=value;}).catch(()=>{status.textContent='这个表情未能读取。';});}
  async function loadModel(){
    const request=++generation,desiredExpression=expression.value,desiredMotion=motion.value;status.textContent='正在读取本机模型…';
    try{
      await catalog();await dependencies();
      const info=manifest.models.find(item=>item.id===costume.value)||manifest.models[0];
      const next=await window.PIXI.live2d.Live2DModel.from(info.url,{autoInteract:false,autoUpdate:false,motionPreload:window.PIXI.live2d.MotionPreloadStrategy?.NONE||'NONE'});
      if(request!==generation||!modeActive){next.destroy({children:true,texture:true,baseTexture:true});return;}
      if(!app){const r=stage.getBoundingClientRect();app=new window.PIXI.Application({view:surface,width:r.width,height:r.height,resolution:Math.min(devicePixelRatio||1,2),autoDensity:true,backgroundAlpha:0,antialias:true});app.ticker.maxFPS=30;app.ticker.add(()=>model?.update(app.ticker.deltaMS));}
      const previous=model;model=next;modelInfo=info;visibleBounds=modelBounds();app.stage.addChild(model);if(previous){app.stage.removeChild(previous);previous.destroy({children:true,texture:true,baseTexture:true});}
      options(expression,info.expressions);options(motion,info.motions);expression.value=manualOverride&&info.expressions.includes(desiredExpression)?desiredExpression:info.expressions.find(name=>name==='exp_idle01')||info.expressions[0];motion.value=manualOverride&&info.motions.includes(desiredMotion)?desiredMotion:info.motions.find(name=>name==='mtn_idle01_C')||info.motions[0];
      root.dataset.renderer='live2d';fit();expressionValue(expression.value);animate(motion.value);surface.hidden=false;root.dataset.engine='cubism3-local';root.dataset.live2dReady='true';root.dataset.live2dCostume=info.id;syncPlayback();if(!manualOverride)automatic('idle');window.dispatchEvent(new CustomEvent('xy:pet-renderer',{detail:{renderer:'live2d'}}));
      status.textContent=info.label+' · '+info.expressions.length+'表情 / '+info.motions.length+'动作';
    }catch(error){if(request!==generation)return;modeActive=false;mode.value='chibi';root.dataset.renderer='chibi';root.dataset.engine='sprite2d';root.dataset.live2dReady='false';surface.hidden=true;app?.stop();find('pet-chibi-options').hidden=false;find('pet-live2d-options').hidden=true;status.textContent='原比例暂不可用：'+error.message+'。Q版可继续使用。';}
  }
  function switchMode(){
    modeActive=mode.value==='live2d';remember('renderer',mode.value);find('pet-live2d-options').hidden=!modeActive;find('pet-chibi-options').hidden=modeActive;
    if(modeActive)loadModel();else{generation++;surface.hidden=true;root.dataset.renderer='chibi';root.dataset.engine='sprite2d';app?.stop();status.textContent='Q版精灵动画 · 可拖动、摸头和选择小动作。';window.dispatchEvent(new CustomEvent('xy:pet-renderer',{detail:{renderer:'chibi'}}));}
  }
  function syncAuto(){manualOverride=false;remember('auto',auto.checked);root.dataset.petAuto=String(auto.checked);window.dispatchEvent(new CustomEvent('xy:pet-auto',{detail:{enabled:auto.checked}}));if(auto.checked)automatic('idle');}
  function automatic(state){
    if(!modeActive||!auto.checked||manualOverride||!modelInfo||root.dataset.quiet==='true')return;
    if(state==='idle'&&musicPlaying)state='music';
    const exp={happy:'exp_bsmile01',surprised:'exp_surprised01',thinking:'exp_serious01',error:'exp_sad01',music:'exp_smile01',shy:'exp_shy01',pout:'exp_angry01'}[state]||((new Date().getHours()>=22||new Date().getHours()<6)?'exp_idle02':'exp_idle01');
    expressionValue(exp);root.dataset.autoExpression=exp;
    const now=performance.now();if(now-lastAutoMotion<20000||reduced.matches||root.dataset.motionPreference==='quiet')return;
    lastAutoMotion=now;animate({thinking:'mtn_thinking01_C',reply:'mtn_nod01_C',music:'mtn_nod01_C',surprised:'mtn_surprised01_C',happy:'mtn_smile01_C'}[state]||'mtn_idle01_C');
  }
  mode.addEventListener('change',switchMode);auto.addEventListener('change',syncAuto);
  costume.addEventListener('change',()=>{remember('costume',costume.value);loadModel();});
  expression.addEventListener('change',()=>{manualOverride=true;expressionValue(expression.value);status.textContent='已保留手动表情。点击恢复自动表情可重新跟随。';});
  find('pet-play-motion').addEventListener('click',()=>{manualOverride=true;animate(motion.value);});
  find('pet-reset-expression').addEventListener('click',()=>{auto.checked=true;syncAuto();status.textContent='已恢复自动表情；衣装仍由你选择。';});
  find('pet-activity').addEventListener('change',event=>window.dispatchEvent(new CustomEvent('xy:pet-activity',{detail:{activity:event.target.value}})));
  document.addEventListener('pointermove',event=>{if(modeActive&&model){const r=stage.getBoundingClientRect();model.focus(event.clientX-r.left,event.clientY-r.top);}}, {passive:true});
  window.addEventListener('xy:companion',event=>{const d=event.detail||{},metadata=d.metadata||d.context||{};automatic(metadata.emotion||d.emotion||d.type);});
  window.addEventListener('xy:pet-reaction',event=>automatic(event.detail?.mood));
  window.addEventListener('xy:music-state',event=>{musicPlaying=event.detail?.playing===true;automatic(musicPlaying?'music':'idle');});
  window.addEventListener('xy:time',()=>automatic('idle'));
  window.addEventListener('xy:pet-quiet',syncPlayback);window.addEventListener('xy:local-preferences',syncPlayback);reduced.addEventListener('change',syncPlayback);
  document.addEventListener('visibilitychange',syncPlayback);
  new ResizeObserver(fit).observe(stage);syncAuto();if(saved.renderer==='live2d'){mode.value='live2d';switchMode();}
})();
