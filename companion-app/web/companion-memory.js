'use strict';
(() => {
  let candidates=[],recent=[];
  try{recent=JSON.parse(localStorage.getItem('xy.pet.recent-lines')||'[]').filter(x=>typeof x==='string').slice(-20);}catch{}
  function remember(line){if(typeof line!=='string'||!line.trim())return;recent.push(line.trim());recent=recent.slice(-20);try{localStorage.setItem('xy.pet.recent-lines',JSON.stringify(recent));}catch{}}
  async function refresh(){try{const r=await fetch('/api/companion/library');if(r.ok){const d=await r.json();candidates=(d.lines||[]).filter(x=>typeof x==='string');}}catch{}}
  window.XYDialogue={next(fallback){const available=candidates.filter(s=>!recent.includes(s));const pool=available.length?available:candidates;const line=pool.length?pool[Math.floor(Math.random()*pool.length)]:fallback;remember(line);return line;},remember};
  window.addEventListener('xy:time',refresh);window.addEventListener('xy:settings',refresh);window.addEventListener('xy:companion',e=>{if(e.detail?.type==='reply')refresh();});refresh();
})();
