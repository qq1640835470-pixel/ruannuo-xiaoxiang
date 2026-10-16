"use strict";
/* Local Cubism rendering only. Imported card scripts and arbitrary URLs are never evaluated. */
(() => {
  const root=document.querySelector('#sakiko-companion'),stage=root?.querySelector('.pet-stage');
  if(!root||!stage)return;
  const panel=document.createElement('details');panel.className='pet-mode-panel';
  panel.innerHTML='<summary>形象与小动作 ▾</summary><label>形象<select id="pet-renderer"><option value="chibi">Q版小祥 · 精灵动画</option><option value="live2d">原比例小祥 · Live2D</option></select></label><div id="pet-chibi-options"><label>小动作<select id="pet-activity"><option value="auto">随时间与播放自动</option><option value="idle">安静站着</option><option value="lunch">小祥吃午餐</option><option value="sleepy">小祥困了</option><option value="music">戴耳机听歌</option><option value="happy">开心</option><option value="surprised">惊讶</option></select></label></div><div id="pet-live2d-options" hidden><label>衣装<select id="pet-costume"></select></label><label>表情<select id="pet-expression"></select></label><label>动作<select id="pet-motion"></select></label><button id="pet-play-motion" type="button">播放动作</button><button id="pet-reset-expression" type="button">恢复表情</button></div><p class="pet-mode-status" id="pet-mode-status" role="status">默认Q版；原比例使用本机模型。</p>';
  root.append(panel);root.dataset.renderer='chibi';
  const find=id=>panel.querySelector('#'+id),mode=find('pet-renderer'),costume=find('pet-costume'),expression=find('pet-expression'),motion=find('pet-motion'),status=find('pet-mode-status');
  const surface=document.createElement('canvas');surface.className='pet-live2d-canvas';surface.hidden=true;surface.setAttribute('aria-hidden','true');stage.append(surface);
  let manifest=null,app=null,model=null,loading=null,generation=0,modeActive=false,modelInfo=null;
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
    manifest=data;costume.replaceChildren(...data.models.map(info=>{const option=document.createElement('option');option.value=info.id;option.textContent=info.label;return option;}));return data;
  }
  function fit(){if(!model||!app)return;const r=stage.getBoundingClientRect();app.renderer.resize(r.width,r.height);const original=model.internalModel;const width=original.width,height=original.height;model.scale.set(Math.min(r.width/width,r.height/height)*.98);model.anchor.set(.5,1);model.position.set(r.width/2,r.height);app.render();}
  function animate(value){if(!model||!modelInfo)return;const selected=modelInfo.motions.find(name=>name===value);if(selected)Promise.resolve(model.motion(selected,0,3)).catch(()=>{status.textContent='这个动作未能播放，请换一个试试。';});}
  function expressionValue(value){if(model&&modelInfo?.expressions.includes(value))model.expression(value).catch(()=>{status.textContent='这个表情未能读取。';});}
  async function loadModel(){
    const request=++generation;status.textContent='正在读取本机模型…';
    try{
      await catalog();await dependencies();
      const info=manifest.models.find(item=>item.id===costume.value)||manifest.models[0];
      const next=await window.PIXI.live2d.Live2DModel.from(info.url,{autoInteract:false,autoUpdate:false,motionPreload:window.PIXI.live2d.MotionPreloadStrategy?.NONE||'NONE'});
      if(request!==generation||!modeActive){next.destroy({children:true,texture:true,baseTexture:true});return;}
      if(!app){const r=stage.getBoundingClientRect();app=new window.PIXI.Application({view:surface,width:r.width,height:r.height,resolution:Math.min(devicePixelRatio||1,2),autoDensity:true,backgroundAlpha:0,antialias:true});app.ticker.maxFPS=30;app.ticker.add(()=>model?.update(app.ticker.deltaMS));}
      const previous=model;model=next;modelInfo=info;app.stage.addChild(model);if(previous){app.stage.removeChild(previous);previous.destroy({children:true,texture:true,baseTexture:true});}
      options(expression,info.expressions);options(motion,info.motions);expression.value=info.expressions.find(name=>name==='exp_idle01')||info.expressions[0];motion.value=info.motions.find(name=>name==='mtn_idle01_C')||info.motions[0];
      fit();expressionValue(expression.value);animate(motion.value);surface.hidden=false;root.dataset.renderer='live2d';root.dataset.engine='cubism3-local';root.dataset.live2dReady='true';root.dataset.live2dCostume=info.id;syncPlayback();
      status.textContent=info.label+' · '+info.expressions.length+'表情 / '+info.motions.length+'动作';
    }catch(error){if(request!==generation)return;modeActive=false;mode.value='chibi';root.dataset.renderer='chibi';root.dataset.engine='sprite2d';root.dataset.live2dReady='false';surface.hidden=true;app?.stop();find('pet-chibi-options').hidden=false;find('pet-live2d-options').hidden=true;status.textContent='原比例暂不可用：'+error.message+'。Q版可继续使用。';}
  }
  mode.addEventListener('change',()=>{modeActive=mode.value==='live2d';find('pet-live2d-options').hidden=!modeActive;find('pet-chibi-options').hidden=modeActive;if(modeActive)loadModel();else{generation++;surface.hidden=true;root.dataset.renderer='chibi';root.dataset.engine='sprite2d';app?.stop();status.textContent='Q版精灵动画 · 可拖动、摸头和选择小动作。';}});
  costume.addEventListener('change',loadModel);expression.addEventListener('change',()=>expressionValue(expression.value));
  find('pet-play-motion').addEventListener('click',()=>animate(motion.value));find('pet-reset-expression').addEventListener('click',()=>{expression.value='exp_idle01';expressionValue(expression.value);});
  find('pet-activity').addEventListener('change',event=>window.dispatchEvent(new CustomEvent('xy:pet-activity',{detail:{activity:event.target.value}})));
  document.addEventListener('pointermove',event=>{if(modeActive&&model){const r=stage.getBoundingClientRect();model.focus(event.clientX-r.left,event.clientY-r.top);}}, {passive:true});
  window.addEventListener('xy:companion',event=>{if(!modeActive)return;const value=event.detail?.type;if(value==='thinking')animate('mtn_think01_C');if(value==='reply')animate('mtn_nod01_C');});
  window.addEventListener('xy:pet-reaction',event=>{if(!modeActive)return;expressionValue({shy:'exp_shy01',pout:'exp_angry01',calm:'exp_idle01'}[event.detail?.mood]||'exp_idle01');});
  window.addEventListener('xy:pet-quiet',syncPlayback);window.addEventListener('xy:local-preferences',syncPlayback);reduced.addEventListener('change',syncPlayback);
  document.addEventListener('visibilitychange',syncPlayback);
  new ResizeObserver(fit).observe(stage);
})();
