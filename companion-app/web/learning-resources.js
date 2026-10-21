"use strict";
(() => {
  const root=document.getElementById('learning-resources');
  const $=id=>document.getElementById('resources-'+id);
  const kinds={video:'视频',text:'教材/讲义',practice:'练习题'},key='xiaoxiang-learning-resources-v1';
  let busy=false,pending=null,search=null,preview=null,taskId="";
  function node(tag,text){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n;}
  function status(text){
    const id=pending?.body.request_id||search?.request_id;
    $('status').textContent=id?text.replaceAll(id,'（详情见请求记录）'):text;
    const details=$('receipt-details');details.replaceChildren(node('summary','请求与回执记录'));
    if(id)details.append(node('p',`完整请求 ID：${id}`));
  }
  function requirements(){return {course:$('course').value.trim(),topic:$('topic').value.trim(),level:$('level').value.trim(),kinds:Object.keys(kinds).filter(k=>$(k).checked)};}
  function fill(req){for(const k of ['course','topic','level'])$(k).value=req[k]||'';for(const k of Object.keys(kinds))$(k).checked=req.kinds?.includes(k)||false;}
  function persist(){try{localStorage.setItem(key,JSON.stringify({text:$('request').value,requirements:requirements(),pending,searchId:search?.request_id,taskId:$('task').value||taskId}));}catch{status('浏览器未能保存恢复标记，请保持页面开启并记录请求编号。');}}
  function controls(){
    root.querySelectorAll('button,input,textarea,select').forEach(n=>n.disabled=busy||!!pending);
    $('recover').hidden=!pending;$('dismiss').hidden=!pending;
    $('recover').disabled=busy;$('dismiss').disabled=busy;
    $('save').disabled=busy||!!pending||!search?.result?.results?.length;
  }
  async function run(action,allowPending=false){if(busy)return;if(pending&&!allowPending){status('请先核对原请求回执，或明确放弃本地标记；未发送新请求。');controls();return;}busy=true;controls();root.setAttribute('aria-busy','true');try{await action();}catch(e){status(e.message||'操作未完成，请核对原回执。');}finally{busy=false;root.removeAttribute('aria-busy');controls();}}
  function clearPreview(){preview=null;$('preview').hidden=true;$('preview').replaceChildren();}
  function link(row){
    const a=node('a',row.title);const u=new URL(row.url);
    if(!['https:','http:'].includes(u.protocol))throw Error('资源链接无效。');
    a.href=u.href;a.target='_blank';a.rel='noopener noreferrer';a.referrerPolicy='no-referrer';return a;
  }
  function card(row,choose=false){
    const c=node('article');c.className='resource-card';
    if(choose){const label=node('label');label.className='check-option';const box=node('input');box.type='checkbox';box.value=row.id;box.className='resource-choice';label.append(box,node('span','选择保存'));c.append(label);}
    c.append(link(row),node('p',`${row.source} · ${kinds[row.kind]||'类型未知'} · 搜索时间 ${row.searched_at}`));
    c.append(node('p','搜索摘录：'+(row.snippet||'无摘录')),node('p','推荐依据：'+row.reason));
    c.append(node('p','搜索词：'+row.query));
    c.append(node('p',`难度：${row.difficulty}；${row.difficulty_confidence}。原文未读取；${row.accessibility}。`));
    if(row.tasks?.length)c.append(node('p','已关联：'+row.tasks.map(t=>t.title).join('、')));
    return c;
  }
  function showSearch(response){
    search=response;$('results').replaceChildren();const data=response.result;
    if(!data)return;
    for(const row of data.results)$('results').append(card(row,true));
    const errors=data.errors.map(e=>e.detail).join(' ');
    status(`${data.status==='empty'?'没有找到符合条件的资源。':data.status==='unavailable'?'本次搜索未取得有效结果。':`找到 ${data.results.length} 条资源。`} ${errors} ${data.missing_kinds.length?'未找到：'+data.missing_kinds.join('、')+'。':''} 供应商已报告用量 ${data.credits_reported} credits${data.usage_uncertain?'，另有用量待核对':''}。${data.note}`);
    persist();
  }
  async function refresh(){
    const [saved,plans]=await Promise.all([api('/api/learning/resources'),api('/api/learning/plans')]);
    $('saved').replaceChildren(node('h4',`已保存资源（最近100条，当前 ${saved.resources.length} 条）`));
    if(!saved.resources.length)$('saved').append(node('p','还没有保存资源。'));
    for(const row of saved.resources)$('saved').append(card(row));
    const old=taskId||$('task').value;$('task').replaceChildren(new Option('独立保存，不关联任务',''));
    for(const plan of plans.plans)for(const task of plan.tasks)if(task.status!=='cancelled')$('task').add(new Option(`${plan.goal.title} · ${task.title}`,task.id));
    if([...$('task').options].some(o=>o.value===old))$('task').value=old;taskId=$('task').value;
  }
  async function accept(response,path){
    if(response.state==='pending'){status(`请求 ${pending?.body.request_id||response.request_id} 尚未完成或已中断，不会重发。`);return;}
    pending=null;persist();
    if(response.state==='failed')throw Error(response.detail);
    if(path.endsWith('/analyze')){fill(response.result.requirements);clearPreview();persist();status(`需求已整理，请核对。请求模型 ${response.result.model.requested_model||'未知'} → 返回 ${response.result.model.returned_model||'未知'}；尚未搜索。`);}
    else if(path.endsWith('/search'))showSearch(response);
    else {window.dispatchEvent(new Event('learning-resources-saved'));status(`资源已保存：选择 ${response.saved} 条，新增 ${response.added} 条${response.task_id?'，已关联所选任务':''}。`);try{await refresh();}catch(e){throw Error('资源已保存，但列表刷新失败：'+e.message);}}
  }
  async function send(path,body){
    if(path.endsWith('/search')){search=null;$('results').replaceChildren();}
    pending={path,body:{request_id:crypto.randomUUID().replaceAll('-',''),...body}};persist();controls();
    status('正在处理，请等待回执；断网不会自动重试。');
    try{const response=await api(path,{method:'POST',body:JSON.stringify(pending.body)});await accept(response,path);}
    catch(e){if(pending)status(`回执待核对，请求 ${pending.body.request_id}。${e.message} 使用“核对原请求回执”，不会重发。`);else throw e;}
  }
  $('analyze').onclick=()=>run(async()=>{
    const text=$('request').value.trim();if(!text)throw Error('请先填写资源需求，或直接填写具体知识点。');
    const selection=await window.XYLearning.confirm('resource_analyze',{text});
    await send('/api/learning/resources/analyze',{text,confirmed:true,model_selection:selection});
  });
  $('form').onsubmit=e=>{e.preventDefault();run(async()=>{
    preview=await api('/api/learning/resources/preview',{method:'POST',body:JSON.stringify(requirements())});
    const area=$('preview');area.replaceChildren(node('h4','搜索关键词 · 可编辑'));area.hidden=false;
    const inputs=[];
    for(const query of preview.queries){const label=node('label',kinds[query.kind]),input=node('input');input.value=query.query;input.maxLength=180;label.append(input);area.append(label);inputs.push(input);}
    area.append(node('p',preview.destination),node('p',`最多 ${preview.max_credits} 次 Basic 查询 / ${preview.max_credits} credits；不调用模型，不自动重试或切换服务。`));
    const b=node('button','确认关键词并开始真实搜索');b.type='button';b.className='primary-button';area.append(b);
    b.onclick=()=>run(async()=>{
      const qs=preview.queries.map((q,i)=>({...q,query:inputs[i].value.trim()}));
      if(!confirm(`将以下查询词发送给 Tavily：\n${qs.map(q=>q.query).join('\n')}\n最多 ${preview.max_credits} credits，仅免费套餐且按量付费关闭时执行。确认搜索？`))return;
      await send('/api/learning/resources/search',{requirements:preview.requirements,queries:qs,confirmed:true});
    });status('关键词预览完成，未联网。');
  });};
  $('save').onclick=()=>run(async()=>{
    const ids=[...$('results').querySelectorAll('.resource-choice:checked')].map(n=>n.value);
    if(!ids.length)throw Error('请先勾选资源。');
    await send('/api/learning/resources/save',{search_id:search.request_id,resource_ids:ids,task_id:$('task').value});
  });
  $('recover').onclick=()=>run(async()=>{const path=pending.path;await accept(await api('/api/learning/resources/receipt?id='+encodeURIComponent(pending.body.request_id)),path);},true);
  $('dismiss').onclick=()=>run(async()=>{
    if(!confirm('只移除本浏览器待核对标记，不会取消服务端请求或重发。若原请求已执行，新的请求可能再次消耗额度。确认放弃标记？'))return;
    pending=null;persist();status('已放弃本地待核对标记，没有重发请求。');
  },true);
  window.LearningResources={async choose(task,req){
    root.open=true;
    if(busy||pending){status('请先核对当前资源请求；未更改搜索内容或任务关联。');root.scrollIntoView({block:'start'});return;}
    await run(async()=>{
      await refresh();taskId=task.id;$('task').value=taskId;
      if($('task').value!==taskId)throw Error('任务已不可关联，请刷新任务状态。');
      fill({course:req.course,topic:task.learning.content.length<=120?task.learning.content:task.title.length<=120?task.title:'',level:req.level,kinds:Object.keys(kinds)});
      $('request').value='';clearPreview();search=null;$('results').replaceChildren();persist();
      status(`已带入任务“${task.title}”的课程、学习内容和基础，请核对具体知识点；尚未联网、未调用模型。${!$('topic').value?'任务内容过长，请填写本次具体知识点。':''}`);
    });root.scrollIntoView({block:'start'});
  }};
  $('task').onchange=()=>{taskId=$('task').value;persist();};
  $('refresh').onclick=()=>run(refresh);
  $('form').addEventListener('input',()=>{clearPreview();persist();});
  $('request').addEventListener('input',persist);
  window.addEventListener('learning-model-changed',()=>{clearPreview();});
  let loaded=false;
  root.addEventListener('toggle',()=>{if(root.open&&!loaded)run(async()=>{await refresh();loaded=true;},true);});
  try{
    const saved=JSON.parse(localStorage.getItem(key)||'null');
    if(saved){$('request').value=saved.text||'';fill(saved.requirements);pending=saved.pending||null;taskId=saved.taskId||'';
      if(pending){root.open=true;}
      if(pending)status(`请求 ${pending.body.request_id} 待核对，未自动重发。`);
      else if(saved.searchId){pending={path:'/api/learning/resources/search',body:{request_id:saved.searchId}};status('上次搜索结果可通过“核对原请求回执”恢复，不会重新搜索。');}
    }
  }catch{status('资源草稿读取失败，请重新填写。');}
  controls();
})();
