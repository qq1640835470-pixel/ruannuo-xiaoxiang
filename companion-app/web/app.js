"use strict";
const $ = (selector) => document.querySelector(selector);
const state = {tasks: [], messages: [], settings: {}, connectors: [], filter: "open", busy: false, editingTaskId: null};
const statusNames = {pending:"待安排", active:"进行中", paused:"已暂停", done:"已完成"};
let lastFocus;

async function api(path, options = {}) {
  let response = await fetch(path, {headers: {"Content-Type":"application/json"}, ...options});
  if(response.status===403){await fetch("/",{cache:"no-store"});response=await fetch(path,{headers:{"Content-Type":"application/json"},...options});}
  const raw = await response.text();
  let data;
  try { data = raw ? JSON.parse(raw) : {}; } catch { throw new Error(`服务返回了无法识别的内容（${response.status}）`); }
  if (!response.ok) {const message=typeof data.error === "string" ? data.error : data.error?.message || data.detail || `请求失败（${response.status}）`;const requestId=/^[a-f0-9]{16}$/.test(data.request_id||"")?data.request_id:"";const failure=new Error(message+(requestId?`（请求编号：${requestId}）`:""));failure.requestId=requestId;failure.responseData=data;throw failure;}
  return data;
}
function error(message, selector = "#global-error") {const el=$(selector); el.textContent=message || "";el.hidden=!message;}
function el(tag, className, text) {const node=document.createElement(tag);if(className)node.className=className;if(text!==undefined)node.textContent=String(text);return node;}
function dateLabel(value, includeYear = false) {
  if(!value)return "未指定时间";
  const d=new Date(value);if(Number.isNaN(d.getTime()))return String(value);
  return d.toLocaleString("zh-CN", {year:includeYear?"numeric":undefined,month:"long",day:"numeric",hour:"2-digit",minute:"2-digit"});
}
function changePage(page) {
  const plan=page==="plan";$("#chat-page").hidden=plan;$("#plan-page").hidden=!plan;$("#page-title").textContent=plan?"计划日程":"";
  document.querySelectorAll("[data-page]").forEach(b=>{b.classList.toggle("selected",b.dataset.page===page);b.setAttribute("aria-current",b.dataset.page===page?"page":"false");});
  history.replaceState(null,"",`#${page}`);
}
function renderMessages() {
  const conversation=$("#conversation");
  conversation.querySelectorAll(".message").forEach(n=>n.remove());
  $("#welcome").hidden=state.messages.length>0;
  const visibleMessages=state.messages.slice(-30);
  visibleMessages.forEach((message,index)=>{
    const role=message.role==="user"?"user":"assistant";
    const row=el("article",`message ${role}`);const avatar=el("div",role==="user"?"message-avatar":"message-avatar sakiko-avatar",role==="user"?"我":undefined);if(role==="assistant"){avatar.setAttribute("role","img");avatar.setAttribute("aria-label","小祥");}row.append(avatar);
    const body=message.display_content||message.content||"";
    const content=el("div","message-content");content.append(el("div","message-text",body));
    if(role==="assistant"){
      const details=executionBlock(message);if(details)content.append(details);
      const previous=visibleMessages.slice(0,index).reverse().find(m=>m.role==="user");
      const retry=chatRetry(message,previous?.content);if(retry)content.append(retry);
      if(body){const voice=el("button","text-button voice-button","▷ 朗读");voice.type="button";voice.addEventListener("click",()=>readAloud(body,voice));content.append(voice);}
    }
    if(message.created_at)content.append(el("div","message-time",dateLabel(message.created_at)));
    row.append(content);conversation.append(row);
  });
  if(state.busy)conversation.append(el("div","message busy-text","小祥在处理啦…"));
  conversation.scrollTop=conversation.scrollHeight;
}
function retryState(message){
  const records=[...(message.actions||[]),...(message.execution||[])];
  const failed=!!message.error||records.some(r=>r.status==='failed');
  const uncertain=records.some(r=>['completed','requested','unknown','sending'].includes(r.status));
  return {failed,uncertain};
}
function chatRetry(message,text){
  const status=retryState(message);if(!status.failed||!text)return null;
  const box=el('div','message-retry');
  if(message.request_id)box.append(el('small','',`请求编号：${message.request_id}`));
  if(status.uncertain){box.append(el('small','','部分操作已发起或完成，请先核对操作记录；如需继续，可编辑原消息后发送。'));return box;}
  const retry=el('button','subtle-button','重试这条消息');retry.type='button';retry.disabled=state.busy;
  retry.addEventListener('click',()=>{if(state.busy)return;$('#chat-input').value=text;sendMessage();});
  box.append(retry);return box;
}
function executionBlock(message) {
  const actions=Array.isArray(message.actions)?message.actions:[];
  const records=Array.isArray(message.execution)?message.execution:[];
  if(!actions.length&&!records.length&&!message.provider)return null;
  const box=el("details","execution-details"),summary=el("summary");box.append(summary);
  const statuses={prepared:"待处理",requested:"已发起",failed:"未完成",completed:"已完成"};
  const updateSummary=()=>{const items=[...actions,...records];summary.textContent=items.length?`操作记录 · ${items.some(a=>a.status==="failed")?"未完成":items.some(a=>a.status==="prepared")?"待处理":items.every(a=>a.status==="completed")?"已完成":"已发起"}`:"回复信息";};
  updateSummary();
  const appendCode=text=>{const pre=el("pre");pre.append(el("code","",text));box.append(pre);return pre;};
  actions.forEach(action=>{
    const text=()=>`${action.title||"操作"}\n状态：${statuses[action.status]||"未知"}\n${action.result||action.description||"没有返回结果"}${action.status==="requested"?"\n说明：系统已接收启动请求；尚未核验窗口或业务完成。":""}`;
    const pre=appendCode(text());
    if(action.status!=="prepared")return;
    const button=el("button","subtle-button","执行此操作");button.type="button";box.append(button);
    button.addEventListener("click",async()=>{
      button.disabled=true;button.textContent="处理中…";
      try{const result=await api(`/api/actions/${encodeURIComponent(action.id)}/execute`,{method:"POST",body:"{}"});action.status=result.status;action.result=result.result||result.reply;pre.firstChild.textContent=text();button.remove();updateSummary();}
      catch(e){pre.firstChild.textContent=text()+`\n本次请求：${e.message}；请刷新核对状态。`;button.textContent="状态待核对";summary.textContent="操作记录 · 需核对";}
    });
  });
  records.forEach(record=>appendCode(`${record.title||"处理记录"}\n状态：${statuses[record.status]||record.status||"未知"}\n${record.result||""}`));
  if(message.display_content&&message.display_content!==message.content)appendCode("原始回复记录：\n"+message.content);
  if(message.provider)appendCode(`回复来源：${message.provider==="local"?"本机处理":message.provider}\n型号：${message.model||"未提供"}`);
  return box;
}
async function sendMessage(event,requestId) {
  event?.preventDefault();const input=$("#chat-input");const text=input.value.trim();if(!text||state.busy)return;
  requestId=requestId||crypto.randomUUID().replaceAll('-','');
  state.busy=true;$('#chat-recover')?.setAttribute('hidden','');$("#send-button").disabled=true;input.disabled=true;error("");input.value="";
  window.dispatchEvent(new CustomEvent("xy:companion",{detail:{type:"thinking"}}));
  state.messages.push({role:"user",content:text,created_at:new Date().toISOString()});renderMessages();
  const controller=new AbortController(),responseTimeout=setTimeout(()=>controller.abort(),60000);
  try {const result=await api("/api/chat",{method:"POST",body:JSON.stringify({text,client_request_id:requestId}),signal:controller.signal});
    if(result.pending){try{localStorage.setItem('xy.chat.pending',JSON.stringify({text,id:requestId}));}catch{}window.dispatchEvent(new CustomEvent('xy:chat-recovery',{detail:{text,id:requestId}}));input.value=text;}else{try{const saved=JSON.parse(localStorage.getItem('xy.chat.pending')||'null');if(saved?.id===requestId)localStorage.removeItem('xy.chat.pending');}catch{}}
    if(result.music){window.dispatchEvent(new CustomEvent('xy:music-queue',{detail:{tracks:result.music.tracks.map(t=>({...t,remote:true})),append:false}}));const song=result.music.tracks.find(t=>String(t.id)===String(result.music.play_id));if(song)window.dispatchEvent(new CustomEvent('xy:music-select',{detail:{...song,remote:true}}));}
    if(result.workspace)window.dispatchEvent(new CustomEvent("xy:workspace",{detail:result.workspace}));
    if(Array.isArray(result.feedback_drafts))importFeedbackDrafts(result.feedback_drafts);
    if(result.feedback_id){feedbackId=result.feedback_id;try{localStorage.setItem('xy.feedback.last',feedbackId);}catch{}}
    state.messages.push({role:"assistant",content:result.reply||"服务已收到请求。",actions:result.actions||[],execution:result.execution||[],provider:result.provider,model:result.model,error:result.error||null,request_id:result.request_id||"",created_at:new Date().toISOString()});
    window.dispatchEvent(new CustomEvent("xy:companion",{detail:{type:"reply",text:result.reply,failed:result.error||result.actions?.some(a=>a.status==="failed")}}));
    if(result.error||result.actions?.some(a=>a.status==="failed"))input.value=text;
    await refreshTasks();
  }catch(e){try{localStorage.setItem('xy.chat.pending',JSON.stringify({text,id:requestId}));}catch{}window.dispatchEvent(new CustomEvent('xy:chat-recovery',{detail:{text,id:requestId}}));error(`消息未完成：${e.message}。可以点击“核对结果／重试”；原文字已保留。`);input.value=text;window.dispatchEvent(new CustomEvent("xy:companion",{detail:{type:"error"}}));}
  finally {clearTimeout(responseTimeout);state.busy=false;$("#send-button").disabled=false;input.disabled=false;renderMessages();input.focus();}
}
async function refreshTasks() {try{const data=await api("/api/state");state.tasks=data.tasks||[];if(data.settings)state.settings=data.settings;if(data.budget)state.settings.budget=data.budget;if(Array.isArray(data.feedback_drafts))importFeedbackDrafts(data.feedback_drafts);renderTasks();renderSettings();}catch(e){error(`刷新日程失败：${e.message}`);}}
function renderTasks() {
  const list=$("#task-list");list.replaceChildren();
  const tasks=state.tasks.filter(t=>state.filter==="all"||(state.filter==="done"?t.status==="done":t.status!=="done")).slice().sort((a,b)=>{
    if(!a.scheduled_at)return b.scheduled_at?1:0;if(!b.scheduled_at)return -1;return String(a.scheduled_at).localeCompare(String(b.scheduled_at));
  });
  $("#task-count").textContent=`${tasks.length} 件事`;
  if(!tasks.length){const box=el("div","empty-plan");box.append(el("p","",state.filter==="done"?"暂无已完成事项":"暂无计划"));list.append(box);return;}
  tasks.forEach(task=>{
    const card=el("article",`task-card ${task.status==="done"?"done":""}`);card.dataset.taskId=task.id;
    const check=el("button","task-check",task.status==="done"?"✓":"");check.setAttribute("aria-label",task.status==="done"?`重新安排：${task.title}`:`完成：${task.title}`);check.addEventListener("click",()=>updateTask(task,{status:task.status==="done"?"pending":"done"},check));
    const main=el("div","task-main");main.append(el("h3","",task.title));if(task.details)main.append(el("p","",task.details));main.append(el("div","task-meta",`${dateLabel(task.scheduled_at,true)} · ${statusNames[task.status]||task.status}`));
    const controls=el("div","task-controls");const select=el("select");select.setAttribute("aria-label",`修改状态：${task.title}`);
    Object.entries(statusNames).forEach(([key,label])=>{const option=el("option","",label);option.value=key;option.selected=task.status===key;select.append(option);});select.addEventListener("change",()=>updateTask(task,{status:select.value},select));
    const remove=el("button","delete-task","×");remove.setAttribute("aria-label",`删除：${task.title}`);remove.addEventListener("click",async()=>{if(!confirm(`删除「${task.title}」？`))return;remove.disabled=true;try{await api(`/api/tasks/${encodeURIComponent(task.id)}`,{method:"DELETE"});state.tasks=state.tasks.filter(t=>t.id!==task.id);renderTasks();}catch(e){error(e.message);remove.disabled=false;}});
    const edit=el("button","text-button","编辑");edit.setAttribute("aria-label",`编辑：${task.title}`);edit.addEventListener("click",()=>openTaskForm(task));
    controls.append(edit,select,remove);card.append(check,main,controls);list.append(card);
  });
}
async function updateTask(task, patch, control) {control.disabled=true;error("");try{const data=await api(`/api/tasks/${encodeURIComponent(task.id)}`,{method:"PATCH",body:JSON.stringify(patch)});Object.assign(task,patch,data.task||{});renderTasks();}catch(e){error(e.message);control.disabled=false;renderTasks();}}
async function saveTask(event) {
  event.preventDefault();const form=event.currentTarget;const values=Object.fromEntries(new FormData(form));values.title=values.title.trim();if(!values.title)return;
  const editing=state.editingTaskId;$("#save-task").disabled=true;error("");try{await api(editing?`/api/tasks/${encodeURIComponent(editing)}`:"/api/tasks",{method:editing?"PATCH":"POST",body:JSON.stringify(values)});form.reset();form.hidden=true;state.editingTaskId=null;await refreshTasks();}catch(e){error(`保存失败：${e.message}`);}finally{$("#save-task").disabled=false;}
}
function openTaskForm(task=null){const form=$("#task-form");form.reset();state.editingTaskId=task?.id||null;$("#save-task").textContent=task?"保存修改":"保存";if(task){form.elements.title.value=task.title||"";form.elements.details.value=task.details||"";if(task.scheduled_at){const date=new Date(task.scheduled_at);if(!Number.isNaN(date.getTime())){const local=new Date(date.getTime()-date.getTimezoneOffset()*60000);form.elements.scheduled_at.value=local.toISOString().slice(0,16);}}}form.hidden=false;form.scrollIntoView({block:"nearest"});form.elements.title.focus();}
function openSettings(){lastFocus=document.activeElement;$("#settings-drawer").hidden=false;$("#drawer-backdrop").hidden=false;$(".app-shell").inert=true;$("#sakiko-companion").inert=true;$("#settings-close").focus();loadSettings();loadConnectors();}
function closeSettings(){$("#settings-drawer").hidden=true;$("#drawer-backdrop").hidden=true;$(".app-shell").inert=false;$("#sakiko-companion").inert=false;lastFocus?.focus();}
function renderSettings(){const s=state.settings;$("#model-select").value=s.provider||"local";$("#cloud-enabled").checked=s.api_generation_enabled===true;$("#model-detail").textContent=s.model?`当前型号：${s.model}`:"具体型号由本机配置决定";$("#pet-ai-enabled").checked=s.pet_ai_enabled===true;$("#pet-provider").value=s.pet_provider||"gemini";renderBudget(s.budget);window.XYModels?.settingsLoaded(s);if(s.local_preferences)window.XYLocal?.apply(s.local_preferences);}
async function loadSettings(){try{const data=await api("/api/settings");state.settings=data.settings||data;if(data.budget)state.settings.budget=data.budget;renderSettings();}catch(e){error(e.message,"#settings-error");}}
async function saveSettings(){const b=$("#save-settings");b.disabled=true;error("","#settings-error");$("#settings-save-status").textContent="";try{const data=await api("/api/settings",{method:"PATCH",body:JSON.stringify({...window.XYModels?.savePayload(),provider:$("#model-select").value,api_generation_enabled:$("#cloud-enabled").checked,pet_ai_enabled:$("#pet-ai-enabled").checked,pet_provider:$("#pet-provider").value})});state.settings=data.settings||data;renderSettings();$("#settings-save-status").textContent="设置已保存";window.dispatchEvent(new Event("xy:settings"));}catch(e){error(`保存失败：${e.message}`,"#settings-error");}finally{b.disabled=false;}}
async function loadConnectors(){const list=$("#connector-list");list.textContent="正在读取…";try{const data=await api("/api/connectors");state.connectors=data.connectors||[];list.replaceChildren();if(!state.connectors.length){list.append(el("p","muted-text","暂未报告可用连接。"));return;}state.connectors.forEach(c=>{const card=el("article","connector-card");const header=el("header");header.append(el("span","",c.name||c.id),el("span",`status-badge ${c.available===true?"available":""}`,c.status|| (c.available?"可用":"未连接")));card.append(header);if(c.description)card.append(el("p","",c.description));if(c.capabilities?.length)card.append(el("p","",`支持：${c.capabilities.join("、")}`));if(c.limitations?.length)card.append(el("p","",`限制：${c.limitations.join("；")}`));list.append(card);});}catch(e){list.textContent=`读取失败：${e.message}`;}}
function formatBalance(data){const items=data.providers||data.balances;if(Array.isArray(items)){if(!items.length)return data.note||"尚无余额快照。";return items.map(x=>{const lines=[x.name||x.provider||"账户"];if(Array.isArray(x.balances)&&x.balances.length)x.balances.forEach(b=>lines.push(`余额：${b.total??"未知"}${b.currency?` ${b.currency}`:""}`));else if(x.api_credit!==null&&x.api_credit!==undefined)lines.push(`API 额度：${x.api_credit}${x.unit?` ${x.unit}`:""}`);else if(x.balance!==null&&x.balance!==undefined)lines.push(`余额：${x.balance}${x.currency?` ${x.currency}`:""}`);else lines.push("余额：未知（供应商未提供可读金额）");if(x.authentication)lines.push(`认证：${typeof x.authentication==="string"?x.authentication:JSON.stringify(x.authentication)}`);if(x.status)lines.push(`状态：${x.status}`);if(x.message||x.note)lines.push(x.message||x.note);if(x.checked_at)lines.push(`查询时间：${dateLabel(x.checked_at,true)}`);return lines.join("\n");}).join("\n\n");}return data.reply||data.message||data.note||JSON.stringify(data,null,2);}
async function refreshBalances(){const button=$("#refresh-balances");button.disabled=true;$("#balance-result").textContent="正在查询…";try{const data=await api("/api/balances/refresh",{method:"POST",body:"{}"});$("#balance-result").textContent=formatBalance(data);}catch(e){$("#balance-result").textContent=`查询失败：${e.message}`;}finally{button.disabled=false;}}
function renderBudget(budget){const target=$("#budget-result");if(!target)return;if(!budget){target.textContent="正在等待本机预算数据。";return;}const money=v=>Number.isFinite(Number(v))?`¥${Number(v).toFixed(2)}`:"未知";target.textContent=`本机预算上限 ${budget.unlimited?"不限":money(budget.limit_cny)}\n已估算 ${money(budget.spent_estimate_cny)} · 预留 ${money(budget.reserved_cny)}\n${budget.unlimited?"不按本机余额拦截":"剩余 "+money(budget.remaining_cny)} · ${budget.requests??0} 次请求`;}
async function shutdown(){if(!confirm("退出本机助手服务？退出后需要重新启动才能继续使用。"))return;const button=$("#shutdown-button");button.disabled=true;try{await api("/api/shutdown",{method:"POST",body:"{}"});$("#connection-status").textContent="服务已退出";$("#settings-save-status").textContent="本机服务已退出，可以关闭此页面。";$("#send-button").disabled=true;}catch(e){error(`退出失败：${e.message}`,"#settings-error");button.disabled=false;}}
function stopReadAloud(){
  const current=readAloud.current;readAloud.current=null;
  if('speechSynthesis' in window)speechSynthesis.cancel();
  if(current?.button){current.button.textContent='▷ 朗读';current.button.setAttribute('aria-pressed','false');}
  const stop=$('#speech-stop');if(stop)stop.hidden=true;
}
function readAloud(text,button){
  if(!('speechSynthesis' in window)){error('此浏览器不支持系统语音朗读。');return;}
  if(readAloud.current?.text===text){stopReadAloud();return;}
  stopReadAloud();const utterance=new SpeechSynthesisUtterance(text);utterance.lang='zh-CN';utterance.rate=.95;
  readAloud.current={text,button,utterance};button.textContent='■ 停止朗读';button.setAttribute('aria-pressed','true');
  const stop=$('#speech-stop');if(stop)stop.hidden=false;
  const finished=()=>{if(readAloud.current?.utterance===utterance)stopReadAloud();};
  utterance.onend=finished;utterance.onerror=finished;speechSynthesis.speak(utterance);
}

