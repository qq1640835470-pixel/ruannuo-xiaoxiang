"use strict";
(() => {
  const box=document.querySelector('#learning-reminder'),review=document.querySelector('#learning-review'),form=document.querySelector('#reminder-settings-form');
  if(!box||!review||!form)return;
  const status=document.querySelector('#reminder-status'),key='xiaoxiang-reminder-pending-v1';
  let active=null,pending=null,busy=false,dirty=false,lastCheck=0,queued=false,todaySummary=null;
  const $=id=>document.getElementById(id);
  const node=(tag,text)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n;};
  function message(text){status.textContent=text;}
  function button(parent,label,action){const b=node('button',label);b.type='button';b.className='subtle-button';b.onclick=action;parent.append(b);return b;}
  function remember(){try{if(pending)localStorage.setItem(key,JSON.stringify(pending));else localStorage.removeItem(key);}catch{message('待核请求无法保存在浏览器，请保持页面开启并核对同一操作。');}}
  function settings(s){$('reminder-pause-indicator').textContent=s.paused_on===new Date().toLocaleDateString('sv-SE')?'今天已暂停提醒':s.enabled?'提醒已启用':'提醒已关闭';if(dirty)return;$('reminder-enabled').checked=s.enabled;for(const k of ['window_start','window_end','quiet_start','quiet_end'])$(`reminder-${k.replaceAll('_','-')}`).value=s[k];$('reminder-limit').value=s.daily_limit;}
  function summary(v){
    todaySummary=v;
    review.replaceChildren(node('h3','今日学习回顾'));
    review.append(node('p',`${v.day} · 计划 ${v.planned} 项 · 已完成 ${v.completed} 项 · 尚未完成 ${v.remaining} 项`));
    review.append(node('p',`今日记录的实际学习时间：${v.actual_minutes===null?'未知 / 未填写':v.actual_minutes+' 分钟'}${v.unfilled_records?'；另有 '+v.unfilled_records+' 条记录未填写分钟':''}。已延期 ${v.deferred} 项，逾期未完成 ${v.overdue} 项。`));
    if(v.undated_records)review.append(node('p',`另有 ${v.undated_records} 条学习记录的日期不明，未计入今日分钟。`));
    review.append(node('p',v.planned===0?'今天没有已安排的学习任务，可以按自己的节奏来。':v.remaining===0?'今日安排已经完成，可以回看收获和疑问；这不代表已确认掌握。':'还有学习安排没完成，方便时从一小步开始就好。'));
  }
  function openTask(task){changePage('learning');window.dispatchEvent(new CustomEvent('learning-task-focus',{detail:{task_id:task.id}}));}
  function display(){
    box.replaceChildren();box.hidden=!active&&!pending;if(box.hidden)return;
    if(pending){box.append(node('p','上次提醒操作的回执待核对，没有自动重做。'));button(box,'核对同一提醒操作',()=>send());return;}
    box.append(node('p','小祥轻轻提醒：这些学习安排还在等你，方便时选一项就好。'));
    if(todaySummary)box.append(node('p',`今日安排 ${todaySummary.planned} 项，已完成 ${todaySummary.completed} 项，尚未完成 ${todaySummary.remaining} 项。`));
    const list=node('ul');for(const task of active.tasks.slice(0,3)){
      const li=node('li',`${task.course} · ${task.title}（${({active:'进行中',deferred:'已延期',paused:'已暂停',pending:'待开始'})[task.status]||task.status}${task.date<(todaySummary?.day||new Date().toLocaleDateString('sv-SE'))?'，逾期未完成':''}）`);
      button(li,'开始学习',()=>action('start',{task_id:task.id}));button(li,'查看计划',()=>{action('dismiss');openTask(task);});list.append(li);
    }box.append(list);if(active.tasks.length>3)box.append(node('p',`另有 ${active.tasks.length-3} 项，学习页可查看全部。`));
    const actions=node('div');actions.className='reminder-actions';
    for(const minutes of [15,60])button(actions,`${minutes}分钟后提醒`,()=>action('snooze',{minutes}));
    button(actions,'今天不再提醒',()=>action('pause'));button(actions,'跳过 / 关闭',()=>action('dismiss'));box.append(actions);
  }
  async function poll(force=false){
    if(pending||document.visibilityState==='hidden')return;
    if(busy){if(force)queued=true;return;}
    queued=false;
    const time=Date.now(),delta=time-lastCheck;if(!force&&delta>=0&&delta<1000)return;
    busy=true;lastCheck=time;
    try{const result=await api('/api/learning/reminders/check',{method:'POST',body:JSON.stringify(active?{current_id:active.id}:{})});settings(result.settings);summary(result.summary);active=result.reminder;display();}
    catch(e){message('提醒检查暂未完成：'+e.message);active=null;display();}
    finally{busy=false;if(queued){queued=false;void poll(true);}}
  }
  async function send(){
    if(busy||!pending)return;busy=true;const request=pending;display();box.querySelectorAll('button').forEach(b=>b.disabled=true);
    try{
      const receipt=await api(request.path,{method:request.method,body:JSON.stringify(request.body)});
      if(!receipt.ok)throw new Error('未取得有效操作回执。');
      pending=null;remember();active=null;display();
      if(receipt.action==='start'){
        const task=await api(`/api/tasks/${receipt.task_id}`);
        if(task.id!==receipt.task_id||task.status!=='active')throw new Error('回执已返回，但任务当前并非进行中，请查看计划核对。');
        message('已核对任务状态：进行中。');openTask({id:receipt.task_id});
      }else if(receipt.action==='snooze')message(`已保存${request.body.minutes}分钟后提醒；仍遵循勿扰及每日上限。`);
      else if(receipt.action==='pause')message('今天已暂停学习提醒；任务状态没有改变。');
      else if(receipt.action==='resume')message('已恢复今日提醒，仍遵循已处理记录和频率限制。');
      else if(receipt.settings){dirty=false;settings(receipt.settings);message('提醒设置已保存。');}
      else message('已关闭本次提醒，任务状态没有改变。');
    }catch(e){if(e.responseData){pending=null;remember();}message(e.message);display();}
    finally{busy=false;display();await poll(true);}
  }
  function action(name,extra={}){
    if(busy||pending)return;
    pending={path:'/api/learning/reminders/action',method:'POST',body:{request_id:crypto.randomUUID().replaceAll('-',''),action:name,...(!['pause','resume'].includes(name)&&active?{reminder_id:active.id}:{}),...extra}};
    remember();send();
  }
  form.addEventListener('input',()=>{dirty=true;});
  form.onsubmit=event=>{
    event.preventDefault();if(busy||pending)return;
    const body={request_id:crypto.randomUUID().replaceAll('-',''),enabled:$('reminder-enabled').checked,daily_limit:Number($('reminder-limit').value)};
    for(const k of ['window_start','window_end','quiet_start','quiet_end'])body[k]=$(`reminder-${k.replaceAll('_','-')}`).value;
    pending={path:'/api/learning/reminders/settings',method:'PATCH',body};remember();send();
  };
  $('reminder-pause').onclick=()=>action('pause');$('reminder-resume').onclick=()=>action('resume');
  try{pending=JSON.parse(localStorage.getItem(key)||'null');}catch{message('待核提醒请求无法读取，请先查看当前任务状态。');}
  display();poll(true);
  window.addEventListener('learning-state-refreshed',()=>poll(true));
  window.addEventListener('learning-open',()=>poll(true));window.addEventListener('focus',()=>poll());window.addEventListener('pageshow',()=>poll());
  document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='visible')poll(true);else{active=null;display();}});
  setInterval(()=>poll(),60000);
})();
