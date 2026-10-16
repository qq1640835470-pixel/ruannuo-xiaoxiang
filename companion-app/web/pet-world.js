"use strict";
/* A window-local pet world: only observes this app's element geometry. */
(() => {
  const P=window.XYPetPhysics;
  const M=window.XYPetMotion;
  function create({root,canvas,onPose,onTalk}){
    const homeParent=root.parentNode,homeBefore=root.nextSibling,stage=root.querySelector('.pet-stage');
    const homeButton=document.querySelector('#pet-home'),poseButton=document.querySelector('#pet-pose');
    const guide=document.createElement('div');guide.className='pet-snap-guide';guide.hidden=true;document.body.append(guide);
    const reduced=window.matchMedia('(prefers-reduced-motion: reduce)');
    let free=false,position={x:0,y:0},dock=null,pendingDock=null,pointer=null,candidate=null,fall=0,movement=0,homePlaceholder=null,layoutFrame=0,swing=0,pose='stand',homeShape=null;
    root.dataset.pose=pose;
    const size=()=>({width:stage.getBoundingClientRect().width,height:stage.getBoundingClientRect().height});
    const view=()=>({width:innerWidth,height:innerHeight});
    function surfaces(){
      const specs=[['composer','#chat-form'],['topbar','.topbar'],['plan-intro','.plan-intro'],['plan-toolbar','.plan-toolbar'],['empty-plan','.empty-plan'],['sidebar','.sidebar']];
      const entries=specs.map(([id,selector])=>({id,node:document.querySelector(selector)}));
      document.querySelectorAll('.task-card').forEach(node=>entries.push({id:'task:'+node.dataset.taskId,node}));
      document.querySelectorAll('.nav-item').forEach(node=>entries.push({id:'nav:'+node.dataset.page,node}));
      const edges=['left','right','top','bottom'].map(edge=>({id:'window-edge:'+edge,edge,rect:{left:6,right:innerWidth-6,top:6,bottom:innerHeight-6,width:innerWidth-12,height:innerHeight-12}}));
      return edges.concat(entries.filter(s=>s.node&&s.node.getClientRects().length).map(s=>({...s,rect:s.node.getBoundingClientRect().toJSON()})).filter(s=>s.rect.top<innerHeight&&s.rect.bottom>0));
    }
    function setPose(value,animate=true){if(value===pose)return;pose=value;root.dataset.pose=value;onPose(value,animate);}
    function place(point){
      const s=size();position=P.dockBounds(point,s,view(),dock);root.style.left=position.x+'px';root.style.top=position.y+'px';
      root.classList.toggle('controls-above',position.y+s.height>innerHeight-85);
      const bubble=root.querySelector('.pet-bubble'),b=bubble.getBoundingClientRect();
      const headY=position.y+s.height*({stand:.25,held:.30,sit:.43,hang:.34,peek:.29}[pose]??.3);
      const right=position.x+s.width*.88+10,left=position.x-b.width-10;
      let x=right,y=headY-b.height/2;
      if(right+b.width>innerWidth-8){if(left>=8)x=left;else{x=position.x+s.width/2-b.width/2;y=position.y-b.height-12;if(y<8)y=position.y+s.height+12;}}
      root.style.setProperty('--bubble-x',P.clamp(x,8,innerWidth-b.width-8)+'px');
      root.style.setProperty('--bubble-y',P.clamp(y,8,innerHeight-b.height-8)+'px');
      const controls=root.querySelector('.pet-controls').getBoundingClientRect();
      root.style.setProperty('--controls-x',P.clamp(position.x+s.width/2-controls.width/2,8,innerWidth-controls.width-8)+'px');
      const menuY=position.y+s.height+8+controls.height<=innerHeight-8?position.y+s.height+8:position.y-controls.height-8;
      root.style.setProperty('--controls-y',P.clamp(menuY,8,innerHeight-controls.height-8)+'px');
      window.dispatchEvent(new CustomEvent('xy:pet-layout',{detail:{stage:stage.getBoundingClientRect().toJSON(),bubble:bubble.getBoundingClientRect().toJSON(),resting:bubble.classList.contains('is-resting')}}));
    }
    function hideGuide(){guide.hidden=true;candidate=null;}
    function showGuide(value){
      candidate=value;if(!value){guide.hidden=true;return;}
      guide.hidden=false;const stageSize=size(),r=value.id==='sidebar-space'?{left:value.point.x-stageSize.width/2,right:value.point.x+stageSize.width/2,top:value.point.y-stageSize.height*P.supports.stand,bottom:value.point.y}:value.rect;guide.style.left=Math.max(0,r.left)+'px';guide.style.top=Math.max(0,r.top)+'px';guide.style.width=Math.min(innerWidth,r.right)-Math.max(0,r.left)+'px';guide.style.height=Math.min(innerHeight,r.bottom)-Math.max(0,r.top)+'px';
      guide.textContent=value.id==='sidebar-space'?'松手站在这里':value.mode==='sit'?'松手坐下':value.mode==='hang'?'松手挂住':value.mode==='stand'?'松手站在这里':'松手躲起来';guide.dataset.edge=value.edge;
    }
    function detach(){
      if(free)return;const rect=stage.getBoundingClientRect(),outer=root.getBoundingClientRect();homeShape={height:outer.height,dx:rect.left-outer.left,dy:rect.top-outer.top};free=true;document.body.append(root);root.classList.add('pet-free');homeButton.hidden=false;poseButton.hidden=false;place({x:rect.x,y:rect.y});
    }
    function clearMask(){stage.style.clipPath='';root.style.removeProperty('--pet-visible-height');root.dataset.edge='';}
    function save(){
      try{localStorage.setItem('xy.pet.world',JSON.stringify({free,x:position.x/Math.max(1,innerWidth),y:position.y/Math.max(1,innerHeight),dock:dock?{id:dock.id,edge:dock.edge,mode:dock.mode,fraction:dock.fraction,offsetY:dock.offsetY,yFraction:dock.yFraction}:null}));}catch{}
    }
    function mask(){
      if(!dock||dock.mode!=='peek'){clearMask();return;}root.dataset.edge=dock.edge;
      if(dock.id.startsWith('window-edge:')){
        const s=size();stage.style.clipPath=`inset(${Math.max(0,-position.y)}px ${Math.max(0,position.x+s.width-innerWidth)}px ${Math.max(0,position.y+s.height-innerHeight)}px ${Math.max(0,-position.x)}px)`;return;
      }
      const r=dock.rect,s=size();
      if(dock.edge==='left')stage.style.clipPath=`inset(0 ${Math.max(0,position.x+s.width-r.left)}px 0 0)`;
      else if(dock.edge==='right')stage.style.clipPath=`inset(0 0 0 ${Math.max(0,r.right-position.x)}px)`;
      else {const edgeY=dock.edge==='top'?r.top:r.bottom;stage.style.clipPath=`inset(0 0 ${Math.max(0,position.y+s.height-edgeY)}px 0)`;root.style.setProperty('--pet-visible-height',Math.max(0,edgeY-position.y)+'px');}
    }
    function stopMovement(){cancelAnimationFrame(movement);movement=0;homePlaceholder?.remove();homePlaceholder=null;root.classList.remove('is-settling','is-returning');root.dataset.moving='false';}
    function moveTo(destination,animate,done){
      const target=P.dockBounds(destination,size(),view(),dock),from={...position};
      if(!animate||reduced.matches||Math.hypot(target.x-from.x,target.y-from.y)<.6){place(target);mask();done?.();return;}
      const started=performance.now(),duration=440;root.classList.add('is-settling');root.dataset.moving='true';
      function step(time){const progress=M.clamp((time-started)/duration);place(M.travel(from,target,progress));mask();
        if(progress<1){movement=requestAnimationFrame(step);return;}movement=0;root.classList.remove('is-settling');root.dataset.moving='false';done?.();}
      movement=requestAnimationFrame(step);
    }
    function rendererDock(value){
      if(!value||root.dataset.renderer!=='live2d'||!['sit','hang'].includes(value.mode))return value;
      const mode=value.mode==='sit'?'stand':'peek',edgeY=value.edge==='top'?value.rect.top:value.rect.bottom;
      const y=edgeY-size().height*P.supports[mode];
      return y>=6&&y+size().height<=innerHeight-6?{...value,mode}:null;
    }
    function settle(value,speak=true){
      value=rendererDock(value)||P.landing(position,size(),[],view());
      cancelAnimationFrame(fall);fall=0;stopMovement();hideGuide();pendingDock=null;dock=value;root.classList.remove('is-lifted','is-falling');clearMask();
      if(!dock)return;
      const r=dock.rect;dock.fraction=dock.fraction??P.clamp((dock.point.x-r.left)/Math.max(1,r.right-r.left),0,1);
      dock.yFraction=dock.yFraction??P.clamp(dock.point.y/innerHeight,0,1);
      setPose(dock.mode,speak);root.dataset.anchor=dock.id;moveTo(P.placement(dock,size(),view()),speak,save);
      if(speak)onTalk(dock.mode==='sit'?'sit':dock.mode==='hang'?'hang':dock.mode==='peek'?'peek':'land');
    }
    function sidebarDock(point){
      const sidebar=document.querySelector('.sidebar');if(!sidebar||!sidebar.getClientRects().length)return null;
      const rect=sidebar.getBoundingClientRect().toJSON(),occupied=[...sidebar.querySelectorAll('.brand,nav,.sidebar-bottom')].filter(n=>n.getClientRects().length).map(n=>n.getBoundingClientRect().toJSON());
      const target=M.sidebarPosition(rect,point,size(),view(),occupied);if(!target)return null;
      const feet=target.y+size().height*P.supports.stand;
      return {id:'sidebar-space',edge:'top',mode:'stand',rect:{...rect,top:feet},point:{x:target.x+size().width/2,y:feet},offsetY:(feet-rect.top)/rect.height};
    }
    function chooseDock(point,hide){
      const distances={left:point.x,right:innerWidth-point.x,top:point.y,bottom:innerHeight-point.y},edge=Object.keys(distances).sort((a,b)=>distances[a]-distances[b])[0];
      if(distances[edge]<=(hide?48:28)){const surface=surfaces().find(s=>s.id==='window-edge:'+edge);return {...surface,point,mode:'peek'};}
      return rendererDock((!hide&&sidebarDock(point))||P.chooseDock(point,size(),surfaces().filter(s=>!s.id.startsWith('window-edge:')),view(),hide));
    }
    function drop(point,hide){
      const hit=chooseDock(point,hide);if(hit){settle(hit);return;}
      clearMask();dock=null;const goal=P.landing(position,size(),surfaces().filter(s=>!s.id.startsWith('window-edge:')),view()),dest=P.placement(goal,size(),view());
      if(reduced.matches){settle(goal);return;}
      let last=performance.now(),velocity=0;root.classList.add('is-falling');setPose('held');
      function step(time){
        const dt=Math.min((time-last)/1000,.04);last=time;velocity+=1050*dt;
        const nextY=Math.min(dest.y,position.y+velocity*dt);
        place({x:position.x,y:nextY});
        if(nextY>=dest.y-.5){settle(goal);return;}
        fall=requestAnimationFrame(step);
      }
      if(dest.y<=position.y){settle(goal);return;}fall=requestAnimationFrame(step);
    }
    function reflow(){
      layoutFrame=0;if(!free||pointer||movement)return;
      if(pendingDock){
        const target=surfaces().find(s=>s.id===pendingDock.id);
        if(target){const r=target.rect;settle({...target,...pendingDock,rect:r,point:{x:r.left+(pendingDock.fraction??.5)*(r.right-r.left),y:pendingDock.edge==='bottom'?r.bottom:r.top}},false);}
        return;
      }
      if(dock?.id==='sidebar-space'){
        const sidebar=document.querySelector('.sidebar'),r=sidebar?.getBoundingClientRect();
        const target=r&&sidebarDock({x:r.left+(dock.fraction??.5)*r.width,y:r.top+(dock.offsetY??.6)*r.height-size().height*.495});
        if(target){settle(target,false);return;}dock=null;
      }
      if(dock&&dock.id!=='window-floor'){
        const current=surfaces().find(s=>s.id===dock.id);
        if(current){const r=current.rect,point={x:r.left+(dock.fraction??.5)*(r.right-r.left),y:['left','right'].includes(dock.edge)?(dock.yFraction??.5)*innerHeight:dock.edge==='bottom'?r.bottom:r.top};settle({...dock,...current,point},false);return;}
        dock=null;
      }
      if(dock?.id==='window-floor')dock.rect={left:0,right:innerWidth,top:innerHeight-6,bottom:innerHeight};
      if(dock){dock.point={x:position.x+size().width/2,y:innerHeight-6};settle(dock,false);}
      else drop({x:position.x+size().width/2,y:position.y},false);
    }
    function queueReflow(){if(!layoutFrame)layoutFrame=requestAnimationFrame(reflow);}
    function home(){
      cancelAnimationFrame(fall);fall=0;stopMovement();const captured=pointer?.id;pointer=null;if(captured!==undefined&&canvas.hasPointerCapture(captured))canvas.releasePointerCapture(captured);dock=null;pendingDock=null;hideGuide();clearMask();root.classList.remove('is-lifted','is-falling');
      const finish=()=>{
        free=false;root.classList.remove('pet-free','is-returning','bubble-below','bubble-right','bubble-left','controls-above');root.style.left=root.style.top='';delete root.dataset.anchor;
        homeParent.insertBefore(root,homeBefore?.parentNode===homeParent?homeBefore:null);homePlaceholder?.remove();homePlaceholder=null;homeButton.hidden=true;poseButton.hidden=true;setPose('stand');save();onTalk('home');
      };
      if(!free||!homeShape||reduced.matches){finish();return;}
      homePlaceholder=document.createElement('section');homePlaceholder.className='pet pet-home-placeholder';homePlaceholder.setAttribute('aria-hidden','true');homePlaceholder.style.height=homeShape.height+'px';homePlaceholder.style.visibility='hidden';homePlaceholder.style.pointerEvents='none';
      homeParent.insertBefore(homePlaceholder,homeBefore?.parentNode===homeParent?homeBefore:null);const target=homePlaceholder.getBoundingClientRect();root.classList.add('is-returning');setPose('stand');moveTo({x:target.left+homeShape.dx,y:target.top+homeShape.dy},true,finish);
    }
    canvas.addEventListener('pointerdown',event=>{
      if(event.button!==0)return;cancelAnimationFrame(fall);fall=0;stopMovement();pointer={id:event.pointerId,x:event.clientX,y:event.clientY,lastX:event.clientX,lastTime:performance.now(),direction:0,shakes:0,shakeTime:0,dragged:false};canvas.setPointerCapture(event.pointerId);
    });
    canvas.addEventListener('pointermove',event=>{
      if(!pointer||event.pointerId!==pointer.id)return;
      if(!pointer.dragged&&Math.hypot(event.clientX-pointer.x,event.clientY-pointer.y)<7)return;
      if(!pointer.dragged){detach();canvas.setPointerCapture(event.pointerId);pointer.grip={x:pointer.x-position.x,y:pointer.y-position.y};pointer.liftStarted=performance.now();dock=null;pendingDock=null;delete root.dataset.anchor;clearMask();root.classList.add('is-lifted');root.classList.remove('is-falling');pointer.dragged=true;onTalk('lift');}
      const time=performance.now(),delta=event.clientX-pointer.lastX,direction=Math.sign(delta);
      if(Math.abs(delta)>12&&time-pointer.lastTime<180){if(direction!==pointer.direction&&pointer.direction){pointer.shakes=time-pointer.shakeTime<1000?pointer.shakes+1:1;pointer.shakeTime=time;if(pointer.shakes>=4){onTalk('dizzy');pointer.shakes=0;}}pointer.direction=direction;}
      swing=P.clamp((event.clientX-pointer.lastX)/Math.max(16,time-pointer.lastTime)*.16,-.28,.28);pointer.lastX=event.clientX;pointer.lastTime=time;
      setPose('held');const s=size(),catchUp=M.smooth((time-pointer.liftStarted)/280);place({x:event.clientX-M.mix(pointer.grip.x,s.width*.53,catchUp),y:event.clientY-M.mix(pointer.grip.y,s.height*.47,catchUp)});showGuide(chooseDock({x:event.clientX,y:event.clientY},event.shiftKey));
    });
    canvas.addEventListener('pointerup',event=>{
      if(!pointer||event.pointerId!==pointer.id)return;const dragged=pointer.dragged;pointer=null;if(canvas.hasPointerCapture(event.pointerId))canvas.releasePointerCapture(event.pointerId);
      root.classList.remove('is-lifted');
      if(dragged)drop({x:event.clientX,y:event.clientY},event.shiftKey);
      else {const r=canvas.getBoundingClientRect(),head=({stand:.25,held:.3,sit:.43,hang:.34,peek:.29}[pose]??.25);onTalk(Math.abs((event.clientY-r.top)/r.height-head)<.25?'pat':'chat');}
    });
    function cancel(){if(!pointer)return;const moved=pointer.dragged;pointer=null;root.classList.remove('is-lifted');if(moved)drop({x:position.x+size().width/2,y:position.y},false);}
    canvas.addEventListener('pointercancel',cancel);canvas.addEventListener('lostpointercapture',cancel);
    canvas.addEventListener('keydown',event=>{
      if(event.key==='Escape'){event.preventDefault();home();return;}
      if(!free||!event.key.startsWith('Arrow'))return;event.preventDefault();const amount=event.shiftKey?40:12;const dx=event.key==='ArrowLeft'?-amount:event.key==='ArrowRight'?amount:0,dy=event.key==='ArrowUp'?-amount:event.key==='ArrowDown'?amount:0;
      stopMovement();dock=null;clearMask();setPose('stand');place({x:position.x+dx,y:position.y+dy});save();
    });
    poseButton.addEventListener('click',()=>{
      if(!dock)return;if(root.dataset.renderer==='live2d'){if(dock.mode==='peek'){onTalk('peek');return;}const r=dock.rect;settle({...dock,mode:'peek',point:{x:position.x+size().width/2,y:dock.edge==='top'?r.top:r.bottom}});return;}if(dock.id==='sidebar-space'){onTalk('no-room');return;}const s=size(),r=dock.rect,modes=dock.edge==='left'||dock.edge==='right'?['peek']:['sit','hang','peek'];
      const edgeY=dock.edge==='top'?r.top:r.bottom;
      for(let i=1;i<modes.length;i++){const next=modes[(modes.indexOf(dock.mode)+i)%modes.length],raw=edgeY-s.height*P.supports[next];
        if(raw>=6&&raw+s.height<=innerHeight-6){settle({...dock,mode:next});return;}}
      onTalk('no-room');
    });
    document.addEventListener('keydown',event=>{if(event.key==='Escape'&&!event.defaultPrevented&&free&&!document.querySelector('dialog[open],.settings-drawer:not([hidden])')){event.preventDefault();home();}});
    homeButton.addEventListener('click',home);window.addEventListener('xy:pet-renderer',()=>{if(free){if(dock)settle(dock,false);else queueReflow();}});new ResizeObserver(queueReflow).observe(stage);window.addEventListener('resize',queueReflow);document.addEventListener('scroll',queueReflow,true);
    new MutationObserver(records=>{if(records.some(r=>!root.contains(r.target)&&!guide.contains(r.target)&&r.target!==homeButton))queueReflow();}).observe(document.querySelector('.app-shell'),{childList:true,subtree:true,attributes:true,attributeFilter:['hidden']});
    // Persist coordinates, not app contents or cursor history. Broken records simply return home.
    try{const saved=JSON.parse(localStorage.getItem('xy.pet.world')||'null');
      if(saved?.free&&Number.isFinite(saved.x)&&Number.isFinite(saved.y)){
        detach();place({x:saved.x*innerWidth,y:saved.y*innerHeight});
        if(saved.dock&&typeof saved.dock.id==='string'&&['stand','sit','hang','peek'].includes(saved.dock.mode)&&['top','bottom','left','right'].includes(saved.dock.edge)&&Number.isFinite(saved.dock.fraction)){
          const rSidebar=document.querySelector('.sidebar')?.getBoundingClientRect();
          const restoredSidebar=saved.dock.id==='sidebar-space'&&Number.isFinite(saved.dock.offsetY)&&rSidebar?sidebarDock({x:rSidebar.left+saved.dock.fraction*rSidebar.width,y:rSidebar.top+saved.dock.offsetY*rSidebar.height-size().height*.495}):null;
          const target=surfaces().find(s=>s.id===saved.dock.id);if(restoredSidebar)settle(restoredSidebar,false);else if(target){const r=target.rect;settle({...target,...saved.dock,rect:r,point:{x:r.left+P.clamp(saved.dock.fraction??.5,0,1)*(r.right-r.left),y:['left','right'].includes(saved.dock.edge)?(saved.dock.yFraction??.5)*innerHeight:saved.dock.edge==='bottom'?r.bottom:r.top}},false);}
          else if(saved.dock.id==='window-floor')settle(P.landing(position,size(),[],view()),false);
          else {pendingDock={...saved.dock,fraction:P.clamp(saved.dock.fraction,0,1)};setPose(saved.dock.mode);setTimeout(()=>{if(pendingDock){pendingDock=null;dock=null;reflow();}},2500);}
        }
      }
    }catch{}
    return {home,refreshBubble:()=>{if(free)place(position);},getPose:()=>pose,getSwing:()=>{if(!pointer?.dragged)swing*=.91;return swing;},isFree:()=>free};
  }
  window.XYPetWorld={create};
})();