async function exportData(){const button=$("#export-button");button.disabled=true;$("#export-status").textContent="正在导出…";try{const data=await api("/api/export");data.feedback_drafts=readFeedbackDrafts();const blob=new Blob([JSON.stringify(data,null,2)],{type:"application/json;charset=utf-8"});const url=URL.createObjectURL(blob);const a=el("a");a.href=url;a.download=`软糯小祥本机数据-${new Date().toISOString().slice(0,10)}.json`;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),10000);$("#export-status").textContent="已生成 JSON 下载文件，请查看浏览器下载记录。";}catch(e){$("#export-status").textContent=`导出失败：${e.message}`;}finally{button.disabled=false;}}
async function loadDiagnostics(download=false){const status=$('#diagnostics-status'),button=download?$('#diagnostics-export'):$('#diagnostics-view');button.disabled=true;status.textContent='正在读取…';try{const data=await api('/api/diagnostics');if(download){const blob=new Blob([JSON.stringify(data,null,2)],{type:'application/json;charset=utf-8'}),url=URL.createObjectURL(blob),a=el('a');a.href=url;a.download=`运行诊断-${new Date().toISOString().slice(0,10)}.json`;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),10000);status.textContent='诊断日志已下载；日志不会自动发送。';}else{$('#diagnostics-output').textContent=JSON.stringify({...data,events:(data.events||[]).slice(-100)},null,2);$('#diagnostics-details').open=true;status.textContent=`已显示最近 ${(data.events||[]).slice(-100).length} 条记录。`;}}catch(e){status.textContent=`读取失败：${e.message}`;}finally{button.disabled=false;}}

