"use strict";
(() => {
  const root=document.querySelector('#learning-adjustments'), $=s=>root.querySelector(s),storage='xiaoxiang-learning-adjustment-v1';
  let context=null,view=null,draft=null,changes=[],pending=null,busy=false;
  const actionNames={update:'调整日期/时长或内容',add:'新增任务',cancel:'取消并保留历史'};
  function node(tag,text,cls){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;}
  function status(text){$('#adjustment-status').textContent=text;}
  function requestId(){return crypto.randomUUID().replaceAll('-','');}
  function persist(){localStorage.setItem(storage,JSON.stringify({draftId:draft?.id,changes,pending,goalId:context?.goal_id||draft?.goal_id}));}
  async function run(action){if(busy)return;busy=true;root.setAttribute('aria-busy','true');try{await action();}catch(e){status(e.message||'本次调整未完成。');}finally{busy=false;root.removeAttribute('aria-busy');}}
  function button(parent,text,action){const b=node('button',text,'subtle-button');b.type='button';b.onclick=()=>run(action);parent.append(b);return b;}
  function check(parent,text,value=false){const label=node('label',text,'check-option'),input=node('input');input.type='checkbox';input.checked=value;label.prepend(input);parent.append(label);return input;}
  function input(parent,label,value,type,max,change){const wrap=node('label',label),n=node(type==='textarea'?'textarea':'input');if(type!=='textarea')n.type=type;n.value=value??'';n.maxLength=max;n.required=true;if(type==='number'){n.min=1;n.max=720;n.step=1;}n.oninput=()=>{change(type==='number'?Number(n.value):n.value);persist();compare();};wrap.append(n);parent.append(wrap);return n;}
  function invalidate(){view=null;$('#adjustment-preview').replaceChildren();}
  window.addEventListener('learning-model-changed',()=>{if(view){invalidate();status('学习模型已变化，请重新预览并确认。');}});
  function selectionForm(){
    const box=$('#adjustment-selection');box.replaceChildren();if(!context||draft)return;
    box.append(node('h4',`调整目标：${context.original.title}`),node('p','本版在原计划日期与每日预算内调整；已完成项锁定，已有计划允许休息日。'));
    const form=node('form'),plan=check(form,'选择当前目标、原计划安排与完成标记（调整必需）'),remaining=check(form,'另包含待开始、进行中、暂停及延期任务的详细状态');plan.required=true;
    const progress=node('fieldset');progress.append(node('legend','实际学习记录（最多50条；用户自报/自评，默认不选）'));
    const pInputs=context.progress.map(p=>({id:p.id,input:check(progress,`${p.recorded_at} · ${p.minutes??'未填'}分钟 · ${context.original.tasks.find(t=>t.id===p.task_id)?.title||p.task_id}`)}));form.append(progress);
    const checks=node('fieldset');checks.append(node('legend','已提交测验（最多20条；默认不选，仅列本计划）'));
    const cInputs=context.checks.map(c=>({id:c.id,input:check(checks,`${c.created_at} · ${context.original.tasks.find(t=>t.id===c.task_id)?.title||c.task_id} · ${c.id.slice(0,8)}`)}));form.append(checks);
    const label=node('label','主动补充的调整要求（可留空）'),note=node('textarea');note.maxLength=2000;note.rows=3;note.id='adjustment-note';label.append(note);form.append(label);
    const submit=node('button','预览将发送的所选资料','subtle-button');submit.type='submit';form.append(submit);box.append(form);
    form.addEventListener('input',invalidate);form.addEventListener('change',invalidate);
    form.onsubmit=e=>{e.preventDefault();run(async()=>{
      if(pending)throw new Error('请先核对待处理请求。');
      const selection={goal_id:context.goal_id,revision:context.revision,include_plan:plan.checked,include_remaining:remaining.checked,progress_ids:pInputs.filter(p=>p.input.checked).map(p=>p.id),check_ids:cInputs.filter(c=>c.input.checked).map(c=>c.id),note:note.value};
      view=await api('/api/learning/adjustments/preview',{method:'POST',body:JSON.stringify({selection})});view.selection=selection;preview();status('仅完成资料预览，尚未调用模型或修改计划。');
    });};
  }
  function preview(){
    const box=$('#adjustment-preview');box.replaceChildren();if(!view)return;
    box.append(node('h4','将发送的信息'),node('p',`提供方：${view.model.provider} / ${view.model.model}。云模型可能计费；仅发送下列资料，无聊天或画像。`));
    box.append(node('p',`目标：${view.payload.plan.title}\n课程与范围：${view.payload.plan.requirements.course} · ${view.payload.plan.requirements.scope}\n原安排：${view.payload.plan.tasks.length}项任务；选择${view.payload.progress.length}条实际学习记录、${view.payload.checks.length}份测验。\n补充要求：${view.payload.user_request||'无'}`));
    for(const p of view.payload.progress)box.append(node('p',`所选学习记录（用户自报）：${p.minutes??'未填'}分钟 · ${p.note||'无备注'}`));
    for(const c of view.payload.checks)box.append(node('p',`所选测验：${c.scope.title} · ${c.submitted_at} · ${c.results.length}题反馈、${c.corrections.length}条人工更正；含本份题目、答案与解释。`));
    const details=node('details');details.append(node('summary','展开核对完整发送内容'),node('pre',JSON.stringify(view.payload,null,2)));box.append(details);
    const form=node('form'),consent=check(form,'我已核对这些资料及提供方，允许本次分析并生成调整草稿（云模型可能计费）');consent.required=true;
    const submit=node('button','确认资料并生成调整草稿','primary-button');submit.type='submit';form.append(submit);box.append(form);
    form.onsubmit=e=>{e.preventDefault();run(async()=>{
      if(!consent.checked)throw new Error('请先确认发送内容。');
      await write('/api/learning/adjustments/generate',{request_id:requestId(),selection:view.selection,preview_hash:view.preview_hash,model:view.model,confirmed:true},'generate');
    });};
  }
  function taskText(t){return `${t.title}\n${t.date} · ${t.minutes}分钟 · ${{study:'学习',review:'复习',practice:'练习'}[t.kind]}\n内容：${t.content}\n成果：${t.outcome}`;}
  function referenceLabel(ref){
    const [kind,id]=ref.split(':');
    if(kind==='plan')return '原任务：'+(draft?.original.tasks||context?.original.tasks||[]).find(t=>t.id===id)?.title;
    if(kind==='progress')return '所选学习记录：'+(draft?.evidence.progress.find(p=>p.id===id)?.recorded_at||id.slice(0,8));
    if(kind==='check')return '所选测验：'+(draft?.evidence.checks.find(c=>c.id===id)?.scope.title||id.slice(0,8));
    return '用户补充要求';
  }
  function compare(){
    const box=$('#adjustment-comparison');if(!box||!draft)return;box.replaceChildren();
    const table=node('table',undefined,'adjustment-comparison'),head=node('tr');for(const label of ['原计划','建议/编辑后','主要原因与依据'])head.append(node('th',label));table.append(head);
    for(const t of draft.original.tasks){
      const change=changes.find(c=>c.task_id===t.id),row=node('tr');row.append(node('td',taskText(t)));
      row.append(node('td',change?(change.action==='cancel'?'建议取消，保留历史':taskText(change.task)):`保持不变${t.status==='done'?'（已完成，锁定）':t.status==='cancelled'?'（已取消历史）':''}`));
      row.append(node('td',change?`${actionNames[change.action]}\n${change.reason}\n依据：${change.evidence.map(referenceLabel).join('、')}`:'原安排保留'));table.append(row);
    }
    for(const c of changes.filter(c=>c.action==='add')){const row=node('tr');row.append(node('td','原无此任务'),node('td',taskText(c.task)),node('td',`建议新增\n${c.reason}\n依据：${c.evidence.map(referenceLabel).join('、')}`));table.append(row);}
    table.querySelectorAll('td').forEach(td=>td.dataset.label=['原计划','建议/编辑后','主要原因与依据'][td.cellIndex]);box.append(table);
  }
  function editor(){
    const box=$('#adjustment-draft');box.replaceChildren();if(!draft)return;
    if(draft.state!=='draft'){box.append(node('p',draft.state==='confirmed'?'此调整已实际保存，可查看下方确认记录。':'此调整未形成有效草稿或已取消。'));return;}
    box.append(node('h4','调整草稿 · 尚未保存'),node('p',`模型建议：${draft.proposal.summary}`),node('p',`生成模型：${draft.model.provider} · 请求 ${draft.model.requested_model||'未知'} → 返回 ${draft.model.returned_model||'未知'}`));
    box.append(node('div',undefined));box.lastChild.id='adjustment-comparison';compare();
    const form=node('form'),lock=node('fieldset');lock.disabled=Boolean(pending);lock.style.minWidth='0';form.append(lock);
    changes.forEach((c,index)=>{
      const field=node('fieldset',undefined,'learning-task');field.dataset.change=index;field.append(node('legend',`建议${index+1} · ${actionNames[c.action]}`));
      if(c.task){
        for(const [k,label,type,max] of [['title','任务名称','text',200],['date','日期','date',10],['minutes','建议分钟','number',4],['content','学习内容','textarea',500],['outcome','预期成果','textarea',500]])input(field,label,c.task[k],type,max,v=>c.task[k]=v);
        const select=node('select');select.setAttribute('aria-label','任务类型');for(const [value,text] of [['study','学习'],['review','复习'],['practice','练习']]){const o=node('option',text);o.value=value;select.append(o);}select.value=c.task.kind;select.onchange=()=>{c.task.kind=select.value;persist();compare();};field.append(select);
      }
      input(field,'调整原因',c.reason,'textarea',800,v=>c.reason=v);
      field.append(node('p',`依据：${c.evidence.map(referenceLabel).join('、')}`));
      button(field,'移除此项建议（保留原任务）',async()=>{changes.splice(index,1);persist();editor();});lock.append(field);
    });
    button(lock,'增加建议任务',async()=>{const first=draft.original.tasks.find(t=>!['done','cancelled'].includes(t.status))||draft.original.tasks[0];changes.push({action:'add',task_id:'',task:{title:'',content:'',date:draft.evidence.today,minutes:20,outcome:'',kind:'review'},reason:'',evidence:['plan:'+first.id]});persist();editor();});
    button(lock,'取消调整草稿',async()=>{
      await api(`/api/learning/adjustments/${draft.id}/cancel`,{method:'POST',body:'{}'});draft=null;changes=[];persist();editor();selectionForm();status('调整草稿已取消，正式目标、任务及记录未改变。');
    });
    const save=node('button','确认保存调整','primary-button');save.type='submit';lock.append(save);box.append(form);
    form.onsubmit=e=>{e.preventDefault();run(async()=>{await write('/api/learning/adjustments/confirm',{request_id:requestId(),adjustment_id:draft.id,changes:structuredClone(changes)},'save');});};
  }
  function pendingView(){
    const box=$('#adjustment-pending');box.replaceChildren();if(!pending)return;
    box.append(node('p','请求回执待核；内容已固定，请核对同一请求。不会自动重复调用模型或保存修改。'));
    button(box,'核对同一调整请求',sendPending);
    if(pending.kind==='generate')button(box,'结束生成请求跟踪',async()=>{pending=null;persist();pendingView();status('已结束跟踪；原请求不会自动再次调用模型。重新生成是一次新请求。');});
  }
  async function write(path,body,kind){
    if(pending)throw new Error('请先核对待处理请求。');pending={path,body,kind};persist();pendingView();editor();await sendPending();
  }
  async function sendPending(){
    const kind=pending.kind;let response;
    try{response=await api(pending.path,{method:'POST',body:JSON.stringify(pending.body)});}
    catch(e){if(e.responseData){pending=null;persist();pendingView();editor();}throw e;}
    if(kind==='generate'){
      draft=response;changes=structuredClone(response.proposal.changes||[]);pending=null;persist();pendingView();$('#adjustment-preview').replaceChildren();$('#adjustment-selection').replaceChildren();editor();status(response.state==='confirmed'?'此调整已实际保存，请核对已确认记录。':'已生成调整建议，尚未实际保存；请比较并修改。');
    }else{
      pending=null;draft=null;changes=[];persist();pendingView();editor();
      if(response.deleted)throw new Error('原目标已删除，请刷新核对。');
      status(response.summary);await history();window.dispatchEvent(new Event('learning-open'));
    }
  }
  async function history(){
    const goalId=context?.goal_id||draft?.goal_id;if(!goalId)return;
    const r=await api(`/api/learning/adjustments?goal_id=${encodeURIComponent(goalId)}`),box=$('#adjustment-history');box.replaceChildren();
    if(!r.adjustments.length)box.append(node('p','暂无已确认的调整。'));
    for(const item of r.adjustments){const d=node('details');d.append(node('summary',`${item.confirmed_at} · ${item.summary}`));for(const c of item.changes)d.append(node('p',`${actionNames[c.action]}：${c.task?.title||c.task_id}\n${c.reason}\n依据：${c.evidence.join('、')}`));box.append(d);}
  }
  window.LearningAdjustments={async open(goalId){
    root.hidden=false;root.scrollIntoView({block:'start'});
    if(pending||draft?.state==='draft'){status('请先核对待处理请求，或保存/取消当前调整草稿。');return;}
    await run(async()=>{context=await api(`/api/learning/adjustments/options?goal_id=${encodeURIComponent(goalId)}`);draft=null;view=null;changes=[];persist();selectionForm();preview();editor();await history();status('请选择本次分析依据；未选中的记录正文不会发送。');});
  }};
  try{
    const saved=JSON.parse(localStorage.getItem(storage)||'null');if(saved&&(saved.draftId||saved.pending)){
      pending=saved.pending;changes=saved.changes||[];root.hidden=false;pendingView();
      run(async()=>{if(saved.goalId)context=await api(`/api/learning/adjustments/options?goal_id=${encodeURIComponent(saved.goalId)}`);if(saved.draftId)draft=await api(`/api/learning/adjustments/${saved.draftId}`);selectionForm();editor();await history();});
    }
  }catch{status('无法恢复本机调整草稿，请重新打开原计划核对。');}
})();
