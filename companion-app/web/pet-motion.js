"use strict";
(function(host){
  const clamp=t=>Math.max(0,Math.min(1,t));
  const smooth=t=>{t=clamp(t);return t*t*t*(10+t*(-15+6*t));};
  const ease=smooth;
  const mix=(a,b,t)=>a+(b-a)*t;
  function travel(from,to,progress){const t=ease(progress);return {x:mix(from.x,to.x,t),y:mix(from.y,to.y,t)};}
  function blend(progress){const t=smooth(progress);return {previous:1-t,current:t,compression:Math.sin(Math.PI*clamp(progress))*.045};}
  function pat(elapsed){const t=Math.max(0,elapsed)/1000;return t>2?0:Math.sin(t*13)*Math.exp(-t*3.4);}
  function greet(elapsed){return elapsed<0||elapsed>1800?0:Math.sin(elapsed/150)*Math.sin(Math.PI*elapsed/1800)*Math.exp(-elapsed/1500);}
  function eyelid(time,until){return until>time?Math.sin(Math.PI*clamp((until-time)/190)):0;}
  function recordPat(state,time){
    const previous=state.times||[],last=previous[previous.length-1];
    const times=(last!==undefined&&time-last<=800?previous:[]).filter(t=>time-t<=8000).concat(time);
    const triggered=times.length>=11&&time-(state.lastTriggered??-Infinity)>=15000;
    return {times:triggered?[]:times,lastTriggered:triggered?time:state.lastTriggered,triggered};
  }
  function activity(hour,playing,choice='auto',context={}){
    if(choice!=='auto')return choice;
    if(playing)return 'music';
    if(['happy','surprised','sleepy','lunch'].includes(context.activity))return context.activity;
    return 'idle';
  }
  function reaction(value,elapsed){
    const t=Math.max(0,elapsed)/1000;
    if(t>2.4)return {bob:0,lean:0};
    const decay=Math.exp(-t*2.4);
    return value==='happy'?{bob:-Math.abs(Math.sin(t*7))*7*decay,lean:Math.sin(t*6)*.018*decay}:
      value==='surprised'?{bob:-Math.sin(Math.min(1,t/.5)*Math.PI)*8*decay,lean:-.018*decay}:{bob:0,lean:0};
  }
  function containSprite(matrix,rect,width,height,padding=6){
    const corners=[[rect.x,rect.y],[rect.x+rect.width,rect.y],[rect.x,rect.y+rect.height],[rect.x+rect.width,rect.y+rect.height]].map(([x,y])=>({x:matrix.a*x+matrix.c*y+matrix.e,y:matrix.b*x+matrix.d*y+matrix.f}));
    const left=Math.min(...corners.map(p=>p.x)),right=Math.max(...corners.map(p=>p.x)),top=Math.min(...corners.map(p=>p.y)),bottom=Math.max(...corners.map(p=>p.y));
    const scale=Math.min(1,(width-padding*2)/(right-left),(height-padding*2)/(bottom-top));
    const x=Math.max(padding-left*scale,Math.min(0,width-padding-right*scale)),y=Math.max(padding-top*scale,Math.min(0,height-padding-bottom*scale));
    return {a:matrix.a*scale,b:matrix.b*scale,c:matrix.c*scale,d:matrix.d*scale,e:matrix.e*scale+x,f:matrix.f*scale+y};
  }
  // A brief stretch, attentive lean, then soft skirt sway, separated by rest.
  function idle(time){
    const cycle=((time%36000)+36000)%36000,slot=Math.floor(cycle/12000),age=cycle%12000;
    const envelope=age<4200?Math.sin(Math.PI*age/4200)**2:0;
    return {kind:envelope===0?'breathe':['stretch','listen','sway'][slot],lean:envelope*[.012,-.022,.016][slot],bob:envelope*[-3,-.5,1][slot],sway:envelope*[.4,.2,2][slot]};
  }
  function sidebarPosition(rect,point,size,view,occupied=[]){
    if(rect.width<size.width+12||rect.height<size.height+12||point.x<rect.left||point.x>rect.right||point.y<rect.top||point.y>rect.bottom)return null;
    const blocks=occupied.filter(r=>r.bottom>rect.top&&r.top<rect.bottom).sort((a,b)=>a.top-b.top);
    let top=rect.top+6;
    for(const block of [...blocks,{top:rect.bottom-6,bottom:rect.bottom}]){
      if(point.y>=top&&point.y<=block.top&&block.top-top>=size.height){
        return {x:Math.max(rect.left+6,Math.min(point.x-size.width/2,rect.right-size.width-6)),y:Math.max(top,Math.min(point.y-size.height*.47,block.top-size.height))};
      }
      top=Math.max(top,block.bottom+8);
    }
    return null;
  }
  const api={clamp,smooth,ease,mix,travel,blend,pat,greet,eyelid,containSprite,idle,sidebarPosition,recordPat,activity,reaction};
  if(typeof module!=="undefined"&&module.exports)module.exports=api;else host.XYPetMotion=api;
})(typeof window==="undefined"?globalThis:window);