let feedbackId='',feedbackTimer=0,feedbackSending=false,lastFeedbackContent='',editingDraftId='';
const feedbackDraftKey='xy.feedback.drafts',feedbackWorkingKey='xy.feedback.working';
const feedbackIgnoredKey='xy.feedback.ignored-sources';
function readFeedbackDrafts(){try{const value=JSON.parse(localStorage.getItem(feedbackDraftKey)||'[]');return Array.isArray(value)?value.filter(x=>x&&typeof x.id==='string'&&typeof x.content==='string'):[];}catch{return [];}}
function writeFeedbackDrafts(items){try{localStorage.setItem(feedbackDraftKey,JSON.stringify(items));notifyFeedbackChange();return true;}catch{return false;}}
function readIgnoredFeedbackSources(){try{const value=JSON.parse(localStorage.getItem(feedbackIgnoredKey)||'[]');return Array.isArray(value)?value.filter(x=>typeof x==='string'):[];}catch{return [];}}
function ignoreFeedbackSource(id){const ignored=readIgnoredFeedbackSources();if(!ignored.includes(id))ignored.push(id);try{localStorage.setItem(feedbackIgnoredKey,JSON.stringify(ignored));return true;}catch{return false;}}
function importFeedbackDrafts(rows){const drafts=readFeedbackDrafts(),ignored=new Set(readIgnoredFeedbackSources());let changed=false;for(const row of rows||[]){if(!row||typeof row.id!=='string'||ignored.has(row.id))continue;const id='api:'+row.id;if(drafts.some(d=>d.id===id))continue;drafts.push({id,source_id:row.id,source:'api',title:row.title||'',raw_text:row.raw_text||'',content:row.summary||'',delivery:'saved',sourceStatus:row.status||'pending',createdAt:row.created_at||new Date().toISOString(),provider:row.provider||'',model:row.model||'',updatedAt:new Date().toISOString()});changed=true;}if(changed&&!writeFeedbackDrafts(drafts))throw new Error('无法保存导入的反馈，本机已有反馈和编辑文字已保留');if(changed)renderFeedbackDrafts();return changed;}
async function syncFeedbackDrafts(){const button=$('#feedback-sync');button.disabled=true;$('#feedback-status').textContent='正在获取对话反馈…';try{const data=await api('/api/feedback-drafts');importFeedbackDrafts(data.drafts||[]);renderFeedbackDrafts();$('#feedback-status').textContent='已同步服务端反馈；导入内容保存在本机，可编辑后手动发送。';}catch(e){$('#feedback-status').textContent=`获取失败：${e.message}。本机暂存仍可照常使用。`;}finally{button.disabled=false;}}
async function patchFeedbackSource(draft,status,deliveryId){if(!draft?.source_id)return;const body={status};if(deliveryId)body.delivery_id=deliveryId;try{await api(`/api/feedback-drafts/${encodeURIComponent(draft.source_id)}`,{method:'PATCH',body:JSON.stringify(body)});}catch{/* Local draft and delivery record remain available when the service is offline. */}}
function notifyFeedbackChange(){if(typeof window!=='undefined'&&typeof CustomEvent!=='undefined')window.dispatchEvent(new CustomEvent('xy-feedback-change'));}
function saveFeedbackWorking(){try{localStorage.setItem(feedbackWorkingKey,JSON.stringify({content:$('#feedback-content').value,updatedAt:new Date().toISOString(),draftId:editingDraftId,mode:editingDraftId?'edit':'new'}));notifyFeedbackChange();return true;}catch{return false;}}
function renderFeedbackDrafts(){const list=$('#feedback-draft-list');list.replaceChildren();const drafts=readFeedbackDrafts();const count=$('#feedback-draft-count');if(count)count.textContent=`共 ${drafts.length} 条暂存反馈`;if(!drafts.length){list.append(el('p','muted-text','暂无暂存反馈'));return;}drafts.sort((a,b)=>String(b.updatedAt).localeCompare(String(a.updatedAt))).forEach(d=>{const row=el('div','feedback-draft-row');const open=el('button','feedback-draft-open');open.type='button';open.textContent=`${d.title?d.title+' · ':''}${d.content.slice(0,60).replace(/\s+/g,' ')} · ${d.delivery==='queued'?'已排队':d.delivery==='sending'?'发送中':d.delivery==='unknown'?'状态待核对':'未发送'} · ${dateLabel(d.updatedAt)}`;open.addEventListener('click',()=>{if(!preserveFeedbackBeforeSwitch())return;editingDraftId=d.id;$('#feedback-content').value=d.content;$('#feedback-status').textContent=d.deliveryDetail||'正在编辑这条暂存反馈；暂存后才会更新原记录。';$('#feedback-source-details').hidden=!(d.source==='api'&&d.raw_text);$('#feedback-source-text').textContent=d.source==='api'?(d.raw_text||''):'';if(!saveFeedbackWorking())$('#feedback-status').textContent='浏览器本机存储不可用；当前内容仍在编辑框中。';updateFeedbackSendState();});const remove=el('button','subtle-button','删除');remove.type='button';remove.addEventListener('click',async()=>{if(d.source_id){if(!ignoreFeedbackSource(d.source_id)){$('#feedback-status').textContent='本机忽略记录保存失败，未删除该反馈。';return;}void patchFeedbackSource(d,'dismissed');}if(!writeFeedbackDrafts(readFeedbackDrafts().filter(x=>x.id!==d.id))){$('#feedback-status').textContent='无法写入本机存储，暂存未删除。';return;}if(editingDraftId===d.id){editingDraftId='';$('#feedback-source-details').hidden=true;$('#feedback-source-text').textContent='';}renderFeedbackDrafts();});row.append(open,remove);list.append(row);});}
function updateFeedbackSendState(){const save=$('#feedback-save-draft');save.textContent=editingDraftId?'保存修改':'暂存为新反馈';const count=$('#feedback-draft-count');if(count)count.textContent=`共 ${readFeedbackDrafts().length} 条暂存反馈`;const content=$('#feedback-content').value.trim(),draft=readFeedbackDrafts().find(d=>d.id===editingDraftId);const blocked=['queued','sending'].includes(draft?.delivery)||(['unknown','failed'].includes(draft?.delivery)&&(content===lastFeedbackContent||content===draft.attemptedContent));$('#feedback-send').disabled=feedbackSending||!content||blocked;}
async function pollFeedback(id,attempt=0){
    try{const r=await api('/api/feedback/'+encodeURIComponent(id));if(id!==feedbackId)return;
    $('#feedback-status').textContent=r.detail;$('#feedback-status').dataset.status=r.status;
    if(r.status==='sending'&&attempt<25){feedbackTimer=setTimeout(()=>pollFeedback(id,attempt+1),1000);return;}
    feedbackSending=false;const drafts=readFeedbackDrafts();const d=drafts.find(x=>x.deliveryId===id);if(d){d.delivery=r.status==='queued'||r.status==='completed'?'queued':r.status==='sending'?'sending':r.status==='failed'?'failed':'unknown';d.deliveryDetail=r.detail;writeFeedbackDrafts(drafts);renderFeedbackDrafts();}updateFeedbackSendState();$('#feedback-send').textContent='发送给Codex';
    if(r.status==='sending')$('#feedback-status').textContent='仍在等待回执，可稍后打开此处核对。请先不要重复发送。';
  }catch{feedbackSending=false;const drafts=readFeedbackDrafts(),d=drafts.find(x=>x.deliveryId===id);if(d){d.delivery='unknown';d.deliveryDetail='暂时无法核对回执，反馈可能已发送，请先不要重复提交。';writeFeedbackDrafts(drafts);renderFeedbackDrafts();}$('#feedback-status').textContent='暂时无法核对回执。反馈可能已发送，请先不要重复提交。';updateFeedbackSendState();}
}
function openFeedback(){
  const dialog=$('#feedback-dialog');dialog.showModal();renderFeedbackDrafts();let working=null;try{working=JSON.parse(localStorage.getItem(feedbackWorkingKey)||'null');}catch{};const drafts=readFeedbackDrafts();const saved=working?.draftId&&drafts.find(d=>d.id===working.draftId);const unsaved=typeof working?.content==='string'&&working.content.trim()&&(!saved||working.content.trim()!==saved.content.trim());const selected=unsaved?saved:null;editingDraftId=selected?.id||'';$('#feedback-content').value=unsaved?working.content:'';$('#feedback-source-details').hidden=!(selected?.source==='api'&&selected.raw_text);$('#feedback-source-text').textContent=selected?.source==='api'?(selected.raw_text||''):'';$('#feedback-status').textContent=unsaved?'已恢复未暂存的本机编辑内容。':'填写新反馈，或从下方列表选择一条进行编辑。';$('#feedback-content').focus();updateFeedbackSendState();
  try{feedbackId=feedbackId||localStorage.getItem('xy.feedback.last')||'';}catch{}
  if(feedbackId&&(!working?.content||selected?.deliveryId===feedbackId))pollFeedback(feedbackId);
}
async function sendFeedback(event){
  event.preventDefault();updateFeedbackSendState();if($('#feedback-send').disabled)return;
  const content=$('#feedback-content').value.trim(),drafts=readFeedbackDrafts();let draft=drafts.find(d=>d.id===editingDraftId);
  if(!draft){draft={id:crypto.randomUUID()};drafts.push(draft);editingDraftId=draft.id;}
  const sendingDraftId=draft.id,deliveryId=crypto.randomUUID();
  Object.assign(draft,{content,updatedAt:new Date().toISOString(),attemptedContent:content,deliveryId,delivery:'sending',deliveryDetail:'正在发送给Codex…'});
  if(!writeFeedbackDrafts(drafts)){$('#feedback-status').textContent='本机暂存失败，已保留文字；请恢复本机存储后再发送。';return;}saveFeedbackWorking();renderFeedbackDrafts();feedbackSending=true;clearTimeout(feedbackTimer);feedbackId=deliveryId;$('#feedback-send').disabled=true;$('#feedback-status').textContent='正在发送给Codex…';
  try{const r=await api('/api/feedback',{method:'POST',body:JSON.stringify({id:deliveryId,content})});lastFeedbackContent=content;
    const saved=readFeedbackDrafts(),record=saved.find(d=>d.id===sendingDraftId);
    if(record){record.delivery=r.status==='queued'||r.status==='completed'?'queued':r.status==='sending'?'sending':r.status==='failed'?'failed':'unknown';record.deliveryDetail=r.detail;writeFeedbackDrafts(saved);renderFeedbackDrafts();}
    try{localStorage.setItem('xy.feedback.last',deliveryId);}catch{}
    $('#feedback-status').textContent=r.detail;pollFeedback(deliveryId);
  }catch(e){feedbackSending=false;lastFeedbackContent=content;const saved=readFeedbackDrafts(),record=saved.find(d=>d.id===sendingDraftId);const detail='未取得发送回执：'+e.message+'。请先核对队列状态。';if(record){record.delivery='unknown';record.deliveryDetail=detail;writeFeedbackDrafts(saved);}renderFeedbackDrafts();saveFeedbackWorking();$('#feedback-status').textContent=detail;updateFeedbackSendState();}
}
function resetFeedbackEditor(){editingDraftId='';$('#feedback-content').value='';$('#feedback-source-details').hidden=true;$('#feedback-source-text').textContent='';updateFeedbackSendState();}
function saveFeedbackDraft(){
  const content=$('#feedback-content').value.trim();if(!content){$('#feedback-status').textContent='先填写反馈内容，再暂存。';return false;}
  const drafts=readFeedbackDrafts();let d=drafts.find(x=>x.id===editingDraftId);
  if(!d||['queued','sending','unknown'].includes(d.delivery)){d={id:crypto.randomUUID(),delivery:'saved'};drafts.push(d);}
  d.content=content;d.updatedAt=new Date().toISOString();
  if(!writeFeedbackDrafts(drafts)){$('#feedback-status').textContent='本机存储空间不可用，反馈仍保留在编辑框中。';return false;}
  // Commit an empty working copy before clearing the editor so failed storage never loses text.
  try{localStorage.setItem(feedbackWorkingKey,JSON.stringify({content:'',draftId:'',mode:'new',updatedAt:new Date().toISOString()}));}catch{$('#feedback-status').textContent='反馈已暂存，但工作副本无法更新；当前文字已保留。';renderFeedbackDrafts();return false;}
  resetFeedbackEditor();notifyFeedbackChange();renderFeedbackDrafts();$('#feedback-status').textContent=`已暂存，共 ${drafts.length} 条。可以继续填写下一条反馈。`;return true;
}
function preserveFeedbackBeforeSwitch(){
  const content=$('#feedback-content').value.trim();if(!content)return true;
  const saved=readFeedbackDrafts().find(d=>d.id===editingDraftId);
  if(saved?.content===content)return true;
  // Preserve unfinished text as its own entry before explicitly changing editor targets.
  const drafts=readFeedbackDrafts();drafts.push({id:crypto.randomUUID(),content,updatedAt:new Date().toISOString(),delivery:'saved'});
  if(!writeFeedbackDrafts(drafts)){$('#feedback-status').textContent='本机保存失败，已保留当前文字。';return false;}return true;
}
function newFeedbackDraft(){
  if(!preserveFeedbackBeforeSwitch())return;
  // Do not clear the visible text unless the empty working copy can be persisted.
  try{localStorage.setItem(feedbackWorkingKey,JSON.stringify({content:'',draftId:'',mode:'new',updatedAt:new Date().toISOString()}));}catch{$('#feedback-status').textContent='本机工作副本保存失败，已保留当前文字。';return;}
  resetFeedbackEditor();notifyFeedbackChange();$('#feedback-status').textContent='新反馈已准备好；原有草稿仍保存在列表中。';renderFeedbackDrafts();$('#feedback-content').focus();
}
function feedbackContentInput(){
  const draft=readFeedbackDrafts().find(d=>d.id===editingDraftId);
  if(draft&&['queued','sending'].includes(draft.delivery)){editingDraftId='';$('#feedback-source-details').hidden=true;$('#feedback-source-text').textContent='';}
  if(!saveFeedbackWorking())$('#feedback-status').textContent='本机工作副本保存失败；当前文字仍在编辑框中。';updateFeedbackSendState();
}
const feedbackSnapshotFields=['id','content','title','source_id','source','raw_text','sourceStatus','createdAt','updatedAt','provider','model','delivery','deliveryId','deliveryDetail','attemptedContent'];
function exportFeedbackSnapshot(){let working=null;try{working=JSON.parse(localStorage.getItem(feedbackWorkingKey)||'null');}catch{}return {drafts:readFeedbackDrafts().map(d=>Object.fromEntries(feedbackSnapshotFields.filter(k=>typeof d[k]==='string').map(k=>[k,d[k]]))),working:working&&typeof working.content==='string'?{content:working.content,draftId:typeof working.draftId==='string'?working.draftId:'',updatedAt:typeof working.updatedAt==='string'?working.updatedAt:'',mode:working.draftId?'edit':'new'}:null};}
function importFeedbackSnapshot(snapshot){
  const drafts=readFeedbackDrafts(),ids=new Set(drafts.map(d=>d.id)),ignored=new Set(readIgnoredFeedbackSources());let changed=false;
  for(const incoming of Array.isArray(snapshot?.drafts)?snapshot.drafts:[]){if(!incoming||typeof incoming.id!=='string'||!incoming.id||typeof incoming.content!=='string'||ids.has(incoming.id)||ignored.has(incoming.source_id))continue;drafts.push(Object.fromEntries(feedbackSnapshotFields.filter(k=>typeof incoming[k]==='string').map(k=>[k,incoming[k]])));ids.add(incoming.id);changed=true;}
  if(changed&&!writeFeedbackDrafts(drafts))return false;
  const working=snapshot?.working;if(!localStorage.getItem(feedbackWorkingKey)&&typeof working?.content==='string'&&!$('#feedback-content').value){try{localStorage.setItem(feedbackWorkingKey,JSON.stringify({content:working.content,draftId:typeof working.draftId==='string'?working.draftId:'',updatedAt:typeof working.updatedAt==='string'?working.updatedAt:''}));}catch{return false;}}
  renderFeedbackDrafts();updateFeedbackSendState();return true;
}
if(typeof window!=='undefined')window.XYFeedback={exportSnapshot:exportFeedbackSnapshot,importSnapshot:importFeedbackSnapshot};

