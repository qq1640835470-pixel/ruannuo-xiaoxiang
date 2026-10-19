"use strict";
(() => {
  const root=document.querySelector('#learning-page');
  const $=s=>root.querySelector(s);
  const storageKey='xiaoxiang-learning-draft-v1';
  const labels={course:'课程',scope:'学习范围（具体章节或主题）',start_date:'开始日期',deadline:'截止日期',daily_minutes:'每天可用分钟',level:'当前基础（不清楚可填“尚不清楚”）'};
  const kinds={study:'学习',review:'复习',practice:'练习'};
  const statuses={pending:'待开始',active:'进行中',paused:'暂停',deferred:'已延期',done:'完成',cancelled:'取消'};
  let draft=null, busy=false, pendingRecord=null, focusTaskId=null, pendingTask=null;
  function node(tag,text,cls){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;}
  function message(text){$('#learning-status').textContent=text;}
  function persist(){
    try{localStorage.setItem(storageKey,JSON.stringify({draft,request:$('#learning-request').value,requirements:readRequirements(),pendingRecord,pendingTask}));}
    catch{message('浏览器未能保存草稿副本，请保持页面开启。');}
  }
  function field(parent,label,value,type='text',oninput=()=>{},max=500){
    const wrap=node('label',label),input=node(type==='textarea'?'textarea':'input');
    if(type!=='textarea')input.type=type;else input.rows=2;
    input.value=value??'';input.required=true;input.maxLength=max;
    if(type==='number'){input.min=1;input.max=720;input.step=1;}
    input.addEventListener('input',()=>{oninput(type==='number'?Number(input.value):input.value);persist();});
    wrap.append(input);parent.append(wrap);return input;
  }
  function requirementsFields(values={}){
    $('#learning-fields').replaceChildren();
    for(const [key,label] of Object.entries(labels)){
      const input=field($('#learning-fields'),label,values[key],key.includes('date')||key==='deadline'?'date':key==='daily_minutes'?'number':key==='scope'?'textarea':'text',()=>{});
      input.name=key;if(key==='daily_minutes')input.max=720;
    }
  }
  function readRequirements(){return Object.fromEntries(Object.keys(labels).map(k=>[k,k==='daily_minutes'?Number($(`[name="${k}"]`).value):$(`[name="${k}"]`).value]));}
  async function run(action){
    if(busy)return;busy=true;
    root.setAttribute('aria-busy','true');root.querySelectorAll('button').forEach(b=>b.disabled=true);
    try{await action();}catch(e){message(e.message||'本次操作未完成。');$('#learning-status').scrollIntoView({block:'center'});}
    finally{busy=false;root.removeAttribute('aria-busy');root.querySelectorAll('button').forEach(b=>b.disabled=false);if(draft?.uncertain)$('#learning-draft').querySelectorAll('input,textarea,select,button[type=button]').forEach(n=>n.disabled=true);}
  }
  function newRequest(){return crypto.randomUUID().replaceAll('-','');}
  function touch(){draft.request_id=newRequest();draft.uncertain=false;persist();}
  function select(parent,label,values,value,change){
    const wrap=node('label',label),s=node('select');for(const [k,v] of Object.entries(values)){const o=node('option',v);o.value=k;s.append(o);}s.value=value;s.onchange=()=>{change(s.value);persist();};wrap.append(s);parent.append(wrap);return s;
  }
  function button(parent,label,handler,cls='subtle-button'){
    const b=node('button',label,cls);b.type='button';b.onclick=()=>run(handler);parent.append(b);return b;
  }
  function editor(){
    const area=$('#learning-draft');area.replaceChildren();area.hidden=!draft;if(!draft)return;
    area.append(node('h3',draft.goal_id?'修改已保存计划':'计划草稿 · 尚未保存'));
    area.append(node('p','移除已有任务会将其取消并保留历史；编辑保留任务状态和学习记录。','muted-text'));
    if(draft.uncertain)area.append(node('p','上次保存回执待核对。草稿已锁定，请重试确认保存以取得同一请求回执。'));
    if(draft.model)area.append(node('p',`生成模型：${draft.model.provider} / ${draft.model.returned_model||draft.model.requested_model}`,'muted-text'));
    const form=node('form'),grid=node('div',undefined,'learning-grid');form.append(grid);
    field(grid,'目标名称',draft.plan.title,'text',v=>{draft.plan.title=v;touch();},200);
    field(grid,'预期成果',draft.plan.outcome,'textarea',v=>{draft.plan.outcome=v;touch();});
    for(const [key,label] of Object.entries(labels))field(grid,label,draft.plan.requirements[key],key.includes('date')||key==='deadline'?'date':key==='daily_minutes'?'number':key==='scope'?'textarea':'text',v=>{draft.plan.requirements[key]=v;touch();});
    draft.plan.tasks.forEach((task,index)=>{
      const card=node('fieldset',undefined,'learning-task');card.append(node('legend',`任务 ${index+1}`));
      const g=node('div',undefined,'learning-grid');card.append(g);
      for(const [key,label,type,max] of [['title','任务名称','text',200],['date','日期','date',20],['minutes','建议分钟','number',10],['content','学习内容','textarea',500],['outcome','预期成果','textarea',500]])field(g,label,task[key],type,v=>{task[key]=v;touch();},max);
      select(g,'任务类型',kinds,task.kind,v=>{task.kind=v;touch();});
      button(card,'移除此项',async()=>{draft.plan.tasks.splice(index,1);touch();editor();});form.append(card);
    });
    const actions=node('div',undefined,'learning-actions');
    button(actions,'增加任务',async()=>{draft.plan.tasks.push({title:'',content:'',date:draft.plan.requirements.start_date,minutes:30,outcome:'',kind:'study'});touch();editor();});
    button(actions,'取消草稿',async()=>{draft=null;persist();editor();message('草稿已取消，正式目标和任务未改变。');});
    const save=node('button','确认保存','primary-button');save.type='submit';actions.append(save);form.append(actions);area.append(form);
    if(draft.uncertain){form.querySelectorAll('input,textarea,select,button[type=button]').forEach(n=>n.disabled=true);}
    form.onsubmit=e=>{e.preventDefault();run(async()=>{
      draft.uncertain=true;persist();message('正在保存，请等待回执…');
      try{
        const response=await api('/api/learning/confirm',{method:'POST',body:JSON.stringify({request_id:draft.request_id,plan:draft.plan,...(draft.goal_id?{goal_id:draft.goal_id,revision:draft.revision}:{})})});
        if(!response.ok||response.deleted)throw new Error('保存回执对应的目标已删除，请刷新核对。');
      }catch(e){if(draft){draft.uncertain=!e.responseData;persist();editor();}throw new Error(e.message+' 若回执不明，请保持草稿内容，重试同一保存以核对；修改内容前先刷新已保存计划。');}
      draft=null;persist();editor();message('计划已保存。');
      try{await refresh();}catch(e){throw new Error('计划已保存，但列表刷新失败：'+e.message);}
    });};
  }
  function progressView(card,task){
    const history=node('details');history.append(node('summary',`学习记录（${task.progress.length}）`));
    for(const p of task.progress){
      const row=node('div',undefined,'learning-record');row.append(node('p',`${p.recorded_at} · ${p.minutes??'未填'} 分钟 · ${p.note||'无备注'}`));
      button(row,'更正此记录',async()=>{
        const form=node('form');field(form,'实际分钟',p.minutes??'','number',()=>{});const min=form.querySelector('input');min.required=false;min.min=0;min.max=1000000;
        const note=field(form,'收获与困难',p.note,'textarea',()=>{},2000);note.required=false;
        const save=node('button','保存更正','primary-button');form.append(save);row.replaceChildren(form);
        form.onsubmit=e=>{e.preventDefault();run(async()=>{await api(`/api/progress/${p.id}`,{method:'PATCH',body:JSON.stringify({minutes:min.value===''?null:Number(min.value),note:note.value,request_id:newRequest()})});message('学习记录已更正。');await refresh();});};
      });history.append(row);
    }card.append(history);
    const form=node('form',undefined,'learning-progress');
    const minutes=field(form,'本次实际分钟（可留空）','','number',()=>{});minutes.required=false;minutes.min=0;minutes.max=1000000;
    const note=field(form,'本次收获与困难','','textarea',()=>{},2000);note.required=false;
    const save=node('button','记录本次学习','subtle-button');form.append(save);card.append(form);
    form.onsubmit=e=>{e.preventDefault();run(async()=>{
      const payload={minutes:minutes.value===''?null:Number(minutes.value),note:note.value};
      if(!payload.note&&!minutes.value)throw new Error('请填写实际分钟或学习备注。');
      const signature=JSON.stringify([task.id,payload]);
      if(pendingRecord&&pendingRecord.signature!==signature)throw new Error('上一条记录回执待核对，请先重试待核记录。');
      pendingRecord=pendingRecord||{signature,task_id:task.id,body:{...payload,request_id:newRequest()}};persist();
      await sendPending();
    });};
  }
  async function sendPending(){
    await api(`/api/tasks/${pendingRecord.task_id}/progress`,{method:'POST',body:JSON.stringify(pendingRecord.body)});
    pendingRecord=null;persist();message('学习记录已保存。');await refresh();
  }
  async function changeTask(task,status){
    if(pendingTask&&(pendingTask.id!==task.id||pendingTask.status!==status))throw new Error('请先核对上一项待处理任务状态。');
    message('正在核对任务状态…');
    let current=await api(`/api/tasks/${task.id}`);
    if(current.status!==status){
      pendingTask=pendingTask||{id:task.id,status,request_id:newRequest()};persist();
      const receipt=await api(`/api/tasks/${task.id}`,{method:'PATCH',body:JSON.stringify({status,request_id:pendingTask.request_id})});
      if(!receipt.ok||receipt.task?.id!==task.id||receipt.task.status!==status)throw new Error('未取得有效任务状态回执，请刷新核对。');
      current=await api(`/api/tasks/${task.id}`);
      if(current.status!==status)throw new Error('任务当前状态已变化，请刷新核对。');
      message(`任务状态已保存并核对：“${current.title}”${statuses[status]}。`);
    }else message(`“${current.title}”已经是${statuses[status]}，未重复写入。`);
    pendingTask=null;persist();focusTaskId=task.id;await refresh();
    if(status==='active')$('#learning-current').scrollIntoView({block:'start'});
  }
  async function refresh(){
    const response=await api('/api/learning/plans');const area=$('#learning-plans');area.replaceChildren();
    if(pendingRecord)button(area,'重试待核学习记录',sendPending);
    if(!response.plans.length)area.append(node('p','还没有已保存的学习计划。'));
    const currentArea=$('#learning-current');currentArea.replaceChildren();
    const studying=response.plans.flatMap(p=>p.tasks).filter(t=>t.status==='active');
    currentArea.hidden=!studying.length;
    if(studying.length){currentArea.append(node('h3','当前正在学习'));for(const task of studying){currentArea.append(node('p',task.title));button(currentArea,'完成本次任务',()=>changeTask(task,'done'));button(currentArea,'暂停学习',()=>changeTask(task,'paused'));button(currentArea,'记录学习收获与实际分钟',async()=>{focusTaskId=task.id;await refresh();root.querySelector(`[data-task-id="${CSS.escape(task.id)}"] .learning-progress textarea`)?.focus();});}}
    if(pendingTask)button(currentArea,'核对待处理任务状态',()=>changeTask({id:pendingTask.id},pendingTask.status));
    if(pendingTask){currentArea.hidden=false;button(currentArea,'结束任务状态跟踪',async()=>{pendingTask=null;persist();message('已结束跟踪，请先刷新核对任务状态；未改动任务。');await refresh();});}
    const today=new Date().toLocaleDateString('sv-SE');
    for(const saved of response.plans){
      const box=node('article',undefined,'learning-plan');box.dataset.goalId=saved.goal.id;
      box.append(node('h3',`${saved.goal.title} · ${statuses[saved.goal.status]||saved.goal.status}`));
      box.append(node('p',`${saved.requirements.course} · ${saved.requirements.scope} · 截止 ${saved.goal.deadline}`));
      box.append(node('p',`预期成果：${saved.outcome}`));
      const live=saved.tasks.filter(t=>t.status!=='cancelled');
      box.append(node('p',`完成 ${live.filter(t=>t.status==='done').length} / ${live.length} 项 · 累计实际 ${saved.tasks.reduce((n,t)=>n+t.actual_minutes,0)} 分钟 · 掌握程度尚未评估`));
      button(box,'编辑此计划',async()=>{
        if(draft)throw new Error('请先保存或取消当前草稿。');
        draft={goal_id:saved.goal.id,revision:saved.revision,request_id:newRequest(),plan:{title:saved.goal.title,requirements:saved.requirements,outcome:saved.outcome,tasks:live.map(t=>({id:t.id,title:t.title,date:t.scheduled_at.slice(0,10),...Object.fromEntries(['content','minutes','outcome','kind'].map(k=>[k,t.learning[k]]))}))}};persist();editor();$('#learning-draft').scrollIntoView({block:'start'});
      });
      button(box,'调整学习计划',async()=>{await window.LearningAdjustments?.open(saved.goal.id);});
      for(const [label,filter] of [['今日与逾期任务',t=>t.scheduled_at.slice(0,10)<=today&&!['done','cancelled'].includes(t.status)],['后续任务',t=>t.scheduled_at.slice(0,10)>today&&!['done','cancelled'].includes(t.status)],['已完成与取消',t=>['done','cancelled'].includes(t.status)]]){
        const group=node('details');group.open=label!=='已完成与取消';group.append(node('summary',label));
        const tasks=saved.tasks.filter(filter).sort((a,b)=>a.scheduled_at.localeCompare(b.scheduled_at));
        if(!tasks.length)group.append(node('p','暂无任务','muted-text'));
        for(const task of tasks){
          const card=node('article',undefined,'learning-task');card.dataset.taskId=task.id;card.classList.toggle('is-active',task.status==='active');
          card.append(node('h4',task.title),node('p',`${task.scheduled_at.slice(0,10)} · ${statuses[task.status]} · ${kinds[task.learning.kind]} · 建议 ${task.learning.minutes} / 实际 ${task.actual_minutes} 分钟`),node('p',task.learning.content),node('p',`预期成果：${task.learning.outcome}`));
          const actions=node('div',undefined,'learning-actions');
          for(const [status,label] of [['active','开始'],['done','完成'],['paused','暂停'],['cancelled','取消任务']]){const b=button(actions,label,async()=>{b.textContent=status==='active'?'正在开始…':'正在保存…';try{await changeTask(task,status);}finally{b.textContent=label;}});}
          card.append(actions);
          button(card,'检验学习成果',async()=>{window.LearningChecks?.choose(task);});
          const defer=node('form',undefined,'learning-actions'),when=field(defer,'延期至',task.scheduled_at.slice(0,10),'date');const b=node('button','延期','subtle-button');defer.append(b);card.append(defer);
          defer.onsubmit=e=>{e.preventDefault();run(async()=>{await api(`/api/tasks/${task.id}`,{method:'PATCH',body:JSON.stringify({status:'deferred',scheduled_at:when.value,request_id:newRequest()})});message('延期已保存。');await refresh();});};
          progressView(card,task);group.append(card);
        }box.append(group);
      }area.append(box);
    }
    if(focusTaskId){const target=root.querySelector(`[data-task-id="${CSS.escape(focusTaskId)}"]`);focusTaskId=null;if(target){const group=target.closest('details');if(group)group.open=true;target.tabIndex=-1;target.focus();target.scrollIntoView({block:'center'});}}
    window.dispatchEvent(new Event('learning-state-refreshed'));
  }
  $('#learning-input').onsubmit=e=>{e.preventDefault();run(async()=>{
    if(draft)throw new Error('请先保存或取消当前草稿。');
    message('正在分析学习需求…');const r=await api('/api/learning/generate',{method:'POST',body:JSON.stringify({stage:'analyze',text:$('#learning-request').value})});
    requirementsFields(r.requirements);$('#learning-questions').textContent=r.questions.join('；')||'请核对提取结果，特别是范围、截止日期与当前基础。';persist();message('需求分析完成，请补充并核对下列信息。');
  });};
  $('#learning-requirements').onsubmit=e=>{e.preventDefault();run(async()=>{
    if(draft)throw new Error('请先保存或取消当前草稿。');
    message('正在生成计划草稿…');const r=await api('/api/learning/generate',{method:'POST',body:JSON.stringify({stage:'plan',requirements:readRequirements()})});
    draft={plan:r.plan,model:r.model,request_id:newRequest()};persist();editor();message('草稿已生成，请编辑并确认保存。');
  });};
  window.addEventListener('learning-task-focus',event=>{focusTaskId=event.detail.task_id;run(refresh);});
  $('#learning-refresh').onclick=()=>run(refresh);
  $('#learning-request').addEventListener('input',persist);
  requirementsFields();
  try{const stored=JSON.parse(localStorage.getItem(storageKey)||'null');if(stored){draft=stored.draft;pendingRecord=stored.pendingRecord;pendingTask=stored.pendingTask;$('#learning-request').value=stored.request||'';requirementsFields(stored.requirements||{});}}catch{message('本机草稿无法恢复，请重新填写。');}
  editor();window.addEventListener('learning-open',()=>run(refresh));
  if(location.hash==='#learning')changePage('learning');
})();
