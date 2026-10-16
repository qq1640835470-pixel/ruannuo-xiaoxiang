"""Allowlisted application adapters. Models propose typed actions, never commands."""
from __future__ import annotations
import os, pathlib, re, subprocess, urllib.parse, uuid

WORKSPACE = pathlib.Path('D:/StudyLifePlan')
DESKTOP = pathlib.Path(os.environ.get('USERPROFILE', str(pathlib.Path.home()))) / 'Desktop'
APP_PATHS = {
    'qq': [r'C:\Program Files\Tencent\QQNT\QQ.exe'],
    'wechat': [r'C:\Program Files\Tencent\Weixin\Weixin.exe', r'C:\Program Files (x86)\Tencent\WeChat\WeChat.exe'],
    'edge':[r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',r'C:\Program Files\Microsoft\Edge\Application\msedge.exe'],
    'chrome':[r'C:\Program Files\Google\Chrome\Application\chrome.exe',r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe'],
    'notepad':[str(pathlib.Path(os.environ.get('WINDIR',r'C:\Windows'))/'System32'/'notepad.exe')],
    'calculator':[str(pathlib.Path(os.environ.get('WINDIR',r'C:\Windows'))/'System32'/'calc.exe')],
    'steam':[r'C:\Program Files (x86)\Steam\steam.exe',r'C:\Program Files\Steam\steam.exe'],
}
APP_NAMES={'qq':'QQ','wechat':'微信','edge':'Edge','chrome':'Chrome','notepad':'记事本','calculator':'计算器','steam':'Steam'}
SERVICES = {
    'bilibili': ('哔哩哔哩', 'https://www.bilibili.com/'),
    'amap': ('高德地图', 'https://www.amap.com/'),
    'baidu': ('百度地图', 'https://map.baidu.com/'),
    'meituan': ('美团', 'https://www.meituan.com/'),
    'taobao': ('淘宝闪购入口', 'https://www.taobao.com/'),
    'gemini_console': ('Google AI Studio', 'https://aistudio.google.com/'),
    'deepseek_console': ('DeepSeek 控制台', 'https://platform.deepseek.com/'),
    'fish_console': ('Fish Audio', 'https://fish.audio/'),
}
WEB_HOSTS = {'www.bilibili.com','www.amap.com','uri.amap.com','map.baidu.com','api.map.baidu.com',
             'www.meituan.com','www.taobao.com','aistudio.google.com','platform.deepseek.com','fish.audio'}

def app_path(name):
    return next((p for p in APP_PATHS.get(name, []) if pathlib.Path(p).is_file()), None)

def registry():
    entries=[]
    for app,name in [('qq','QQ'),('wechat','微信')]:
        ok=bool(app_path(app))
        entries.append(dict(id=app,name=name,status='可打开 · 消息接口未连接' if ok else '未发现安装位置',available=ok,
            description='可打开客户端、生成带收件对象的消息草稿。',capabilities=['打开本机客户端','准备消息草稿'],
            limitations=['本初版不读取或发送个人聊天消息','Codex聊天里的桌面控制工具不自动属于本软件']))
    installed=[APP_NAMES[k] for k in APP_PATHS if k not in ('qq','wechat') and app_path(k)]
    entries.append(dict(id='desktop_apps',name='其他电脑程序',status='可直接打开',available=bool(installed),
        description='明确说“打开程序名”即可自动启动，无需再次点击确认。',capabilities=installed,
        limitations=['仅启动已发现且支持的程序；不能执行任意命令']))
    for sid in ('amap','baidu','meituan','taobao','bilibili'):
        name,url=SERVICES[sid]
        ismap=sid in ('amap','baidu')
        entries.append(dict(id=sid,name=name,status='地图网页入口' if ismap else '网页入口',available=True,
            description='根据地点生成地图检索入口。' if ismap else '打开官方网页；后续操作由原平台接手。',
            capabilities=['地点检索链接','打开官方地图'] if ismap else ['打开官方网页'],
            limitations=['不读取当前位置，不返回实时路况或叫车订单'] if ismap else ['没有接通订单、支付或账号数据接口']))
    entries += [dict(id='providers',name='AI与余额',status='本机加密凭据',available=True,
        description='Gemini文字与工具规划、DeepSeek可选、三家余额/认证查询。',capabilities=['真实文字API','函数调用','按需余额查询'],
        limitations=['Google余额未知','模型API计费独立于Codex','不自动重试或回退付费模型']),
        dict(id='fish',name='Fish Audio',status='余额已接入 · 语音暂缓',available=False,description='官方免费期限资料冲突，远程语音暂不调用；先使用系统语音朗读。',
        capabilities=['API credit查询','已编写TTS适配器（未启用）'],limitations=['免费期当前是否有效待核实','不自动改用收费语音']),
        dict(id='mobile',name='手机与Watch S3',status='尚未连接',available=False,description='本版仅电脑本机运行。',
        capabilities=[],limitations=['未实现手机同步、手表推送或行为监测'])]
    return entries

def clean(value, limit=2000):
    if not isinstance(value,str): raise ValueError('参数必须是文字')
    value=value.strip()
    if not value or len(value)>limit: raise ValueError('参数为空或过长')
    if any(ord(c)<32 and c not in '\n\t' for c in value): raise ValueError('参数含控制字符')
    return value

def prepare(args):
    kind=args.get('kind')
    data={}
    if kind=='open_app':
        app=args.get('app')
        if app not in APP_PATHS or not app_path(app): raise ValueError('未发现这个应用的可用安装位置')
        data={'kind':kind,'app':app}; title='打开'+APP_NAMES[app]
        description='在本机启动'+APP_NAMES[app]+'。'
    elif kind=='map_search':
        app=args.get('app','amap')
        query=clean(args.get('query',''),200)
        if app=='amap': url='https://uri.amap.com/search?'+urllib.parse.urlencode({'keyword':query,'city':'深圳','view':'list','src':'StudyLifeAssistant'})
        elif app=='baidu': url='https://api.map.baidu.com/place/search?'+urllib.parse.urlencode({'query':query,'region':'深圳','output':'html','src':'webapp.StudyLife.Assistant'})
        else: raise ValueError('地图仅支持高德和百度')
        data={'kind':kind,'app':app,'query':query,'url':url};title=f'用{SERVICES[app][0]}查找：{query}'
        description='将在浏览器打开地点检索。未获取定位、路线时间或叫车价格。'
    elif kind=='open_service':
        app=args.get('app')
        if app not in SERVICES: raise ValueError('该服务尚无已核对入口')
        name,url=SERVICES[app];data={'kind':kind,'app':app,'url':url}; title='打开'+name
        description='打开官方网页。'+('淘宝闪购可能需要在淘宝手机App内进入；这里不代表已进入外卖频道。' if app=='taobao' else '账号、订单和支付继续由原平台处理。')
    elif kind=='prepare_message':
        recipient=clean(args.get('recipient','待确认对象'),120)
        content=clean(args.get('text',''),2000)
        app=args.get('app','qq')
        if app not in APP_PATHS: raise ValueError('通讯应用未支持')
        data={'kind':kind,'app':app,'recipient':recipient,'text':content};title='消息草稿 · '+recipient
        description=content+'\n（仅保存草稿；没有发送接口。你可以打开原应用手动发送。）'
    elif kind=='open_workspace':
        data={'kind':kind};title='打开助手资料目录';description=str(WORKSPACE)
    else: raise ValueError('这类操作当前尚未接通')
    return dict(id=uuid.uuid4().hex,title=title,description=description,status='prepared',payload=data)

def execute(action):
    p=action['payload'];kind=p['kind']
    if kind=='open_app':
        path=app_path(p['app'])
        if not path: raise ValueError('应用文件已不可用')
        subprocess.Popen([path],shell=False)
        return '已请求系统打开'+APP_NAMES[p['app']]+'。'
    if kind in ('map_search','open_service'):
        if p.get('app') in ('amap','baidu'):
            import local_features
            outcome=local_features.queue_workspace('map',query=p.get('query',''))
            return outcome['detail']
        url=p['url'];u=urllib.parse.urlsplit(url)
        if u.scheme!='https' or u.hostname not in WEB_HOSTS or u.username or u.password:
            raise ValueError('链接不在已核对的服务范围内')
        os.startfile(url)
        return '已请求系统打开网页；网页加载和平台后续操作仍由浏览器接手。'
    if kind=='open_workspace':
        os.startfile(str(WORKSPACE));return '已请求打开助手资料目录。'
    if kind=='prepare_message':
        return '草稿已保留在本机，没有向任何人发送。'
    raise ValueError('操作不可执行')

TOOLS=[dict(name='prepare_action',description='为用户明确要求的操作创建结构化动作；打开程序/网页由协调器自动执行，消息仅为草稿。',parameters={
    'type':'object','properties':{
        'kind':{'type':'string','enum':['open_app','map_search','open_service','prepare_message','open_workspace']},
        'app':{'type':'string','description':'qq/wechat/edge/chrome/notepad/calculator/steam/amap/baidu/meituan/taobao/bilibili/gemini_console/deepseek_console/fish_console'},
        'query':{'type':'string'},'recipient':{'type':'string'},'text':{'type':'string'}},'required':['kind']}),
    dict(name='create_task',description='只有用户明确要求添加或记下任务时才保存本机任务，不能把建议自动加入日程。',parameters={
        'type':'object','properties':{'title':{'type':'string'},'details':{'type':'string'},
        'scheduled_at':{'type':'string','description':'若用户指定时间，使用Asia/Shanghai的YYYY-MM-DDTHH:MM；未指定留空。'}},'required':['title']}),
    dict(name='show_balances',description='读取本机最新余额快照，不把它当成刚刷新；用户可另点刷新。',parameters={'type':'object','properties':{}}),
    dict(name='capture_feedback',description='用户提出对本软件/助手的改进要求、使用体验或交流偏好时，将其精简为暂存反馈；仅本机保存，不发送Codex，不执行软件修改。不要把日常私事或学习问题当软件反馈。',parameters={
        'type':'object','properties':{'title':{'type':'string','description':'简短主题'},
        'summary':{'type':'string','description':'简洁准确地概括用户要求、出现问题和期望效果，不扩大原意、不编造原因。'},
        'source_quote':{'type':'string','description':'从本次或最近用户消息中逐字摘取相关原话，不改写；系统会核对来源。'}},'required':['title','summary']})]
