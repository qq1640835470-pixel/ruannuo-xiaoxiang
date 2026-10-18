'use strict';
(()=>{
  const form=document.querySelector('#chat-form');if(!form)return;
  const button=document.createElement('button');button.type='button';button.id='chat-attach';button.className='subtle-button';button.textContent='＋ 图片/文件';
  const picker=document.createElement('input');picker.type='file';picker.id='chat-files';picker.multiple=true;picker.hidden=true;
  picker.accept='.png,.jpg,.jpeg,.webp,.txt,.md,.csv,.json,.log,.py,.js,.ts,.html,.css,.yaml,.yml,.xml,.docx';
  const list=document.createElement('div');list.id='chat-attachment-list';list.className='chat-attachment-list';list.setAttribute('aria-label','待发送附件');
  const tip=document.createElement('p');tip.className='chat-attachment-tip';tip.hidden=true;tip.textContent='附件仅在本机保存、提取；发送时文字或图片摘要会交给当前对话模型。最多3个文件（图片最多2张），每个4MB、合计8MB；文本/Word正文每份最多5000字。暂不支持PDF。';
  const status=document.createElement('p');status.id='chat-attachment-status';status.className='chat-attachment-tip';status.setAttribute('role','status');
  form.querySelector('.composer-footer').prepend(button);form.prepend(list,tip,status,picker);
  let files=[],uploading=false,busy=false;
  function render(){
    button.disabled=busy||uploading;picker.disabled=busy||uploading;list.replaceChildren();tip.hidden=!files.length;
    for(const file of files){
      const chip=document.createElement('div');chip.className='chat-attachment-chip';
      if(file.id&&file.kind==='image'){const image=document.createElement('img');image.src='/api/chat/attachments/'+file.id+'?preview=1';image.alt=file.name;chip.append(image);}
      const label=document.createElement('span');label.textContent=file.name+(file.id?'':' · 正在传到本机…');
      const remove=document.createElement('button');remove.type='button';remove.className='text-button';remove.textContent='移除';remove.setAttribute('aria-label','移除 '+file.name);remove.disabled=busy||uploading;
      remove.onclick=()=>{files=files.filter(f=>f!==file);render();};chip.append(label,remove);list.append(chip);
    }
  }
  button.onclick=()=>picker.click();
  picker.addEventListener('change',async()=>{
    const selected=Array.from(picker.files||[]);picker.value='';if(!selected.length)return;
    if(files.length+selected.length>3||selected.some(f=>f.size>4*1024*1024)||files.reduce((sum,f)=>sum+f.size,0)+selected.reduce((sum,f)=>sum+f.size,0)>8*1024*1024){status.textContent='最多3个附件，每个4MB、合计8MB；请减少文件。';return;}
    if(files.filter(f=>f.kind==='image').length+selected.filter(f=>/\.(png|jpe?g|webp)$/i.test(f.name)).length>2){status.textContent='每条消息最多2张图片。';return;}
    uploading=true;status.textContent='正在传到本机，尚未发给对话模型。';render();
    try{
      for(const file of selected){
        const entry={name:file.name,size:file.size};files.push(entry);render();
        try{
          const base64=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result).split(',')[1]);reader.onerror=()=>reject(Error('附件读取失败'));reader.readAsDataURL(file);});
          Object.assign(entry,await api('/api/chat/attachments',{method:'POST',body:JSON.stringify({name:file.name,base64})}));
          if(files.some(f=>f!==entry&&f.id===entry.id))files=files.filter(f=>f!==entry);
        }catch(e){files=files.filter(f=>f!==entry);throw e;}
      }
      status.textContent='附件已在本机准备好，可以输入问题并发送。';
    }catch(e){status.textContent='附件未添加：'+e.message;}
    finally{uploading=false;render();}
  });
  function renderMessage(message,host){
    if(!Array.isArray(message.attachments))return;
    for(const file of message.attachments){
      if(!/^[a-f0-9]{64}$/.test(file.id||''))continue;
      const link=document.createElement('a');link.className='chat-attachment-link';link.href='/api/chat/attachments/'+file.id;link.download=file.name;
      if(file.kind==='image'){const image=document.createElement('img');image.src=link.href+'?preview=1';image.alt=file.name;image.loading='lazy';link.append(image);}
      const name=document.createElement('span');name.textContent=file.name;link.append(name);host.append(link);
    }
  }
  window.XYAttachments={get uploading(){return uploading;},snapshot:()=>files.filter(f=>f.id).map(f=>({id:f.id,name:f.name,size:f.size,kind:f.kind})),
    setBusy(value){busy=!!value;render();},clear(ids){files=files.filter(f=>!ids.includes(f.id));status.textContent='';render();},renderMessage};
  try{const saved=JSON.parse(localStorage.getItem('xy.chat.pending')||'null');if(Array.isArray(saved?.attachments))files=saved.attachments.filter(f=>/^[a-f0-9]{64}$/.test(f.id||'')).slice(0,3);}catch{}
  render();
  if(typeof renderMessages==='function')renderMessages();
})();
