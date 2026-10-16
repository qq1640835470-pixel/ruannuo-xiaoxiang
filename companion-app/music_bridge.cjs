/* Private stdin/stdout RPC. No listener, arbitrary method or credential logging. */
'use strict';
const fs=require('node:fs'),path=require('node:path');
for(const k of ['log','info','warn','error','debug'])console[k]=()=>{};
const base=path.join(__dirname,'music-runtime','node_modules','NeteaseCloudMusicApi');
const allowed=new Set(['login_qr_key','login_qr_create','login_qr_check','login_status','user_playlist','playlist_track_all','song_url_v1','cloudsearch']);
let input='';process.stdin.setEncoding('utf8');process.stdin.on('data',s=>{input+=s;if(input.length>32000)process.exit(2);});
process.stdin.on('end',async()=>{
  const timer=setTimeout(()=>{process.stdout.write(JSON.stringify({ok:false,error:'音乐服务响应超时'}));process.exit(0);},20000);
  try{
    const b=JSON.parse(input);if(!allowed.has(b.method))throw new Error('method');
    const temp=require('node:os').tmpdir();fs.mkdirSync(temp,{recursive:true});const anon=path.join(temp,'anonymous_token');if(!fs.existsSync(anon))fs.writeFileSync(anon,'');
    const {cookieToJson}=require(path.join(base,'util','index.js'));
    const request=require(path.join(base,'util','request.js'));
    const fn=require(path.join(base,'module',b.method+'.js'));
    const result=await fn({...b.params,cookie:cookieToJson(b.cookie||'')},request);
    process.stdout.write(JSON.stringify({ok:true,body:result.body||{},cookies:result.cookie||[]}));
  }catch(e){process.stdout.write(JSON.stringify({ok:false,error:'网易云接口未返回可用结果',code:Number(e?.body?.code||e?.status||0)}));}
  clearTimeout(timer);
});
