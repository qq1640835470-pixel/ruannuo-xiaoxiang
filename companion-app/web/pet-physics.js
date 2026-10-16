"use strict";
/* Geometry shared by browser behavior and deterministic Node checks. No DOM or network. */
(function(host){
  const clamp=(n,a,b)=>Math.min(Math.max(n,a),Math.max(a,b));
  const supports={stand:.965,sit:.79,hang:.10,peek:.50,held:.47};
  function bounded(position,size,view){return {x:clamp(position.x,6,view.width-size.width-6),y:clamp(position.y,6,view.height-size.height-6)};}
  function dockBounds(position,size,view,dock){
    const point=bounded(position,size,view);
    if(dock?.mode==='peek'&&dock.id?.startsWith('window-edge:')){
      if(dock.edge==='left')point.x=-size.width*.5;
      if(dock.edge==='right')point.x=view.width-size.width*.5;
      if(dock.edge==='top')point.y=-size.height*.18;
      if(dock.edge==='bottom')point.y=view.height-size.height*.4;
    }
    return point;
  }
  function placement(dock,size,view){
    const r=dock.rect,p=dock.point;let x=p.x-size.width*.5,y;
    if(dock.edge==='left'){x=r.left-size.width*.62;y=p.y-size.height*.34;}
    else if(dock.edge==='right'){x=r.right-size.width*.38;y=p.y-size.height*.34;}
    else {const edgeY=dock.edge==='top'?r.top:r.bottom;y=edgeY-size.height*(supports[dock.mode]??supports.stand);}
    return dockBounds({x,y},size,view,dock);
  }
  function chooseDock(point,size,surfaces,view,hide=false){
    const choices=[];
    for(const surface of surfaces){
      const r=surface.rect;if(r.right-r.left<30||r.bottom-r.top<12)continue;
      if(point.x>=r.left-18&&point.x<=r.right+18){
        for(const edge of ['top','bottom']){
          const line=edge==='top'?r.top:r.bottom,mode=hide?'peek':edge==='top'?'sit':'hang';
          const rawY=line-size.height*supports[mode];
          if(rawY<5||rawY+size.height>view.height-5)continue;
          const distance=Math.abs(point.y-line);if(distance<=48)choices.push({...surface,point,edge,mode,distance});
        }
      }
      if(point.y>=r.top+20&&point.y<=r.bottom-20){
        for(const edge of ['left','right']){const distance=Math.abs(point.x-r[edge]);if(distance<=30)choices.push({...surface,point,edge,mode:'peek',distance:distance+8});}
      }
    }
    choices.sort((a,b)=>a.distance-b.distance||((a.rect.right-a.rect.left)*(a.rect.bottom-a.rect.top)-(b.rect.right-b.rect.left)*(b.rect.bottom-b.rect.top)));
    return choices[0]||null;
  }
  function landing(position,size,surfaces,view){
    const center=position.x+size.width*.5,feet=position.y+size.height*supports.sit;
    const options=surfaces.filter(s=>center>=s.rect.left&&center<=s.rect.right&&s.rect.top>=feet-8&&s.rect.top>=size.height*supports.sit+6&&s.rect.top+size.height*(1-supports.sit)<view.height-6).sort((a,b)=>a.rect.top-b.rect.top);
    if(options.length)return {...options[0],point:{x:center,y:options[0].rect.top},edge:'top',mode:'sit'};
    return {id:'window-floor',rect:{left:0,right:view.width,top:view.height-6,bottom:view.height},point:{x:center,y:view.height-6},edge:'top',mode:'stand'};
  }
  const api={clamp,bounded,dockBounds,placement,chooseDock,landing,supports};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;else host.XYPetPhysics=api;
})(typeof window==='undefined'?globalThis:window);
