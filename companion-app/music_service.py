"""Optional community NetEase adapter. Cookies DPAPI encrypted; never sent to an LLM."""
from __future__ import annotations
import app_paths
import json,os,pathlib,re,subprocess,threading,time,urllib.parse
import providers,runtime_log
ROOT=pathlib.Path(__file__).resolve().parent
DATA=app_paths.DATA
NODE=pathlib.Path(r'C:\Users\16408\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe')
_LOCK=threading.RLock();_QR=None

def rpc(method,params=None,cookie=None):
    if not NODE.is_file() or not (ROOT/'music-runtime'/'node_modules'/'NeteaseCloudMusicApi').is_dir():raise ValueError('网易云适配组件未就绪。')
    env=os.environ.copy();temp=DATA/'music-temp';temp.mkdir(parents=True,exist_ok=True);env.update(TEMP=str(temp),TMP=str(temp))
    payload=json.dumps({'method':method,'params':params or {},'cookie':load_cookie() if cookie is None else cookie})
    try:
        p=subprocess.run([str(NODE),str(ROOT/'music_bridge.cjs')],input=payload,text=True,encoding='utf-8',stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=24,env=env,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        result=json.loads(p.stdout)
    except (subprocess.SubprocessError,ValueError,OSError) as exc:
        runtime_log.error('music_request_failed',exc,kind=method);raise ValueError('网易云音乐连接失败或超时，未自动重试。') from None
    if not result.get('ok'):raise ValueError(result.get('error','网易云接口暂不可用。'))
    return result

def load_cookie():
    file=DATA/'netease-cookie.dpapi'
    if not file.is_file():return ''
    try:return providers.hub.protect(file.read_bytes(),decrypt=True).decode('utf-8')
    except Exception:raise ValueError('本机网易云登录状态无法解密，请重新扫码。') from None

def save_cookie(value):
    if not isinstance(value,str) or not 0<len(value)<=16000:raise ValueError('登录状态格式无效。')
    DATA.mkdir(parents=True,exist_ok=True);file=DATA/'netease-cookie.dpapi';temp=file.with_suffix('.tmp');temp.write_bytes(providers.hub.protect(value.encode('utf-8')));temp.replace(file)

def clean_id(value):
    value=str(value)
    if not re.fullmatch(r'[1-9][0-9]{0,19}',value):raise ValueError('音乐编号无效。')
    return value

def status():
    if not load_cookie():return {'logged_in':False,'detail':'未登录网易云音乐。','adapter':'community:NeteaseCloudMusicApi@4.32.0'}
    body=rpc('login_status')['body'];profile=(body.get('data') or body).get('profile')
    if not profile:return {'logged_in':False,'detail':'网易云登录已过期，请重新扫码。'}
    return {'logged_in':True,'user_id':profile.get('userId'),'nickname':str(profile.get('nickname',''))[:100],'detail':'已连接网易云账号。'}

def qr_start():
    global _QR
    with _LOCK:
        body=rpc('login_qr_key',cookie='')['body'];data=body.get('data') or {};key=data.get('unikey') or (data.get('data') or {}).get('unikey')
        if not isinstance(key,str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,200}',key):raise ValueError('未取得网易云扫码凭据。')
        image=rpc('login_qr_create',{'key':key,'qrimg':True},cookie='')['body'].get('data',{}).get('qrimg','')
        if not image.startswith('data:image/png;base64,') or len(image)>200000:raise ValueError('未取得网易云登录二维码。')
        _QR={'key':key,'until':time.monotonic()+120,'last_check':0}
    return {'qr_image':image,'expires_seconds':120,'detail':'请用网易云音乐手机App扫码，并核对官方登录提示。'}

def qr_check():
    with _LOCK:
        if not _QR or time.monotonic()>_QR['until']:return {'state':'expired','detail':'二维码已过期，请重新获取。'}
        if time.monotonic()-_QR['last_check']<2:return {'state':'waiting','detail':'等待扫码确认。'}
        _QR['last_check']=time.monotonic();result=rpc('login_qr_check',{'key':_QR['key']},cookie='');body=result['body'];code=body.get('code')
        if code==803:
            cookies=result.get('cookies') or [];value=body.get('cookie') or ';'.join(cookies)
            if 'MUSIC_U=' not in value:raise ValueError('扫码成功但未取得有效登录状态。')
            save_cookie(value);_QR['until']=0;return {'state':'authorized','detail':'网易云账号已连接。'}
        return {'state':{800:'expired',801:'waiting',802:'confirming'}.get(code,'failed'),'detail':{800:'二维码已过期。',801:'等待扫码。',802:'已扫码，请在手机确认登录。'}.get(code,'扫码接口暂不可用，请稍后重试。')}

def playlists():
    account=status()
    if not account.get('logged_in'):return {**account,'playlists':[]}
    body=rpc('user_playlist',{'uid':str(account['user_id']),'limit':200})['body']
    return {'logged_in':True,'playlists':[{'id':p.get('id'),'name':str(p.get('name',''))[:160],'track_count':p.get('trackCount',0)} for p in body.get('playlist',[])[:200]],'detail':'显示账号创建及收藏的歌单，最多200个。'}

def tracks(playlist_id,offset=0):
    ident=clean_id(playlist_id)
    if not isinstance(offset,int) or not 0<=offset<=100000:raise ValueError('歌单页码无效。')
    body=rpc('playlist_track_all',{'id':ident,'limit':100,'offset':offset})['body']
    return {'tracks':[{'id':s.get('id'),'name':str(s.get('name',''))[:160],'artists':' / '.join(str(a.get('name','')) for a in s.get('ar',s.get('artists',[])))[:160],'duration_ms':s.get('dt',0)} for s in body.get('songs',[])[:100]],'offset':offset,'next_offset':offset+100 if len(body.get('songs',[]))==100 else None}

def search(query):
    if not isinstance(query,str) or not 1<=len(query.strip())<=100:raise ValueError('请输入1–100字的歌曲或歌手名称。')
    body=rpc('cloudsearch',{'keywords':query.strip(),'type':1,'limit':30,'offset':0})['body']
    result=body.get('result') or {}
    songs=result.get('songs') or []
    return {'tracks':[{'id':s.get('id'),'name':str(s.get('name',''))[:160],'artists':' / '.join(str(a.get('name','')) for a in s.get('ar',s.get('artists',[])))[:160],'duration_ms':s.get('dt',s.get('duration',0))} for s in songs[:30]],'detail':'搜索结果最多30首；播放遵循账号会员、版权和地区权限。'}


def song_url(song_id):
    ident=clean_id(song_id);body=rpc('song_url_v1',{'id':ident,'level':'standard'})['body'];rows=body.get('data') or [];row=rows[0] if rows else {};url=row.get('url')
    if not url:return {'available':False,'detail':'该歌曲当前无可用播放地址，可能受会员、版权或地区限制。'}
    parsed=urllib.parse.urlsplit(url);host=(parsed.hostname or '').lower()
    if parsed.scheme not in ('http','https') or not any(host==x or host.endswith('.'+x) for x in ('music.126.net','music.163.com','nosdn.127.net')):raise ValueError('平台返回了非预期的音乐地址。')
    url=urllib.parse.urlunsplit(('https',parsed.netloc,parsed.path,parsed.query,parsed.fragment))
    return {'available':True,'url':url,'trial':bool(row.get('freeTrialInfo')),'expires_seconds':row.get('expi',0),'detail':'平台返回试听片段。' if row.get('freeTrialInfo') else '已取得账号当前有权播放的音源。'}
