'use strict';
(()=>{
async function localModel(){try{const d=await api('/api/local/model');const p=document.querySelector('#local-model-info');if(p)p.textContent=d.installed?'本机Qwen已安装，选择“本机 Qwen／本地工具”即可离线对话；首次加载需要稍等。':`本机Qwen准备中：${(d.downloaded_bytes/1e9).toFixed(2)} / ${(d.model_bytes/1e9).toFixed(2)} GB。`; }catch{}}localModel();window.addEventListener('xy:settings',localModel);
const release=document.createElement('button');release.type='button';release.className='text-button';release.textContent='释放本机模型占用';release.onclick=async()=>{try{await api('/api/local/model/control',{method:'POST',body:JSON.stringify({operation:'stop'})});await localModel();}catch(e){document.querySelector('#local-model-info').textContent=e.message;}};document.querySelector('#local-model-info')?.after(release);
const sections=[...document.querySelectorAll('.drawer-body > .settings-section')];
for(const section of sections.slice(1)){const heading=section.querySelector('h3');if(!heading)continue;const group=document.createElement('details'),summary=document.createElement('summary');group.className='settings-group';summary.textContent=heading.textContent;section.before(group);group.append(summary,section);}
})();
