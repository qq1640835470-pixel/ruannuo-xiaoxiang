'use strict';
(()=>{
  const host=document.querySelector('#settings-drawer .drawer-body');if(!host)return;
  const section=document.createElement('details');section.id='feedback-target-settings';
  section.innerHTML=`<summary>反馈发送目标</summary><label>Codex会话UUID<input id="feedback-thread" maxlength="36" placeholder="完整会话UUID，不是会话标题"></label><label>本机备注<input id="feedback-target-label" maxlength="80" placeholder="例如：小祥开发会话"></label><label><input type="checkbox" id="feedback-target-enabled">启用手动反馈发送</label><button type="button" id="feedback-target-save">保存目标</button><p id="feedback-target-status" role="status"></p><button type="button" id="feedback-target-test">发送测试反馈</button><p>测试按钮会向已保存的目标发送一条固定测试消息；排队回执不代表已阅读。未发送或失败的正式反馈仍在本机暂存，不会自动补发。</p><p id="feedback-test-status" role="status"></p>`;
  host.append(section);
  const thread=section.querySelector('#feedback-thread'),label=section.querySelector('#feedback-target-label'),enabled=section.querySelector('#feedback-target-enabled'),status=section.querySelector('#feedback-target-status'),testStatus=section.querySelector('#feedback-test-status'),testButton=section.querySelector('#feedback-target-test');
  const display=document.createElement('p');display.id='feedback-target-display';display.className='muted-text';document.querySelector('#feedback-content').before(display);
  let target=null,testRecord=null;
  try{testRecord=JSON.parse(localStorage.getItem('xy.feedback.test')||'null');}catch{}
  function show(){
    display.textContent=target?.configured&&target.enabled?`发送目标：${target.label||'Codex会话'} · ${target.thread_id}`:'反馈发送尚未配置或已暂停；请在设置“反馈发送目标”中保存目标，仍可本机暂存。';
    status.textContent=target?.configured?`已保存：${target.thread_id}；${target.enabled?'已启用':'已暂停'}。${target.cli_available?'本机Codex命令行可用，目标是否接收需测试。':'未找到Codex命令行。'}`:'请填写并保存目标会话UUID。';
    updateFeedbackSendState();
  }
  function saveTest(record){testRecord=record;try{localStorage.setItem('xy.feedback.test',JSON.stringify(record));}catch{}}
  async function checkTest(id,attempt=0){
    try{
      const result=await api('/api/feedback/'+encodeURIComponent(id));saveTest({...result,id});
      testStatus.textContent=`测试目标：${result.target_label||result.target_thread_id||'旧记录未注明目标'} · ${result.target_thread_id||''}；${result.detail}`;
      if(result.status==='sending'&&attempt<20){setTimeout(()=>checkTest(id,attempt+1),1000);return;}
      testButton.disabled=false;testButton.textContent=['unknown','sending'].includes(result.status)?'核对测试回执':'发送测试反馈';
    }catch(e){saveTest({...testRecord,id,status:'unknown'});testStatus.textContent='测试状态待核对：'+e.message+'；没有自动重发。';testButton.disabled=false;testButton.textContent='核对测试回执';}
  }
  async function load(){
    try{target=await api('/api/feedback-target');thread.value=target.thread_id;label.value=target.label;enabled.checked=target.enabled;show();}
    catch(e){target=null;display.textContent='目标读取失败，反馈仍可本机暂存。';status.textContent=e.message;updateFeedbackSendState();}
  }
  section.querySelector('#feedback-target-save').onclick=async event=>{
    const button=event.currentTarget;button.disabled=true;
    try{target=await api('/api/feedback-target',{method:'PATCH',body:JSON.stringify({thread_id:thread.value,label:label.value,enabled:enabled.checked})});show();}
    catch(e){status.textContent=e.message;}finally{button.disabled=false;}
  };
  testButton.onclick=async()=>{
    if(!target?.configured||!target.enabled){testStatus.textContent='先保存并启用目标。';return;}
    if(thread.value.trim().toLowerCase()!==target.thread_id||label.value.trim()!==target.label||enabled.checked!==target.enabled){testStatus.textContent='目标有未保存的修改，请先保存。';return;}
    testButton.disabled=true;
    if(testRecord?.target_thread_id===target.thread_id&&['sending','unknown'].includes(testRecord.status)){await checkTest(testRecord.id);return;}
    const id=crypto.randomUUID(),captured={...target};saveTest({id,status:'sending',target_thread_id:captured.thread_id});
    try{
      const result=await api('/api/feedback/test',{method:'POST',body:JSON.stringify({id,target_thread_id:captured.thread_id})});saveTest({...result,id});await checkTest(id);
    }catch(e){saveTest({id,status:'unknown',target_thread_id:captured.thread_id});testStatus.textContent='没有取得测试回执：'+e.message+'；不会自动重发。';testButton.disabled=false;testButton.textContent='核对测试回执';}
  };
  window.XYFeedbackTarget={snapshot:()=>target?{...target}:null};
  window.addEventListener('xy:settings',load);document.querySelector('#feedback-button').addEventListener('click',load);
  load();if(testRecord?.id)checkTest(testRecord.id);
})();
