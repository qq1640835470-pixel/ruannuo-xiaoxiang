"use strict";
(function(host){
  const stops=[
    [0,'#dce3ef','#c5d1e5','#788db2'],[5,'#eff2f9','#dce4f2','#8599bc'],
    [8,'#f2f7fc','#dceafa','#7e9fc5'],[12,'#f4f7fb','#e2edf9','#7d98be'],
    [17,'#e9edf6','#d5dff1','#8596bb'],[20,'#dfe6f1','#c9d6ea','#7c91b6'],[24,'#dce3ef','#c5d1e5','#788db2']
  ];
  const rgb=hex=>hex.match(/[\da-f]{2}/gi).map(x=>parseInt(x,16));
  const blend=(a,b,t)=>'#'+rgb(a).map((v,i)=>Math.round(v+(rgb(b)[i]-v)*t).toString(16).padStart(2,'0')).join('');
  function phase(hour){return hour<5?'深夜':hour<8?'清晨':hour<12?'上午':hour<14?'午间':hour<18?'下午':hour<20?'傍晚':'夜晚';}
  function palette(hour){
    hour=((hour%24)+24)%24;let i=0;while(i<stops.length-2&&hour>=stops[i+1][0])i++;
    const a=stops[i],b=stops[i+1],x=(hour-a[0])/(b[0]-a[0]),t=x*x*(3-2*x);
    return {sky:blend(a[1],b[1],t),rail:blend(a[2],b[2],t),accent:blend(a[3],b[3],t),glow:Number((.70+.17*Math.cos((hour-12)*Math.PI/12)).toFixed(4)),phase:phase(hour)};
  }
  const api={palette,phase};
  if(typeof module!=="undefined"&&module.exports){module.exports=api;return;}
  host.XYDaylight=api;
  let lastMinute='',lastPhase='',locationZone='';
  host.addEventListener('xy:location',e=>{locationZone=e.detail?.enabled?e.detail.timezone||'':'';lastMinute='';refresh();});
  function refresh(){
    const now=new Date(),opts=locationZone?{timeZone:locationZone}:{},parts=new Intl.DateTimeFormat('en-GB',{...opts,hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'}).formatToParts(now),values=Object.fromEntries(parts.map(p=>[p.type,p.value])),hour=Number(values.hour)+Number(values.minute)/60+Number(values.second)/3600;
    const time=document.querySelector('#live-clock'),date=document.querySelector('#today-label'),label=document.querySelector('#time-period');
    if(time){time.textContent=now.toLocaleTimeString('zh-CN',{...opts,hour12:false});time.dateTime=now.toISOString();time.title=(locationZone?'位置时区 · ':'本机系统时间 · ')+(locationZone||Intl.DateTimeFormat().resolvedOptions().timeZone);}
    const minute=now.getFullYear()+'-'+now.getMonth()+'-'+now.getDate()+'-'+now.getHours()+'-'+now.getMinutes();
    if(minute!==lastMinute){
      lastMinute=minute;const p=palette(hour),root=document.documentElement;
      root.style.setProperty('--sky',p.sky);root.style.setProperty('--rail',p.rail);root.style.setProperty('--accent',p.accent);root.style.setProperty('--glow',p.glow);root.dataset.timePhase=p.phase;
      if(date)date.textContent=now.toLocaleDateString('zh-CN',{...opts,year:'numeric',month:'long',day:'numeric',weekday:'long'});
      if(label)label.textContent=p.phase;
      document.querySelector('meta[name="theme-color"]')?.setAttribute('content',p.rail);
      if(lastPhase!==p.phase){lastPhase=p.phase;host.dispatchEvent(new CustomEvent('xy:time',{detail:{phase:p.phase,hour:Math.floor(hour)}}));}
    }
  }
  let timer=0;
  function start(){clearInterval(timer);refresh();if(!document.hidden)timer=setInterval(refresh,1000);}
  document.addEventListener('visibilitychange',start);host.addEventListener('focus',start);start();
})(typeof window==='undefined'?globalThis:window);