document.querySelectorAll("[data-page]").forEach(b=>b.addEventListener("click",()=>changePage(b.dataset.page)));
document.querySelectorAll("[data-prompt]").forEach(b=>b.addEventListener("click",()=>{$("#chat-input").value=b.dataset.prompt;$("#chat-input").focus();}));
document.querySelectorAll("[data-filter]").forEach(b=>b.addEventListener("click",()=>{state.filter=b.dataset.filter;document.querySelectorAll("[data-filter]").forEach(x=>x.classList.toggle("selected",x===b));renderTasks();}));
$("#chat-form").addEventListener("submit",sendMessage);
$("#chat-input").addEventListener("keydown",e=>{if(e.key==="Enter"&&!e.shiftKey&&!e.isComposing){e.preventDefault();sendMessage();}});
$("#new-task-button").addEventListener("click",()=>openTaskForm());
$("#cancel-task").addEventListener("click",()=>{$("#task-form").hidden=true;$("#task-form").reset();state.editingTaskId=null;});
$("#task-form").addEventListener("submit",saveTask);$("#settings-open").addEventListener("click",openSettings);$("#settings-close").addEventListener("click",closeSettings);$("#drawer-backdrop").addEventListener("click",closeSettings);
$("#save-settings").addEventListener("click",saveSettings);$("#refresh-connectors").addEventListener("click",loadConnectors);$("#refresh-balances").addEventListener("click",refreshBalances);
$("#shutdown-button").addEventListener("click",shutdown);$("#feedback-button").addEventListener("click",openFeedback);
$('#feedback-form').addEventListener('submit',sendFeedback);
$('#feedback-content').addEventListener('input',feedbackContentInput);
$('#feedback-save-draft').addEventListener('click',saveFeedbackDraft);
$('#feedback-new-draft').addEventListener('click',newFeedbackDraft);
$('#feedback-sync').addEventListener('click',syncFeedbackDrafts);
$('#feedback-close').addEventListener('click',()=>$('#feedback-dialog').close());
$('#feedback-copy').addEventListener('click',async()=>{try{await navigator.clipboard.writeText($('#feedback-content').value);$('#feedback-status').textContent='已复制，可以粘贴到Codex。';}catch{$('#feedback-content').select();$('#feedback-status').textContent='已选中反馈，按Ctrl+C复制。';}});
$("#export-button").addEventListener("click",exportData);
$('#diagnostics-view').addEventListener('click',()=>loadDiagnostics(false));$('#diagnostics-export').addEventListener('click',()=>loadDiagnostics(true));
document.addEventListener("keydown",event=>{if($("#settings-drawer").hidden)return;if(event.key==="Escape")closeSettings();if(event.key==="Tab"){const focusables=Array.from($("#settings-drawer").querySelectorAll("button,input,select,a[href]")).filter(e=>!e.disabled&&!e.hidden);const first=focusables[0],last=focusables.at(-1);if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus();}else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus();}}});
$("#today-label").textContent=new Date().toLocaleDateString("zh-CN",{year:"numeric",month:"long",day:"numeric",weekday:"long"});
changePage(location.hash==="#plan"?"plan":"chat");
(async()=>{try{const data=await api("/api/state");state.tasks=data.tasks||[];state.messages=data.messages||[];state.settings=data.settings||{};if(data.budget)state.settings.budget=data.budget;state.connectors=data.connectors||[];if(Array.isArray(data.feedback_drafts))importFeedbackDrafts(data.feedback_drafts);renderMessages();renderTasks();renderSettings();$("#connection-status").textContent="已连接本机服务";}catch(e){$("#connection-status").textContent="本机服务未连接";error(`连接失败：${e.message}。请确认助手服务已启动，再刷新页面。`);renderTasks();}})();


window.addEventListener("pagehide",stopReadAloud);
