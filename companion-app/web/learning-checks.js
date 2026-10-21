"use strict";
(() => {
  const area=document.querySelector('#learning-checks'), $=s=>area.querySelector(s);
  const key='xiaoxiang-learning-check-pending-v1';
  let selected=null, active=null, busy=false, pending=null, answers={};
  const verdicts={correct:'答对',incorrect:'答错',supported:'符合参考要点',needs_review:'待复习建议',uncertain:'未可靠评价'};
  function node(tag,text,cls){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;}
  function status(s){$('#check-status').textContent=s;}
  function id(){return crypto.randomUUID().replaceAll('-','');}
  function persist(){localStorage.setItem(key,JSON.stringify({pending,activeId:active?.id,answers,selected}));}
  function button(parent,text,action){const b=node('button',text,'subtle-button');b.type='button';b.onclick=()=>run(action);parent.append(b);return b;}
  async function run(action){
    if(busy)return;busy=true;area.setAttribute('aria-busy','true');
    try{await action();}catch(e){status(e.message||'本次检验操作未完成。');}
    finally{busy=false;area.removeAttribute('aria-busy');}
  }
  function providerLabel(){return window.XYLearning?.label(state.settings.learning_selection)||'正在读取学习模型';}
  function preview(){
    const box=$('#check-selection');box.replaceChildren();$('#check-topic').closest('label').hidden=!!selected;
    box.append(node('p',`当前模型：${providerLabel()}。仅发送下列所选范围；云模型可能计费。不会附带聊天、画像、进度备注或历史检验。`));
    box.append(node('p',selected?`所选任务：${selected.title}\n内容：${selected.learning.content}\n预期成果：${selected.learning.outcome}`:'自选知识点：只使用下方填写内容，不关联任务。'));
  }
  window.LearningChecks={choose(task){
    area.open=true;
    if(busy||pending){status('请先等待当前检验操作完成，或核对待处理请求。');area.scrollIntoView();return;}
    selected=task;persist();preview();run(refresh);area.scrollIntoView({block:'start'});
  }};
  function pendingView(){
    const box=$('#check-pending');box.replaceChildren();
    if(!pending)return;
    box.append(node('p','请求已固定；回执不明时仅核对同一请求，不自动再次调用模型。'));
    button(box,'核对同一请求',sendPending);
    button(box,'结束本次请求',async()=>{pending=null;persist();pendingView();render();await refresh();status('已结束请求跟踪；请先查看历史。新生成按钮会发起新的模型调用。');});
  }
  async function sendPending(){
    const result=await api(pending.path,{method:pending.method,body:JSON.stringify(pending.body)});
    pending=null;persist();pendingView();
    if(result.deleted){active=null;answers={};render();persist();}
    else {active=await api(`/api/learning/checks/${result.id}`);answers=active.answers||{};render();persist();}
    status(result.deleted?'测验已删除。':active.status==='generated'?'测验题目已生成并保存，尚未提交答案。':'结果已保存到本机；测验表现不代表真正掌握程度。');await refresh();
  }
  async function write(path,method,body){
    if(pending)throw new Error('请先核对或结束待处理请求。');
    pending={path,method,body:{...body,request_id:id()}};persist();pendingView();render();
    await sendPending();
  }
  function render(){
    const box=$('#check-current');box.replaceChildren();if(!active)return;
    box.append(node('h3',`本次检验 · ${active.scope.title}`));
    if(selected&&active.task_id!==selected.id)box.append(node('p','下方保留的是另一范围的测验与答案；新生成将使用上方所选任务。'));
    box.append(node('p',`范围：${active.scope.content}\n预期成果：${active.scope.outcome||'自选知识点'}\n生成：${active.created_at} · 题目版本 ${active.schema_version}`));
    {const info=node('details');info.append(node('summary','模型请求与返回详情'),node('p',`出题模型：${active.generation_model.provider} · 请求 ${active.generation_model.requested_model||'未知'} → 返回 ${active.generation_model.returned_model||'未知'}。题目、参考答案和范围相关性仍可人工核对。`,'muted-text'));box.append(info);}
    const submitted=active.status==='submitted',form=node('form');
    for(const q of active.questions){
      const card=node('fieldset',undefined,'learning-task');card.dataset.question=q.id;
      card.append(node('legend',`第 ${q.id} 题 · ${q.type==='choice'?'单选':'简答'}`),node('p',q.prompt),node('p',`范围依据：${q.evidence}`,'muted-text'));
      if(submitted){
        const answer=active.answers[q.id];card.append(node('p',`你的答案：${q.type==='choice'?q.options[answer]:answer}`),node('p',`参考答案：${q.type==='choice'?q.options[q.answer]:q.answer}`),node('p',`解释：${q.explanation}`));
        const result=active.results.find(r=>r.id===q.id),correction=active.corrections.filter(c=>c.question_id===q.id).at(-1);
        card.append(node('p',`原始结果：${verdicts[result.verdict]} · ${result.source==='deterministic'?'程序按固定答案判分':result.source==='model_assistance'?'模型辅助评价':'未进行可靠评价'}\n依据：${result.basis}`));
        if(result.missing)card.append(node('p',`遗漏/错误：${result.missing}\n改进方向：${result.improvement}`));
        if(correction)card.append(node('p',`用户更正：${verdicts[correction.verdict]} · ${correction.note}`));
        const details=node('details');details.append(node('summary','纠正本题评价或参考答案问题'));
        details.append(node('p','更正保留原题与原始判分，记录你的判断；不会修改客观题标准答案。'));
        const select=node('select');select.setAttribute('aria-label','更正结论');
        for(const v of ['supported','needs_review','uncertain']){const o=node('option',verdicts[v]);o.value=v;select.append(o);}details.append(select);
        const note=node('textarea');note.maxLength=1000;note.placeholder='更正原因或正确解释';note.setAttribute('aria-label','更正原因');details.append(note);
        button(details,'保存评价更正',async()=>{if(!note.value.trim())throw new Error('请填写更正原因。');await write(`/api/learning/checks/${active.id}`,'PATCH',{question_id:q.id,verdict:select.value,note:note.value});});card.append(details);
      }else if(q.type==='choice'){
        q.options.forEach((option,index)=>{const label=node('label',option,'check-option'),input=node('input');input.type='radio';input.name='q'+q.id;input.value=index;input.checked=answers[q.id]===index;input.required=true;
          input.onchange=()=>{answers[q.id]=index;persist();};label.prepend(input);card.append(label);});
      }else{
        const input=node('textarea');input.rows=3;input.maxLength=2000;input.required=true;input.value=answers[q.id]||'';input.setAttribute('aria-label',`第${q.id}题答案`);input.oninput=()=>{answers[q.id]=input.value;persist();};card.append(input);
      }
      form.append(card);
    }
    if(submitted){
      const corrections=Object.fromEntries(active.corrections.map(c=>[c.question_id,c]));
      const objective=active.results.filter(r=>r.source==='deterministic');
      box.append(node('p',`客观题：${objective.filter(r=>r.verdict==='correct').length} / ${objective.length} 答对 · 简答评价仅供核对，未计算掌握度。`));
      const review=active.results.filter(r=>corrections[r.id]?corrections[r.id].verdict!=='supported':r.review);
      box.append(node('h4','待复习建议（可更正）'));
      if(!review.length)box.append(node('p','本次未标出待复习题目；可在下次学习时自行回忆核对，不代表已经掌握。'));
      for(const r of review){const q=active.questions.find(q=>q.id===r.id);box.append(node('p',`第${r.id}题 · ${q.evidence}：${corrections[r.id]?.note||r.missing||r.basis}`));}
      box.append(node('p','下次复习建议：先回忆所选知识点，再核对上述题目与解释；无法确认的结论请查阅教材或向老师求证。不会自动改计划或新增任务。'));
      if(active.evaluation_model.status==='failed')box.append(node('p',active.evaluation_model.note));
      if(active.evaluation_model.provider){const info=node('details');info.append(node('summary','模型请求与返回详情'),node('p',`辅助评价模型：${active.evaluation_model.provider} · 请求 ${active.evaluation_model.requested_model||'未知'} → 返回 ${active.evaluation_model.returned_model||'未知'}`));box.append(info);}
    }else{
      const label=node('label',`允许将本次简答题、参考要点和我的答案发送给当前所选模型辅助评价（${providerLabel()}；可能计费，一次调用）`,'check-option'),consent=node('input');consent.type='checkbox';consent.id='check-evaluate';label.prepend(consent);form.append(label);
      const submit=node('button','提交答案并保存结果','primary-button');submit.type='submit';form.append(submit);
      form.onsubmit=e=>{e.preventDefault();run(async()=>{const body={answers:structuredClone(answers),evaluate_short:consent.checked};if(consent.checked)body.model_selection=await window.XYLearning.confirm('evaluate',body,active.id);await write(`/api/learning/checks/${active.id}/submit`,'POST',body);});};
    }
    if(pending)form.querySelectorAll('input,textarea,select,button').forEach(n=>n.disabled=true);
    box.append(form);
  }
  async function refresh(){
    const r=await api('/api/learning/checks'),box=$('#check-history');box.replaceChildren();
    if(!r.checks.length)box.append(node('p','暂无检验记录。'));
    for(const item of r.checks.filter(item=>!selected||item.task_id===selected.id)){
      const row=node('article',undefined,'learning-record');row.append(node('p',`${item.created_at} · ${item.scope.title} · ${item.status==='submitted'?'已提交':'待作答'}${item.task_id?' · 关联学习任务':' · 自选知识点'}`));
      button(row,item.status==='submitted'?'查看检验结果':'继续作答',async()=>{if(pending)throw new Error('请先核对待处理请求。');const same=active?.id===item.id;active=await api(`/api/learning/checks/${item.id}`);if(!same)answers=active.answers||{};persist();render();$('#check-current').scrollIntoView({block:'start'});});
      button(row,'删除测验记录',async()=>{if(!confirm('删除这份题目、答案、反馈与更正记录？'))return;await write(`/api/learning/checks/${item.id}`,'DELETE',{});});box.append(row);
    }
  }
  $('#check-topic-mode').onclick=()=>{if(pending){status('请先核对待处理请求。');return;}selected=null;persist();preview();run(refresh);};
  $('#check-generate').onsubmit=e=>{e.preventDefault();run(async()=>{
    const body=selected?{task_id:selected.id,scope_snapshot:{title:selected.title,content:selected.learning.content,outcome:selected.learning.outcome}}:{topic:$('#check-topic').value};body.count=Number($('#check-count').value);
    body.model_selection=await window.XYLearning.confirm('check',body);status('正在生成；失败不会自动重试或切换模型。');await write('/api/learning/checks','POST',body);
  });};
  $('#check-refresh').onclick=()=>run(refresh);
  let restoreId=null;
  try{const saved=JSON.parse(localStorage.getItem(key)||'null');if(saved){pending=saved.pending;selected=saved.selected||null;if(pending)area.open=true;answers=saved.answers||{};restoreId=saved.activeId;}}catch{status('本机待处理请求无法恢复，请先查看历史。');}
  window.addEventListener('learning-model-changed',()=>{preview();render();});
  preview();pendingView();window.addEventListener('learning-open',()=>run(async()=>{preview();await refresh();}));
  if(restoreId||location.hash==='#learning')run(async()=>{await refresh();if(restoreId){active=await api(`/api/learning/checks/${restoreId}`);render();}});
})();
