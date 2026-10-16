"use strict";
/* Original local sprite companion. This renderer does not claim to load Cubism models. */
(() => {
  const root=document.querySelector("#sakiko-companion"),canvas=document.querySelector("#pet-canvas");
  if(!root||!canvas)return;
  const ctx=canvas.getContext("2d"),bubble=document.querySelector("#pet-bubble"),text=document.querySelector("#pet-text");
  const kind=document.querySelector("#pet-bubble-kind"),quietButton=document.querySelector("#pet-quiet");
  const reduce=window.matchMedia("(prefers-reduced-motion: reduce)");
  const M=window.XYPetMotion;
  const lines={
    greeting:["你来了。那么，先坐一会儿吧。","今天想聊些什么？我在听。","不用急着说出结论，先说你真正想做的事。"],
    pat:["……头发会乱的。稍微一下就好。","怎么忽然……我可没有在等你摸头。","嗯……你的手，倒是很温柔。"],
    repeat:["好、好啦，头发要乱了。先让我自己待一小会儿。","还摸呀……哼，先让我安静一小会儿。"],
    dizzy:["呜……有点晕。停一停，让我缓缓。","别晃啦……我要抓不稳了。"],
    lift:["欸、等一下……别拎着衣服晃来晃去。","领子会皱的。你要带我去哪儿？"],
    sit:["这里倒是不错。就让我在这儿坐一会儿吧。","我坐在这里，你继续忙。"],
    hang:["……我抓稳了。你可别故意逗我。","这里有点高。不过，我还撑得住。"],
    peek:["……被你发现了吗？我只是看看。","嘘。我在这里，先不打扰你。"],
    land:["好了，站稳了。下次轻一点。","呼……总算落地了。"],
    home:["还是这里熟悉些。","嗯，我回来了。"],
    'no-room':["这里太挤了，换个宽敞些的位置吧。"],
    idle:["如果有一段喜欢的旋律，今天也会变得不一样吧。","想说话的时候，叫我就好。","一段合奏，不必由一个人撑起所有声音。","有些心意，放进旋律里反而更容易说出口。","就这样安静待一会儿，也很好。"],
    thinking:["让我想一想，先把事情理清。","嗯，我正在听，也在认真想。"],
    error:["这次没能顺利办好。我们先看清哪里出了问题。","稍等一下，这里还需要处理。"],
    quiet:["好。我会安静些。想找我时，点点我就好。"],
    welcomeBack:["嗯？我在。有什么想告诉我的？"]
  };
  let localMotion='normal';
  let quiet=false;try{quiet=localStorage.getItem("xy.pet.quiet")==="true";}catch{}
  let loaded=false,raf=0,lastFrame=0,blinkUntil=0,nextBlink=0,mood="calm",moodUntil=0;
  let lookX=0,lookY=0,targetX=0,targetY=0,pose="stand",poseBounds=[],poseLoaded=false,world=null;
  let bubbleTimer=0,idleTimer=0,moodTimer=0,busy=false,patState={times:[]},frameBounds=[],lastLine={};
  let activityChoice='auto',musicPlaying=false,activity='idle',sulkUntil=0;
  let transition=null,displayHead={x:180,y:110},patStarted=-10000,greetStarted=-10000,dizzyUntil=0,petRequest=false,petAI=true,petProvider='gemini',preparedDialogue=null;
  const logicalSize={width:360,height:440};
  const poseFrames=[];
  function syncResolution(){
    const rect=canvas.getBoundingClientRect(),ratio=window.devicePixelRatio||1;
    const width=Math.max(1,Math.round(rect.width*ratio)),height=Math.max(1,Math.round(rect.height*ratio));
    if(canvas.width!==width||canvas.height!==height){canvas.width=width;canvas.height=height;transition=null;root.dataset.transitioning="false";}
    root.dataset.pixelRatio=String(ratio);
  }
  function beginTransition(duration=260){
    if(!loaded||reduce.matches){transition=null;root.dataset.transitioning="false";return;}
    // Ease the body toward its new support point. A raster dissolve can retain
    // old eyes, hearts and earlier dissolves when a pat is followed by a grab.
    transition={started:performance.now(),duration,head:{...displayHead}};root.dataset.transitioning="true";
  }
  root.dataset.engine="sprite2d";
  const timeLines={
    '深夜':['夜里很安静。想说些什么，我都在听。','这个时间，旋律听起来也柔和了些。'],
    '清晨':['早安，xy。今天想先跟我聊些什么？','清晨好。要从一首喜欢的歌开始吗？'],
    '上午':['上午好。今天有什么新鲜事想告诉我？','早上的光线很适合这里的蓝色，对吧？'],
    '午间':['中午好。想轻松聊一会儿吗？','已经到午间了。有什么想分享的？'],
    '下午':['下午好，xy。想聊技术，还是聊音乐？','这个下午，我们慢慢把事情说清楚吧。'],
    '傍晚':['傍晚了，界面的蓝色也慢慢柔和下来了。','这个时间，很适合想起一首喜欢的歌。'],
    '夜晚':['晚上好。今天有什么想和我说的吗？','夜色里的蓝色也很好看。我在这儿陪你。']
  };
  const randomLine=key=>{const phase=window.XYDaylight?.phase(new Date().getHours()),casual=key==='greeting'||key==='idle';const bank=casual?(timeLines[phase]||lines[key]):lines[key];let n=Math.floor(Math.random()*bank.length);if(bank.length>1&&n===lastLine[key])n=(n+1)%bank.length;lastLine[key]=n;if(casual&&window.XYDialogue){preparedDialogue=window.XYDialogue.next(bank[n]);return preparedDialogue;}return bank[n];};
  const active=()=>!document.hidden&&root.getClientRects().length>0;
  function say(value,label="小祥 · 小声说",duration=11000){
    if(value!==preparedDialogue)window.XYDialogue?.remember(value);preparedDialogue=null;
    clearTimeout(bubbleTimer);text.textContent=value;kind.textContent=label;bubble.classList.remove("is-resting");
    world?.refreshBubble();
    bubbleTimer=setTimeout(()=>bubble.classList.add("is-resting"),duration);
  }
  function expression(value,duration=2400){clearTimeout(moodTimer);if(mood!==value)beginTransition(170);mood=value;moodUntil=performance.now()+duration;root.dataset.mood=value;window.dispatchEvent(new CustomEvent('xy:pet-reaction',{detail:{mood:value}}));draw(performance.now());start();moodTimer=setTimeout(()=>{if(mood!=="calm")beginTransition(180);mood="calm";draw(performance.now());start();},duration+20);}
  function setQuiet(value,announce=true){
    quiet=value;root.dataset.quiet=String(value);quietButton.setAttribute("aria-pressed",String(value));quietButton.textContent=value?"继续陪伴":"安静陪伴";window.dispatchEvent(new CustomEvent('xy:pet-quiet',{detail:{quiet:value}}));
    try{localStorage.setItem("xy.pet.quiet",String(value));}catch{}
    if(value){cancelAnimationFrame(raf);raf=0;transition=null;root.dataset.transitioning="false";targetX=targetY=lookX=lookY=0;draw(performance.now());}
    else start();
    if(announce)say(randomLine(value?"quiet":"welcomeBack"));scheduleIdle();
  }
  async function aiLine(trigger='manual'){
    if(petRequest||!petAI||(quiet&&trigger==='idle')||!active()||busy)return false;
    petRequest=true;root.dataset.aiState='thinking';
    try{
      const r=await api('/api/companion/chat',{method:'POST',body:JSON.stringify({trigger,pose})});
      if(r.budget&&typeof renderBudget==='function')renderBudget(r.budget);
      root.dataset.aiState=r.error?'failed':r.skipped||'ready';
      if(r.text&&active()&&(!quiet||trigger==='manual')&&!busy){root.dataset.replyModel=r.model||'';say(r.text,'小祥 · 对你说',16000);expression('shy',2400);return true;}
      if(trigger==='manual'&&r.error)say('唔，这次没能接上话。我在这里，等会儿再聊吧。','小祥 · 回应你');
      if(trigger==='manual'&&r.skipped){const messages={cooldown:'刚刚那句话，我还想听听你的回答呢。',daily_limit:'今天已经聊了不少，先让我安静陪你一会儿吧。',disabled:'AI闲聊暂时关着，我先在这里陪你。',busy:'我先把你刚才的事情处理好，再陪你聊。'};say(messages[r.skipped]||'我在这里，稍后再聊。','小祥 · 回应你');}
      return !!r.skipped;
    }catch{root.dataset.aiState='failed';return false;}
    finally{petRequest=false;}
  }
  async function loadPetSettings(){try{const s=await api('/api/settings');petAI=s.pet_ai_enabled&&s.api_generation_enabled;petProvider=s.pet_provider;root.dataset.aiProvider=petProvider;}catch{petAI=false;}}
  window.addEventListener('xy:settings',loadPetSettings);
  loadPetSettings();
  function scheduleIdle(){
    clearTimeout(idleTimer);
    if(quiet||localMotion==='quiet')return;
    idleTimer=setTimeout(async()=>{
      const typing=document.activeElement?.matches("input,textarea,[contenteditable=true]");
      if(active()&&!busy&&!typing&&bubble.classList.contains("is-resting")&&!root.matches(':hover')&&!document.querySelector('.settings-drawer:not([hidden])')&&!document.querySelector('#feedback-dialog[open]')){
        if(petAI)await aiLine('idle');else say(randomLine('idle'),'小祥 · 碎碎念');
      }
      scheduleIdle();
    },600000+Math.random()*300000);
  }
  function pat(){
    const time=performance.now();patState=M.recordPat(patState,time);
    if(patState.triggered)sulkUntil=time+4200;
    root.dataset.rapidPats=String(patState.times.length);root.dataset.sulking=String(time<sulkUntil);
    patStarted=time;root.dataset.patting='true';setTimeout(()=>{root.dataset.patting='false';},2000);
    const sulking=time<sulkUntil;
    say(randomLine(sulking?"repeat":"pat"),"小祥 · 回应你");expression(sulking?"pout":"shy",3000);scheduleIdle();
  }
  async function chat(){greetStarted=performance.now();say(petAI?'嗯？让我想想……':randomLine('greeting'),'小祥 · 回应你');expression('calm',1000);if(petAI)await aiLine();scheduleIdle();}
  // Find each cell's visible silhouette so generated facial variants don't jump between margins.
  function bounds(image,regions=null){
    const scratch=document.createElement("canvas");scratch.width=image.naturalWidth;scratch.height=image.naturalHeight;
    const sc=scratch.getContext("2d",{willReadFrequently:true});sc.drawImage(image,0,0);
    const {data}=sc.getImageData(0,0,scratch.width,scratch.height);
    const cells=regions||[0,1,2,3].map(i=>[i%2/2,Math.floor(i/2)/2,.5,.5]);
    return cells.map(cell=>{const [ox,oy,cw,ch]=cell.map((v,i)=>Math.floor(v*(i%2?scratch.height:scratch.width)));let x0=cw,y0=ch,x1=0,y1=0;
      for(let y=0;y<ch;y++)for(let x=0;x<cw;x++)if(data[((oy+y)*scratch.width+ox+x)*4+3]>100){x0=Math.min(x0,x);x1=Math.max(x1,x);y0=Math.min(y0,y);y1=Math.max(y1,y);}
      if(x1<=x0||y1<=y0)throw new Error("empty sprite cell");return {x:ox+x0,y:oy+y0,w:x1-x0+1,h:y1-y0+1};
    });
  }
  const image=new Image(),poseImage=new Image(),dailyImage=new Image();let dailyBounds=[],dailyLoaded=false;
  function draw(time){
    if(!loaded)return;
    syncResolution();
    const still=quiet||reduce.matches||localMotion==='quiet',amplitude=localMotion==='gentle'?.45:1;
    if(!still&&time>nextBlink){blinkUntil=time+190;nextBlink=time+3000+Math.random()*2600;}
    activity=M.activity(new Date().getHours(),musicPlaying,activityChoice);root.dataset.activity=activity;
    const frame=(!still&&time<blinkUntil)||time-patStarted<900||activity==='sleepy'?1:mood==="shy"||activity==='happy'?2:mood==="pout"||time<sulkUntil?3:0;
    root.dataset.frame=String(frame);root.dataset.mood=mood;
    const poseIndex={held:0,sit:1,hang:2,peek:3}[pose],usePose=poseLoaded&&poseIndex!==undefined;
    const closure=still?0:Math.max(M.eyelid(time,blinkUntil),(time-patStarted<900?.92:0));
    const dailyIndex=time<sulkUntil?0:({sleepy:1,lunch:2,music:3})[activity],useDaily=!usePose&&dailyLoaded&&dailyIndex!==undefined;
    root.dataset.spriteVariant=useDaily?['back','sleepy','lunch','music'][dailyIndex]:'original';
    const texture=useDaily?dailyImage:usePose?poseFrames[poseIndex]:image;
    const source=useDaily?dailyBounds[dailyIndex]:usePose?{x:0,y:0,w:poseBounds[poseIndex].w,h:poseBounds[poseIndex].h}:frameBounds[frame],w=logicalSize.width,h=logicalSize.height;
    root.dataset.eyelid=(usePose?0:closure).toFixed(2);
    root.dataset.poseAsset=usePose?pose:"standing";
    const targetHead=({stand:{x:180,y:110},held:{x:144,y:132},sit:{x:180,y:188},hang:{x:180,y:150},peek:{x:180,y:126}})[pose]||{x:180,y:110};
    const progress=transition?M.clamp((time-transition.started)/transition.duration):1,weight=M.blend(progress);
    const head=transition?{x:M.mix(transition.head.x,targetHead.x,weight.current),y:M.mix(transition.head.y,targetHead.y,weight.current)}:targetHead;
    ctx.setTransform(canvas.width/w,0,0,canvas.height/h,0,0);ctx.clearRect(0,0,w,h);ctx.save();
    ctx.translate(head.x-targetHead.x,head.y-targetHead.y);
    if(transition&&pose!=="held"){
      const supportY=h*(window.XYPetPhysics.supports[pose]??.965);
      ctx.translate(w/2,supportY);ctx.scale(1+weight.compression*.45,1-weight.compression);ctx.translate(-w/2,-supportY);
    }
    const patMotion=still?0:M.pat(time-patStarted)*amplitude,patAge=(time-patStarted)/1000;
    const idle=still?{lean:0,bob:0,sway:0}:M.idle(time),greet=still?0:M.greet(time-greetStarted)*amplitude;
    idle.lean*=amplitude;idle.bob*=amplitude;idle.sway*=amplitude;
    root.dataset.idleMotion=still?'still':idle.kind;
    const bounce=still?0:Math.sin(time/1050)*1.2*amplitude+idle.bob-Math.abs(greet)*2+(activity==='music'?Math.sin(time/310)*2.5:activity==='lunch'?Math.sin(time/230)*.8:activity==='sleepy'?Math.sin(time/2400)*3:0);
    const supportY=h*(window.XYPetPhysics.supports[pose]??.965);
    const tilt=pose==='hang'?.025:pose==='sit'?.013:.009;
    ctx.translate(w/2,supportY);ctx.rotate((still?0:Math.sin(time/1350)*tilt*amplitude+lookX*.008*amplitude+idle.lean+greet*.025)+patMotion*.035);ctx.scale(1+patMotion*.016,1-patMotion*.025);ctx.translate(-w/2,-supportY);
    if(pose==="held"){ctx.translate(w*.53,h*.47);ctx.rotate((world?.getSwing()||0)+(still?0:Math.sin(time/240)*.035*amplitude));ctx.translate(-w*.53,-h*.47);}
    const dimension=usePose?({held:[410,432],sit:[330,430],hang:[395,430],peek:[190,222]}[pose]):[h-25,h-8];
    const dh=Math.min(dimension[0],w*.91*source.h/source.w),dw=dh*source.w/source.h;
    if(pose==='hang')dimension[1]=h*window.XYPetPhysics.supports.hang+dh;
    ctx.translate(w/2,dimension[1]+(pose==="stand"?bounce+(still?0:lookY*1.5*amplitude):0));ctx.rotate(still||pose!=="stand"?0:(lookX*.018+Math.sin(time/1800)*.01)*amplitude);
    const breath=still?1:1+Math.sin(time/1000)*(pose==='hang'?.004:.003)*amplitude;
    ctx.scale(1,breath);root.dataset.turningAway=String(useDaily&&dailyIndex===0);root.dataset.sulking=String(time<sulkUntil);
    ctx.imageSmoothingEnabled=true;ctx.imageSmoothingQuality="high";
    const sway=still?0:Math.sin(time/1200)*idle.sway*.35;
    const current=ctx.getTransform(),sx=canvas.width/w,sy=canvas.height/h;
    const contained=M.containSprite({a:current.a/sx,b:current.b/sy,c:current.c/sx,d:current.d/sy,e:current.e/sx,f:current.f/sy},{x:-dw/2+sway,y:-dh,width:dw,height:dh},w,h);
    ctx.setTransform(contained.a*sx,contained.b*sy,contained.c*sx,contained.d*sy,contained.e*sx,contained.f*sy);
    if(useDaily&&dailyIndex===0){
      const fade=M.clamp(Math.min((time-(sulkUntil-4200))/180,(sulkUntil-time)/220));
      const front=frameBounds[frame];ctx.globalAlpha=1-fade;ctx.drawImage(image,front.x,front.y,front.w,front.h,-dw/2+sway,-dh,dw,dh);ctx.globalAlpha=fade;
    }
    ctx.drawImage(texture,source.x,source.y,source.w,source.h,-dw/2+sway,-dh,dw,dh);ctx.globalAlpha=1;
    if(!usePose&&!useDaily){
      const top=-dh,headY=top+dh*.27;
      ctx.save();ctx.strokeStyle='#425b86';ctx.fillStyle='#e4edff';ctx.lineWidth=6;ctx.lineCap='round';
      if(activity==='music'){
        ctx.beginPath();ctx.ellipse(0,headY-14,dw*.31,dh*.19,0,Math.PI,Math.PI*2);ctx.stroke();
        for(const side of [-1,1]){ctx.beginPath();ctx.roundRect(side*dw*.31-9,headY-17,18,38,8);ctx.fill();ctx.stroke();}
        ctx.font='25px sans-serif';ctx.fillStyle='#5277b6';ctx.fillText('♪',dw*.38,top+54+(still?0:Math.sin(time/300)*5));
      }else if(activity==='lunch'){
        const y=top+dh*.63;ctx.fillStyle='#f5f7ff';ctx.lineWidth=3;
        ctx.beginPath();ctx.ellipse(0,y,35,10,0,0,Math.PI*2);ctx.fill();ctx.stroke();ctx.beginPath();ctx.arc(0,y,34,0,Math.PI);ctx.fill();ctx.stroke();
        const lift=still?0:(Math.sin(time/500)+1)*8;ctx.strokeStyle='#a1836d';ctx.beginPath();ctx.moveTo(22,y-10-lift);ctx.lineTo(45,y-34-lift);ctx.moveTo(27,y-9-lift);ctx.lineTo(50,y-33-lift);ctx.stroke();
        ctx.fillStyle='#6f906a';ctx.fillRect(-15,y-5,13,5);ctx.fillStyle='#d9aa64';ctx.fillRect(3,y-4,13,6);
      }else if(activity==='sleepy'){
        ctx.font='24px sans-serif';ctx.fillStyle='#7182ad';ctx.fillText('z',dw*.35,top+52+(still?0:Math.sin(time/1800)*4));ctx.font='16px sans-serif';ctx.fillText('z',dw*.43,top+28);
      }else if(activity==='surprised'){
        ctx.font='30px sans-serif';ctx.fillStyle='#bf9b5e';ctx.fillText('!',dw*.36,top+65);
      }else if(activity==='happy'){
        ctx.font='26px sans-serif';ctx.fillStyle='#cf95b0';ctx.fillText('♡',dw*.34,top+60);
      }
      ctx.restore();
    }
    ctx.restore();
    displayHead=head;root.dataset.transitionProgress=progress.toFixed(2);
    if(!still&&time<dizzyUntil){ctx.save();ctx.fillStyle='#617da4';ctx.font='22px sans-serif';ctx.fillText('✧',head.x-48+Math.cos(time/160)*9,head.y-32);ctx.fillText('﹏',head.x+35,head.y-25+Math.sin(time/180)*6);ctx.restore();}
    root.dataset.dizzy=String(time<dizzyUntil);
    if(time>=sulkUntil&&patAge>=0&&patAge<1.7){
      ctx.save();ctx.globalAlpha=Math.sin(Math.PI*patAge/1.7);ctx.fillStyle='#7c98c2';ctx.font='25px sans-serif';ctx.fillText('♡',head.x+48+patAge*8,head.y-42-patAge*24);ctx.restore();
    }
    if(progress>=1&&transition){transition=null;root.dataset.transitioning="false";}
  }
  function tick(time){
    raf=0;if(!active()||((quiet||reduce.matches||localMotion==='quiet')&&!transition))return;
    if(time-lastFrame>32){lookX+=(targetX-lookX)*.12;lookY+=(targetY-lookY)*.12;draw(time);lastFrame=time;}
    raf=requestAnimationFrame(tick);
  }
  function start(){if(loaded&&active()&&((!quiet&&!reduce.matches&&localMotion!=='quiet')||transition)&&!raf)raf=requestAnimationFrame(tick);}
  image.onload=()=>{try{frameBounds=bounds(image);loaded=true;root.dataset.ready="true";document.querySelector("#pet-loading").hidden=true;draw(performance.now());start();}catch{loadError();}};
  function loadError(){document.querySelector("#pet-loading").textContent="小祥的形象暂时没加载好";root.dataset.ready="false";}
  dailyImage.onload=()=>{try{dailyBounds=bounds(dailyImage);dailyLoaded=true;draw(performance.now());}catch{dailyLoaded=false;}};dailyImage.src='/sakiko-daily-atlas-031.png';
  image.onerror=loadError;image.src="/sakiko-chibi-atlas.png";
  poseImage.onload=()=>{try{poseBounds=bounds(poseImage,[[0,0,.5,.52],[.5,0,.5,.58],[0,.52,.5,.48],[.5,.58,.5,.42]]);for(const b of poseBounds){const cell=document.createElement('canvas');cell.width=b.w;cell.height=b.h;cell.getContext('2d').drawImage(poseImage,b.x,b.y,b.w,b.h,0,0,b.w,b.h);poseFrames.push(cell);}poseLoaded=true;root.dataset.posesReady="true";draw(performance.now());}catch{root.dataset.posesReady="false";}};
  poseImage.onerror=()=>{root.dataset.posesReady="false";};poseImage.src="/sakiko-pose-atlas.png";
  document.querySelector("#pet-pat").addEventListener("click",pat);
  document.querySelector("#pet-chat").addEventListener("click",chat);
  quietButton.addEventListener("click",()=>setQuiet(!quiet));
  document.querySelector("#pet-dismiss").addEventListener("click",()=>{clearTimeout(bubbleTimer);bubble.classList.add("is-resting");});
  canvas.addEventListener("keydown",event=>{if(event.key==="Enter"||event.key===" "){event.preventDefault();pat();}});
  world=window.XYPetWorld.create({root,canvas,onPose:(value,animate=true)=>{if(value!==pose){if(animate)beginTransition(value==="held"?320:520);else{transition=null;root.dataset.transitioning="false";}pose=value;}draw(performance.now());start();},onTalk:value=>{
    if(value==="dizzy"){dizzyUntil=performance.now()+3200;say(randomLine("dizzy"),"小祥 · 有点晕");expression("pout",3200);draw(performance.now());start();return;}
    if(value==="pat"){pat();return;}if(value==="chat"){chat();return;}
    say(randomLine(value),"小祥 · 回应你");if(value==="lift"){patState.times=[];expression("shy",1800);}
  }});
  document.addEventListener("pointermove",event=>{
    if(!loaded||quiet||document.hidden)return;const rect=canvas.getBoundingClientRect();
    targetX=Math.max(-1,Math.min(1,(event.clientX-rect.left-rect.width/2)/300));targetY=Math.max(-1,Math.min(1,(event.clientY-rect.top-rect.height/3)/300));
  },{passive:true});
  document.addEventListener("visibilitychange",()=>{if(document.hidden){cancelAnimationFrame(raf);raf=0;clearTimeout(idleTimer);}else{draw(performance.now());start();scheduleIdle();}});
  window.addEventListener('xy:time',()=>{
    if(!quiet&&active()&&!busy&&!document.activeElement?.matches('input,textarea,[contenteditable=true]')&&!document.querySelector('dialog[open]')&&kind.textContent==='小祥 · 小声说'&&!bubble.classList.contains('is-resting'))say(randomLine('greeting'));
  });
  reduce.addEventListener("change",()=>{cancelAnimationFrame(raf);raf=0;transition=null;root.dataset.transitioning="false";draw(performance.now());start();});
  new ResizeObserver(()=>{draw(performance.now());start();}).observe(canvas);
  window.addEventListener("resize",()=>{draw(performance.now());start();});
  window.addEventListener('xy:local-preferences',event=>{
    localMotion=['normal','gentle','quiet'].includes(event.detail?.motion)?event.detail.motion:'normal';root.dataset.motionPreference=localMotion;
    cancelAnimationFrame(raf);raf=0;transition=null;root.dataset.transitioning='false';
    if(localMotion==='quiet'&&kind.textContent==='小祥 · 小声说')bubble.classList.add('is-resting');
    draw(performance.now());start();scheduleIdle();
  });
  window.addEventListener("xy:companion",event=>{
    const d=event.detail||{};busy=d.type==="thinking";
    if(quiet)return;
    if(d.type==="thinking")say(randomLine("thinking"),"小祥 · 正在想",45000);
    else if(d.type==="error"||d.failed){say(randomLine("error"),"小祥 · 回应你");expression("pout",2400);}
    else if(d.type==="reply"&&typeof d.text==="string"){
      const value=d.text.replace(/[*#`]/g,"").trim();say(value.length>76?value.slice(0,75)+"…":value,"小祥 · 对你说",14000);expression("calm",1000);
    }
    scheduleIdle();
  });
  setQuiet(quiet,false);if(quiet)bubble.classList.add("is-resting");else say(randomLine("greeting"));
  window.addEventListener('xy:music-state',event=>{musicPlaying=event.detail?.playing===true;draw(performance.now());start();});
  window.addEventListener('xy:pet-activity',event=>{activityChoice=['auto','idle','lunch','sleepy','music','happy','surprised'].includes(event.detail?.activity)?event.detail.activity:'auto';draw(performance.now());start();});
  const petStyle=document.createElement('link');petStyle.rel='stylesheet';petStyle.href='/live2d-pet.css';document.head.append(petStyle);
  const petModule=document.createElement('script');petModule.src='/live2d-pet.js';document.body.append(petModule);
})();
