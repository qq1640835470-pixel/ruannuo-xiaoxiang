"use strict";
(() => {
  const parent=document.getElementById('openrouter-settings');if(!parent)return;
  const panel=document.createElement('details');panel.id='model-center';panel.innerHTML='<summary>模型中心 · 搜索与筛选</summary>';
  parent.parentElement.after(panel);const status=document.createElement('p');status.role='status';panel.append(status);
  const selections=document.createElement('p');selections.id='model-center-selections';panel.append(selections);
  let data=null,page=0,loadRevision=0;const size=24,fields={};
  const tags={all:'全部模型',chat:'日常聊天',learning:'学习计划与出题',reasoning:'数学与复杂推理（声明参数）',vision:'多模态/视觉（上游）',free:'免费模型',low_cost:'低成本模型',favorites:'收藏模型',recent:'最近使用'};
  function n(tag,text){const e=document.createElement(tag);if(text!==undefined)e.textContent=text;return e;}
  const filters=n('div');filters.className='model-filters';panel.append(filters);
  function field(key,label,type,options){const wrap=n('label',label),input=n(options?'select':'input');input.id='model-center-'+key;if(!options)input.type=type;
    if(options)for(const [value,text] of Object.entries(options)){const o=n('option',text);o.value=value;input.append(o);}
    else if(type==='number'){input.min=0;input.step='any';}
    fields[key]=input;wrap.append(input);filters.append(wrap);input.oninput=()=>{page=0;render();};return input;
  }
  field('search','名称或准确ID','search');field('vendor','厂商','',{'':'全部厂商'});field('tag','分类','',tags);
  field('billing','价格类型','',{'':'全部价格',free:'免费（输入输出均为0）',paid:'付费',unknown:'未知'});
  field('input','输入价上限 USD/百万Token','number');field('output','输出价上限 USD/百万Token','number');field('context','最低上下文Token','number');
  field('json','结构化输出','',{'':'全部能力',json:'声明JSON参数',text:'未声明JSON，文字解析',unknown:'参数未知'});
  field('sort','排序','',{'id':'准确ID',input:'输入价从低到高',output:'输出价从低到高',input_desc:'输入价从高到低',output_desc:'输出价从高到低',context:'上下文从大到小'});
  const toolbar=n('div');toolbar.className='model-center-actions';panel.append(toolbar);
  function button(parent,label,action){const b=n('button',label);b.type='button';b.className='subtle-button';b.onclick=async()=>{b.disabled=true;try{await action();}catch(e){status.textContent=e.message+'；未自动重试或调用模型。';}finally{b.disabled=false;}};parent.append(b);return b;}
  button(toolbar,'切回全部模型',()=>{for(const [key,input] of Object.entries(fields))input.value=key==='tag'?'all':key==='sort'?'id':'';page=0;render();});
  button(toolbar,'重新读取本机目录与记录',load);
  const note=n('p','规则分类只表示元数据满足要求，可尝试；不是权限、效果或正确性验证。视觉为上游声明，当前小祥OpenRouter仅适配文字。低成本门槛：输入≤1、输出≤4 USD/百万Token；未知价格不计为免费。下拉框最多展示前100项，模型中心按24项分页；选用后仍需保存设置。最近使用包含已保存选择与成功调用，不代表已真实验证。');panel.append(note);
  const count=n('p'),list=n('div');list.id='model-center-list';panel.append(count,list);
  const navigation=n('div');navigation.className='model-center-actions';panel.append(navigation);
  const previous=button(navigation,'上一页',()=>{page--;render();}),next=button(navigation,'下一页',()=>{page++;render();});
  const records=n('div');records.id='model-center-records';panel.append(records);
  const money=value=>value===null||value===undefined?'未知':`${value.toLocaleString('en-US',{maximumFractionDigits:6})} USD/百万Token`;
  function filtered(){
    const query=fields.search.value.normalize('NFKC').toLowerCase().trim();
    const rows=data.models.filter(row=>{
      const ip=row.input_usd_million,op=row.output_usd_million;
      if(query&&!`${row.id} ${row.label}`.normalize('NFKC').toLowerCase().includes(query))return false;
      if(fields.vendor.value&&row.vendor!==fields.vendor.value)return false;
      if(fields.tag.value!=='all'&&!row.tags.includes(fields.tag.value))return false;
      if(fields.billing.value==='free'&&!(ip===0&&op===0))return false;
      if(fields.billing.value==='paid'&&!((ip!==null&&ip>0)||(op!==null&&op>0)))return false;
      if(fields.billing.value==='unknown'&&ip!==null&&op!==null)return false;
      if(fields.input.value!==''&&(ip===null||ip>Number(fields.input.value)))return false;
      if(fields.output.value!==''&&(op===null||op>Number(fields.output.value)))return false;
      if(fields.context.value!==''&&!(row.context_length>=Number(fields.context.value)))return false;
      const params=row.supported_parameters||[];
      if(fields.json.value==='json'&&!params.some(p=>['response_format','structured_outputs'].includes(p)))return false;
      if(fields.json.value==='text'&&(!params.length||params.some(p=>['response_format','structured_outputs'].includes(p))))return false;
      if(fields.json.value==='unknown'&&params.length)return false;
      return true;
    });
    const sort=fields.sort.value,key=sort.startsWith('input')?'input_usd_million':sort.startsWith('output')?'output_usd_million':'context_length';
    rows.sort((a,b)=>{
      if(sort==='id')return a.id.localeCompare(b.id);
      const av=a[key],bv=b[key];if(av==null)return bv==null?0:1;if(bv==null)return -1;
      return (av-bv)*(sort.endsWith('desc')||sort==='context'?-1:1)||a.id.localeCompare(b.id);
    });return rows;
  }
  function render(){
    if(!data)return;const rows=filtered();page=Math.max(0,Math.min(page,Math.max(0,Math.ceil(rows.length/size)-1)));list.replaceChildren();
    count.textContent=`筛选 ${rows.length} / ${data.models.length} · 第${page+1}页 · 每页${size}项`;previous.disabled=page===0;next.disabled=(page+1)*size>=rows.length;
    for(const row of rows.slice(page*size,(page+1)*size)){
      const card=n('article');card.className='model-card';card.dataset.modelId=row.id;
      card.append(n('h4',row.label||row.id),n('p',`准确ID：${row.id} · 厂商：${row.vendor}`),n('p',`输入 ${money(row.input_usd_million)}；输出 ${money(row.output_usd_million)}。目录价格非账单。`),n('p',`上下文 ${row.context_length??'未知'} · 最大输出 ${row.max_completion_tokens??'未知'} Token`),n('p',`声明参数：${(row.supported_parameters||[]).join('、')||'未知'}`),n('p',`上游模态：${(row.input_modalities||[]).join('/')||'未知'} → ${(row.output_modalities||[]).join('/')||'未知'}；当前仅文字输入，未适配OpenRouter图片直传。`),n('p',`已适配：${row.app_adapted.join('、')}；出题：${row.learning_check.reason}；计划：${row.learning_plan.reason}`),n('p',`JSON适配：${row.supported_parameters?.includes('response_format')?'使用已声明的JSON对象参数':'按文字请求并校验JSON，无自动参数重试'}；学习出题验证：${row.verification}`),n('p',`分类：${row.tags.map(t=>tags[t]).join('、')||'待验证'}`));
      button(card,'用作聊天模型（再保存设置）',()=>{window.XYModels.selectChatModel('openrouter',row.id);status.textContent=`已选 ${row.id}，请保存设置；没有调用模型。`;});
      button(card,'用作学习模型（再保存设置）',()=>{window.XYLearning.selectModel('openrouter',row.id);status.textContent=`已选学习模型 ${row.id}，请保存设置；聊天选择未改变。`;});
      button(card,data.preferences.favorites.includes(row.id)?'取消收藏':'收藏',async()=>{await api('/api/models/center',{method:'POST',body:JSON.stringify({action:'favorite',model_id:row.id,favorite:!data.preferences.favorites.includes(row.id),request_id:crypto.randomUUID().replaceAll('-','')})});await load();});list.append(card);
    }
  }
  function verification(){
    records.replaceChildren(n('h4','本机测试记录（按任务类型）'));
    for(const r of data.preferences.records.slice(0,20))records.append(n('p',`${r.time} · ${r.model_id} → ${r.returned_model} · ${({learning_check:'学习出题',learning_plan:'学习计划',chat:'文字聊天'})[r.task]||r.task} · ${r.outcome==='success'?'成功':'失败'} · ${({real:'用户确认真实',simulated:'模拟测试',unverified:'来源尚未人工确认'})[r.origin]||r.origin} · ${r.category||'无失败类别'} · 应用${r.app_version} / 规则${r.rules}`));
    const real=new Set(data.preferences.records.filter(r=>r.origin==='real').map(r=>r.check_id));
    const choices=data.preferences.records.filter(r=>r.outcome==='success'&&r.task==='learning_check'&&r.origin==='unverified'&&r.check_id&&!real.has(r.check_id));
    if(!choices.length){records.append(n('p','尚无可确认的已保存出题测试。不会为了验证自动调用付费API。'));return;}
    const form=n('form'),select=n('select');select.id='model-center-verify-check';
    for(const r of choices){const o=n('option',`${r.model_id} · ${r.time}`);o.value=r.check_id;select.append(o);}form.append(select);
    const label=n('label','我确认选中的测验由真实模型生成并已核对，绝非模拟；此标记是我的本机测试声明，不是目录推荐。'),check=n('input');check.type='checkbox';check.required=true;label.prepend(check);form.append(label);
    button(form,'保存真实出题验证记录',async()=>{if(!check.checked)throw Error('请先明确确认真实测试来源。');await api('/api/models/center',{method:'POST',body:JSON.stringify({action:'verify',check_id:select.value,real_confirmation:true,request_id:crypto.randomUUID().replaceAll('-','')})});await load();});records.append(form);
  }
  async function load(){const revision=++loadRevision;const result=await api('/api/models/center');if(revision!==loadRevision)return;data=result;const vendor=fields.vendor.value;fields.vendor.replaceChildren(new Option('全部厂商',''));for(const v of [...new Set(data.models.map(r=>r.vendor))].sort())fields.vendor.add(new Option(v,v));fields.vendor.value=vendor;render();verification();status.textContent=`本机目录 ${data.catalogue_status}；没有发起模型调用。`;
  }
  panel.addEventListener('toggle',()=>{if(panel.open)load().catch(e=>status.textContent=e.message);});
  window.addEventListener('models-catalogue-updated',()=>{if(panel.open)load().catch(e=>status.textContent=e.message);});
})();
