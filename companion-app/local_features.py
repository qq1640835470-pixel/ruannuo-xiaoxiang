"""Small, typed local capabilities. No shell, arbitrary files, or generated code execution."""
from __future__ import annotations
import ipaddress,json,os,pathlib,subprocess,sys,threading,time,urllib.parse,uuid
import runtime_log

ROOT=pathlib.Path(__file__).resolve().parent
PREFERENCE_DEFAULTS={'font_scale':1.0,'density':'comfortable','motion':'normal'}
_lock=threading.RLock()
_browsers=[]

def validate_preferences(body):
    if not isinstance(body,dict) or not body or set(body)-set(PREFERENCE_DEFAULTS):raise ValueError('仅支持字号、布局密度和动画偏好。')
    result={}
    for key,value in body.items():
        if key=='font_scale':
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not .9<=value<=1.3:raise ValueError('字号比例范围为0.9至1.3。')
            result[key]=round(value,2)
        elif key=='density':
            if value not in ('comfortable','compact'):raise ValueError('布局密度不支持。')
            result[key]=value
        elif key=='motion':
            if value not in ('normal','gentle','quiet'):raise ValueError('动画偏好不支持。')
            result[key]=value
    return result

def browser_url(value):
    if not isinstance(value,str) or not value.strip() or len(value)>2000:raise ValueError('请输入网页地址。')
    value=value.strip()
    if '://' not in value:value='https://'+value
    p=urllib.parse.urlsplit(value)
    host=(p.hostname or '').lower().rstrip('.')
    if p.scheme not in ('https','http') or not host or p.username or p.password:raise ValueError('浏览器只接受不含账号密码的HTTP/HTTPS网址。')
    if host=='localhost' or host.endswith(('.localhost','.local')) or '.' not in host:raise ValueError('这里仅打开公开网站。')
    try:
        if not ipaddress.ip_address(host).is_global:raise ValueError('这里不打开本机或内网地址。')
    except ValueError as exc:
        if '这里' in str(exc):raise
    if any(ord(c)<32 for c in value):raise ValueError('网址包含无效字符。')
    return urllib.parse.urlunsplit((p.scheme,p.netloc,p.path or '/',p.query,p.fragment))

def runtime_available():
    return os.name=='nt' and (ROOT/'.runtime'/'webview'/'__init__.py').is_file()

def queue_workspace(kind,url='',query=''):
    import workspace_queue
    return workspace_queue.queue(kind,url,query)

def open_browser(value,data_dir):
    return queue_workspace('browser',url=browser_url(value))


def browser_status(ident,data_dir):
    if not isinstance(ident,str) or len(ident)!=32 or any(c not in '0123456789abcdef' for c in ident):raise ValueError('浏览器编号无效。')
    file=pathlib.Path(data_dir)/'native-status'/(ident+'.json')
    if file.is_file():
        try:return json.loads(file.read_text(encoding='utf-8'))
        except (OSError,ValueError):pass
    with _lock:
        row=next(((p,i) for p,i in _browsers if i==ident),None)
        if row and row[0].poll() is not None:return {'id':ident,'status':'failed','detail':'浏览器进程已退出，未确认页面加载。'}
    return {'id':ident,'status':'starting','detail':'等待浏览器加载回执。'}

def local_status(data_dir):
    return {'schema_version':1,'browser':{'engine':'Microsoft Edge WebView2','component_available':runtime_available(),'layout':'same_window_split'},
            'capabilities':['typed_ui_preferences','local_health_check','metadata_diagnostics','native_browser','local_audio'],
            'permissions':[
                {'name':'软件自己的数据与日志','scope':'项目旁companion-data/companion-v01','enabled':True},
                {'name':'已支持程序启动','scope':'固定程序清单；无任意命令执行','enabled':True},
                {'name':'本地音乐','scope':'只读取你在文件选择器中选择的音乐；不上传','enabled':True},
                {'name':'公开网页','scope':'同窗右侧WebView2；网页无Python/系统工具接口','enabled':True},
                {'name':'管理员/持续监测/聊天读取/付款','scope':'未启用','enabled':False}],
            'self_improvement':'可调整已支持偏好和运行本地自检，不执行模型生成的代码。'}

def maintenance(data_dir,check='health'):
    if check not in ('health','reset_preferences'):raise ValueError('仅支持运行自检或恢复界面偏好。')
    if check=='reset_preferences':return {'preferences':dict(PREFERENCE_DEFAULTS),'changed':True}
    return {'ok':True,'checks':{'web_assets':all((ROOT/'web'/x).is_file() for x in ('app.js','index.html','companion.js')),
                                'data_directory':pathlib.Path(data_dir).is_dir(),'browser_component':runtime_available()},
            'note':'只核查本软件文件与数据目录；未扫描其他软件或联网调用模型。'}

LOCAL_TOOL={'name':'configure_local','description':'用户明确要求调整本软件时使用：字号font_scale 0.9至1.3、密度density comfortable/compact、动画motion normal/gentle/quiet；或operation=health运行本地自检。只改支持的设置，不修改源代码，不安装软件，不提升系统权限。讨论例子或否定要求不调用。',
 'parameters':{'type':'object','properties':{'operation':{'type':'string','enum':['preferences','health']},'font_scale':{'type':'number'},'density':{'type':'string','enum':['comfortable','compact']},'motion':{'type':'string','enum':['normal','gentle','quiet']}},'required':['operation']}}
