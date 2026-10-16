"use strict";
// Error class + own script/line only. Never send message, stack, text, DOM or URL query.
(() => {
  let windowStarted=Date.now(),count=0;
  function report(reason,file,line){
    if(Date.now()-windowStarted>60000){windowStarted=Date.now();count=0;}
    if(count++>=10)return;
    const known=new Set(['Error','TypeError','RangeError','SyntaxError','ReferenceError','URIError','EvalError']);
    const error_type=known.has(reason?.name)?reason.name:'Error';
    const name=String(file||'').split('/').pop().split('?')[0];
    fetch('/api/diagnostics/client',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({error_type,file:name,line:Number.isInteger(line)?line:null}),keepalive:true}).catch(()=>{});
  }
  window.addEventListener('error',event=>report(event.error,event.filename,event.lineno));
  window.addEventListener('unhandledrejection',event=>report(event.reason,'frontend',null));
})();
