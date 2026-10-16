"use strict";
(() => {
  const home=document.querySelector('#workspace-home');if(!home)return;
  const section=document.createElement('details');section.id='local-image-tool';
  section.innerHTML=`<summary>本地看图 · Gemma 3 4B</summary><p>仅在本机处理你选择的图片，不上传云端。首次加载需要稍等；未安装完整模型时不可用。</p>
    <label>图片<input type="file" accept="image/png,image/jpeg,image/webp" id="local-image-file"></label>
    <label>想了解什么<input id="local-image-prompt" maxlength="2000" value="请描述图片中的主要内容，用中文回答。"></label>
    <button type="button" id="local-image-run">本地解析</button><p id="local-image-result" role="status" style="white-space:pre-wrap"></p>`;
  home.append(section);
  const button=section.querySelector('#local-image-run'),result=section.querySelector('#local-image-result');
  button.addEventListener('click',async()=>{
    const file=section.querySelector('#local-image-file').files[0];if(!file){result.textContent='先选择一张图片吧。';return;}
    if(!['image/png','image/jpeg','image/webp'].includes(file.type)||file.size>8*1024*1024){result.textContent='请选择8MB以内的PNG、JPEG或WebP图片。';return;}
    button.disabled=true;result.textContent='正在本机解析，首次启动会稍久一些…';
    try{
      const base64=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result).split(',')[1]);reader.onerror=()=>reject(new Error('图片读取失败'));reader.readAsDataURL(file);});
      const data=await api('/api/local/analyze-image',{method:'POST',body:JSON.stringify({prompt:section.querySelector('#local-image-prompt').value,image:{base64,mime_type:file.type}})});
      result.textContent=data.text;
    }catch(e){result.textContent=e.message;}finally{button.disabled=false;}
  });
})();
