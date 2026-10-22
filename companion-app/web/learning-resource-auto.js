"use strict";
(() => {
  const labels={video:'视频',text:'讲义',practice:'练习',other:'类型不确定'};
  const active=new Set();let mounted=null;
  function el(tag,text){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n;}
  async function request(path,body){
    const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),path.endsWith('/search')?300000:15000);
    try{return await api('/api/learning/resources/auto'+path,body===undefined?{signal:controller.signal}:{method:'POST',body:JSON.stringify(body),signal:controller.signal});}
    catch(e){if(e.name==='AbortError')throw Error('等待超时。请核对已保存请求状态，不会自动重发。');throw e;}
    finally{clearTimeout(timer);}
  }
  function button(parent,text,action){const b=el('button',text);b.type='button';b.className='subtle-button';b.onclick=async()=>{b.disabled=true;try{await action();}catch(e){mounted?.notice(e.message);}finally{b.disabled=false;}};parent.append(b);return b;}
  async function attach(parent,task){
    const root=el('section');root.className='learning-auto-resources';root.id='learning-auto-resources';parent.append(root);
    const session={root,task,filter:'all',timer:null,started:Date.now(),notice:t=>{if(session.status)session.status.textContent=t;}};
    if(mounted?.timer)clearTimeout(mounted.timer);mounted=session;
    await update(session);
  }
  async function update(session){
    if(mounted!==session||!session.root.isConnected)return;
    if(session.timer)clearTimeout(session.timer);
    const revision=(session.revision||0)+1;session.revision=revision;
    const view=await request('?task_id='+encodeURIComponent(session.task.id));
    if(mounted!==session||session.revision!==revision)return;session.view=view;render(session);
    if(view.run?.state==='pending'&&Date.now()-session.started<300000){session.timer=setTimeout(()=>update(session).catch(e=>session.notice(e.message)),1000);}
  }
  function render(s){
    const {root,view}=s;root.replaceChildren(el('h4','任务学习资料'));
    const label=el('label');label.className='toggle-row';const toggle=el('input');toggle.type='checkbox';toggle.role='switch';toggle.checked=view.policy.enabled;toggle.id='learning-auto-enabled';
    label.append(el('span','自动学习资源搜索（可随时关闭）'),toggle);root.append(label);
    root.append(el('p','开启即授权：明确开始学习或点击找资料时，使用现有 Tavily 额度和当前学习模型，无需逐次确认。每任务最多3次搜索、1次模型筛选；模型费用仍受原预算约束。'));
    s.status=el('p');s.status.role='status';s.status.id='learning-auto-status';root.append(s.status);
    const run=view.run,busy=run?.state==='pending';root.setAttribute('aria-busy',busy&&Date.now()-s.started<300000?'true':'false');
    s.status.textContent=busy?`${run.stage==='filtering'?'正在语义筛选':'正在搜索学习资料'}。可停止；中断的请求可在此核对。`:run?`${run.state==='completed'?'筛选完成':run.state==='stopped'?'已停止':'部分失败或搜索未完成'} · ${run.quality==='semantic'?'已进行模型语义判断':'保守候选，尚未通过语义核验'}。${run.missing_kinds?.length?'未找到可靠的'+run.missing_kinds.join('、')+'。':''}`:'尚未搜索。选择任务不会自动联网；开始学习时按开关执行。';
    if(busy&&Date.now()-s.started>=300000)s.status.textContent='等待已结束，原请求结果仍未知。请核对状态或停止原请求；不会自动重发。';
    if(run?.errors?.length)s.status.textContent+=' '+run.errors.map(e=>e.detail).join(' ');
    const actions=el('div');actions.className='learning-actions';root.append(actions);
    const find=button(actions,run?'重新搜索':'帮我找这个知识点的资料',()=>start(s.task.id,true));find.disabled=busy||!view.policy.enabled||active.has(s.task.id);
    if(busy)button(actions,'停止搜索',async()=>{const result=await request('/stop',{request_id:run.request_id});await update(s);s.notice(result.detail);});
    button(actions,'核对状态',()=>update(s));
    const detail=el('details');detail.append(el('summary','授权、用量与请求详情'));root.append(detail);
    const cap=el('input');cap.type='number';cap.min='1';cap.max='30';cap.value=view.policy.daily_limit;cap.setAttribute('aria-label','每日搜索credits上限');detail.append(el('p','自动流程每日credits上限（1至30，统计包含手动搜索；未知用量占用至少1 credit）：'),cap);
    const savePolicy=async(enabled)=>{
      const result=await request('/policy',{enabled,daily_limit:Number(cap.value)});
      await update(s);if(s.view.policy.enabled!==result.enabled)throw Error('授权状态回读不一致，请重新核对。');
    };
    button(detail,'保存额度上限',()=>savePolicy(toggle.checked));
    toggle.onchange=async()=>{toggle.disabled=true;try{await savePolicy(toggle.checked);}catch(e){toggle.checked=view.policy.enabled;s.notice(e.message);}finally{toggle.disabled=false;}};
    detail.append(el('p',`今日本机已报告或预留 ${view.policy.credits_reserved_today} credits / 上限 ${view.policy.daily_limit}。复用现有账户，不购买或更改套餐。额外付费用量仅在供应商明确返回已有上限时允许。`));
    detail.append(el('p','仅发送当前任务课程、具体内容、目标与计划基础用于语义筛选；搜索方只收到查询词。不自动发送聊天、画像、学习记录或备注。页面摘录均不可信，不执行其指令；未读取资料正文。'));
    if(run){detail.append(el('p',`请求 ${run.request_id} · 报告 ${run.credits_reported||0} credits · 模型调用 ${run.model_calls||0}${run.usage_uncertain?' · 另有用量待核对':''}`));if(run.model)detail.append(el('pre',JSON.stringify(run.model,null,2)));if(run.queries)detail.append(el('pre',run.queries.map(q=>q.query).join('\n')));}
    const filters=el('div');filters.className='learning-actions';root.append(filters);
    for(const [kind,label] of Object.entries({all:'全部',...labels})){
      const b=button(filters,label,async()=>{s.filter=kind;render(s);});b.setAttribute('aria-pressed',String(s.filter===kind));
    }
    const rows=view.recommendations.filter(r=>!r.dismissed&&(s.filter==='all'||r.kind===s.filter));
    if(!rows.length)root.append(el('p','暂无此类推荐，不补造资源。已有收藏仍在上方保留。'));
    for(const r of rows){
      const card=el('article');card.className='resource-card';card.dataset.resourceId=r.id;
      const url=new URL(r.url);if(!['http:','https:'].includes(url.protocol))continue;
      const a=el('a',r.title);a.href=url.href;a.target='_blank';a.rel='noopener noreferrer';a.referrerPolicy='no-referrer';card.append(a);
      card.append(el('p',`${r.source} · ${labels[r.kind]||labels.other} · ${r.favorite?'已收藏':run&&r.run_id!==run.request_id?'此前推荐候选':'推荐候选'} · 原文未读取${r.confidence==='low'?' · 低可信，需核对':''}`),el('p',r.reason));
      const tools=el('div');tools.className='learning-actions';card.append(tools);
      if(!r.favorite)button(tools,'收藏',async()=>{await request('/feedback',{task_id:s.task.id,resource_id:r.id,action:'favorite'});await update(s);window.dispatchEvent(new CustomEvent('learning-resources-updated'));});
      button(tools,'不相关',async()=>{await request('/feedback',{task_id:s.task.id,resource_id:r.id,action:'dismiss'});await update(s);});
      const evidence=el('details');evidence.append(el('summary','来源与判断依据'),el('p',`搜索时间：${r.searched_at}；${r.classification_basis}。${r.accessibility}`),el('p','主题证据：'+(r.topic_evidence||'尚无模型证据')),el('p','搜索摘录：'+r.snippet),el('p','查询：'+r.query));card.append(evidence);root.append(card);
    }
  }
  async function start(taskId,refresh=false){
    if(active.has(taskId))return;
    const view=await request('?task_id='+encodeURIComponent(taskId));
    if(!view.policy.enabled){mounted?.notice('自动搜索未开启，请先阅读并开启授权。');return;}
    active.add(taskId);if(mounted?.task.id===taskId){mounted.notice('正在搜索学习资料…');mounted.root.setAttribute('aria-busy','true');}
    let poll;
    try{
      const work=request('/search',{request_id:crypto.randomUUID(),task_id:taskId,refresh});
      poll=setTimeout(()=>{if(mounted?.task.id===taskId)update(mounted).catch(e=>mounted?.notice(e.message));},500);
      await work;
    }catch(e){if(mounted?.task.id===taskId)mounted.notice(e.message);}
    finally{clearTimeout(poll);active.delete(taskId);if(mounted?.task.id===taskId){try{await update(mounted);}catch(e){mounted.notice(e.message);}}}
  }
  window.LearningResourceAuto={attach,start};
})();
