"use strict";
(() => {
  const $=id=>document.getElementById(id);
  let saved=null,revision=0,center=null;
  const label=m=>m?`${m.provider} / ${m.model}${m.configured_model==='auto'?'（按本机原规则；发送前解析准确型号）':''}`:'正在读取学习模型';
  function summary(){
    if(!saved)return;
    const text=`当前聊天：${saved.provider} / ${saved.model}；当前学习：${label(saved.learning_selection)}（${saved.learning_model_config?.mode!=='independent'?'跟随聊天':'独立指定'}）。`;
    $('learning-model-summary').textContent=text;if($('model-center-selections'))$('model-center-selections').textContent=text;$('learning-model-current').textContent=text;
    const selected=saved.learning_selection;
    if(!selected)return;
    const row=selected.provider==='openrouter'?center?.models.find(r=>r.id===selected.model):null;
    $('learning-model-evidence').textContent=row?`出题适配：${row.learning_check.reason}；价格 USD/百万Token：输入 ${row.input_usd_million??'未知'} / 输出 ${row.output_usd_million??'未知'}；${row.verification}。目录非账单，候选不保证兼容。`:`出题适配与真实验证待核对；${saved.learning_model_rates?('保护估算 CNY/百万Token：输入 '+saved.learning_model_rates[0]+' / 输出 '+saved.learning_model_rates[1]+'，非账单'):('价格未知')}。手动ID或目录缺失不表示不可选，也不表示调用成功。`;
  }
  async function evidence(){try{center=await api('/api/models/center');summary();}catch{$('learning-model-evidence').textContent='目录证据暂不可读，真实能力与价格待验证。';}}
  function changed(){
    $('learning-model-fields').hidden=$('learning-model-mode').value!=='independent';
    $('settings-save-status').textContent='学习模型选择尚未保存；不会调用模型。';
  }
  async function catalogue(){
    const rev=++revision,provider=$('learning-model-provider').value,select=$('learning-model-id'),current=select.value;
    if(provider==='local'){
      select.replaceChildren();for(const row of saved?.learning_local_models||[])select.add(new Option(`${row.label} · ${row.id}`,row.id));
      if([...select.options].some(o=>o.value===current))select.value=current;return;
    }
    try{
      const data=await window.XYModels?.getCatalogue(provider);
      if(rev!==revision)return;
      select.replaceChildren(new Option('请选择准确型号',''));
      const rows=data.models.slice(0,100);
      if(current&&!rows.some(r=>r.id===current))select.add(new Option(`${current}（手动/目录未确认）`,current));
      for(const row of rows)select.add(new Option(`${row.label||row.id} · ${row.id}`,row.id));
      select.value=current;
    }catch{$('settings-save-status').textContent='学习型号目录读取失败，保留当前ID；可手动准确输入。';}
  }
  window.XYLearning={
    label,
    catalogueProvider(){return $('learning-model-mode').value==='independent'?$('learning-model-provider').value:null;},
    settingsLoaded(s){
      const old=saved?.learning_selection;saved=s;
      $('learning-model-mode').value=s.learning_model_config?.mode||'follow';
      $('learning-model-provider').value=s.learning_model_config?.provider||s.provider;
      $('learning-model-id').replaceChildren(new Option(s.learning_model_config?.model||'请选择准确型号',s.learning_model_config?.model||''));
      $('learning-model-fields').hidden=$('learning-model-mode').value!=='independent';
      summary();catalogue();evidence();
      if(JSON.stringify(old)!==JSON.stringify(s.learning_selection))window.dispatchEvent(new Event('learning-model-changed'));
    },
    selectModel(provider,model){
      $('learning-model-mode').value='independent';$('learning-model-provider').value=provider;
      $('learning-model-id').replaceChildren(new Option(`${model}（当前选择）`,model));changed();catalogue();
    },
    savePayload(){return {learning_model_config:$('learning-model-mode').value==='follow'?{mode:'follow',provider:'',model:''}:{mode:'independent',provider:$('learning-model-provider').value,model:$('learning-model-id').value}};},
    async confirm(operation,body,checkId){
      const preview=await api('/api/learning/model-preview',{method:'POST',body:JSON.stringify({operation,body,...(checkId?{check_id:checkId}:{})})});
      if(!confirm(`本次学习模型：${label(preview.model)}\n仅发送本页已选内容${operation==='evaluate'?'及本次简答题、参考要点和答案':''}；云模型可能计费。确认发送？`))throw Error('已取消，未调用学习模型。');
      $('learning-model-current').textContent=`本次即将调用：${label(preview.model)}。`;return preview.model;
    }
  };
  $('learning-model-mode').onchange=changed;
  $('learning-model-provider').onchange=()=>{$('learning-model-id').replaceChildren(new Option('请选择准确型号',''));changed();catalogue();};
  $('learning-model-use-id').onclick=()=>{
    const model=$('learning-model-manual').value.trim();
    if(!model||/sk-|AIza|Bearer/i.test(model)){$('settings-save-status').textContent='请填写准确模型ID，不要填写Key。';return;}
    $('learning-model-id').replaceChildren(new Option(`${model}（手动，能力待验证）`,model));changed();
  };
  $('learning-model-follow').onclick=()=>{$('learning-model-mode').value='follow';changed();};
  window.addEventListener('models-catalogue-updated',()=>{catalogue();evidence();});
  window.addEventListener('local-model-selection-changed',async()=>{
    if(saved?.learning_selection?.mode!=='follow'||saved.learning_selection.provider!=='local')return;
    window.dispatchEvent(new Event('learning-model-changed'));
    try{saved=await api('/api/settings');summary();}
    catch{$('learning-model-current').textContent='本机学习型号已改变，请重新读取设置并确认准确型号。';}
  });
})();
