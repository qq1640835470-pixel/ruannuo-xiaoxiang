"""On-demand, loopback-only portable Qwen inference; no cloud fallback or tool execution."""
from __future__ import annotations
import atexit,json,pathlib,re,secrets,subprocess,threading,time,urllib.request,urllib.error
import local_runtime_setup as setup
from web_tools import NoRedirect
MODEL='qwen3-4b-q4_k_m'
HOST='http://127.0.0.1:18766'
_LOCK=threading.RLock();_PROCESS=None;_KEY=secrets.token_urlsafe(32);_BACKEND='';_LAST_ERROR=''

def _request(path,payload=None,timeout=2):
    body=json.dumps(payload,ensure_ascii=False).encode('utf-8') if payload is not None else None
    request=urllib.request.Request(HOST+path,data=body,headers={'Content-Type':'application/json','Authorization':'Bearer '+_KEY})
    with urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect()).open(request,timeout=timeout) as response:
        return json.load(response)

def _configuration():
    try:
        config=json.loads((setup.BASE/'runtime.json').read_text(encoding='utf-8'))
        executable=pathlib.Path(config['executable']).resolve()
        if not executable.is_relative_to(setup.BASE.resolve()) or not executable.is_file() or not config.get('verified'):return None
        return config
    except (OSError,ValueError,KeyError):return None

def _healthy(timeout=1):
    return _request('/health',timeout=timeout).get('status')=='ok' and any(row.get('id')==MODEL for row in _request('/v1/models',timeout=timeout).get('data',[]))

def status():
    config=_configuration();model_file=setup.BASE/setup.MODEL_NAME
    try:verification=json.loads(model_file.with_suffix('.gguf.download.json').read_text(encoding='utf-8'))
    except (OSError,ValueError):verification={}
    installed=bool(config and model_file.is_file() and model_file.stat().st_size==setup.MODEL_SIZE and verification.get('state')=='verified' and verification.get('sha256')==setup.MODEL_SHA)
    ready=False
    if installed:
        try:ready=_healthy(timeout=.5)
        except (OSError,ValueError):pass
    partial=model_file.with_suffix('.gguf.part')
    return {'installed':installed,'ready':ready,'model':MODEL,'backend':_BACKEND or (config or {}).get('backend','not_installed'),'host':'127.0.0.1','port':18766,'model_bytes':setup.MODEL_SIZE,'downloaded_bytes':model_file.stat().st_size if model_file.exists() else partial.stat().st_size if partial.exists() else 0,'detail':'本机Qwen已就绪。' if ready else '本地组件已下载，首次调用按需启动。' if installed else '本地Qwen组件未就绪，需完成官方模型与便携运行时下载。','last_error':_LAST_ERROR}

def stop():
    global _PROCESS
    if _PROCESS is not None and _PROCESS.poll() is None:
        _PROCESS.terminate()
        try:_PROCESS.wait(timeout=5)
        except subprocess.TimeoutExpired:_PROCESS.kill()
    _PROCESS=None
atexit.register(stop)

def ensure_ready():
    global _PROCESS,_BACKEND,_LAST_ERROR
    with _LOCK:
        if status()['ready']:return
        config=_configuration()
        if not status()['installed']:raise ValueError('本地Qwen尚未安装完成，请先运行本机官方组件安装。')
        stop();executable=pathlib.Path(config['executable']);model_file=setup.BASE/setup.MODEL_NAME
        choices=[('cuda',99),('cpu',0)] if config.get('backend','').startswith('cuda') else [('cpu',0)]
        for backend,layers in choices:
            if backend=='cpu' and config.get('cpu_executable'):
                cpu=pathlib.Path(config['cpu_executable']).resolve()
                if cpu.is_relative_to(setup.BASE.resolve()) and cpu.is_file():executable=cpu
            log=setup.BASE/'llama-server.log'
            command=[str(executable),'-m',str(model_file),'--host','127.0.0.1','--port','18766','--alias',MODEL,'-c','16384','-np','1','-t','8','-ngl',str(layers),'--jinja','--reasoning','off','--api-key',_KEY,'--no-ui']
            with log.open('wb') as output:
                _PROCESS=subprocess.Popen(command,cwd=executable.parent,stdout=output,stderr=output,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            deadline=time.monotonic()+90
            while time.monotonic()<deadline:
                if _PROCESS.poll() is not None:break
                try:
                    if _healthy(timeout=1):
                        offloaded=re.search(r'offloaded (\d+)/\d+ layers',log.read_text(encoding='utf-8',errors='replace'))
                        _BACKEND='cuda' if offloaded and int(offloaded.group(1))>0 and backend=='cuda' else 'cpu' if backend=='cpu' or offloaded else 'llama.cpp'
                        _LAST_ERROR='';return
                except (OSError,ValueError):pass
                time.sleep(.3)
            stop()
        _LAST_ERROR='本机运行时启动失败，请检查本机llama-server.log；未调用云端。'
        raise ValueError(_LAST_ERROR)

def chat(history,context,companion=False,model=None,tools=None):
    if model not in (None,MODEL):raise ValueError('本地模型编号无效。')
    import providers,persistent_memory
    tools=[] if companion else (tools or [])
    messages=[];remaining=6000
    for message in reversed(history[-10:]):
        if message.get('role') not in ('user','assistant'):continue
        content=persistent_memory.redact(str(message.get('content','')))[:3000]
        if len(content)>remaining:break
        messages.insert(0,{'role':message['role'],'content':content});remaining-=len(content)
    raw_context=persistent_memory.redact(context if isinstance(context,str) else json.dumps(context,ensure_ascii=False))
    try:
        data=json.loads(raw_context)
        selected={k:data[k] for k in ('name','clock','machine_capabilities','user_memory','memory_policy','preferences','recent_weather','worldbook','tasks') if k in data}
        if 'worldbook' in selected:selected['worldbook']=selected['worldbook'][:5]
        if 'tasks' in selected:selected['tasks']=[{'title':str(t.get('title',''))[:80],'status':t.get('status')} for t in selected['tasks'][:4]]
        while len(json.dumps(selected,ensure_ascii=False))>5000:
            key=next((k for k in ('tasks','recent_weather','worldbook','user_memory') if isinstance(selected.get(k),list) and len(selected[k])>1),None)
            if key:selected[key].pop()
            elif 'recent_weather' in selected:selected.pop('recent_weather')
            else:break
        safe_context=json.dumps(selected,ensure_ascii=False)
    except (ValueError,TypeError,AttributeError):safe_context=raw_context[:4000]
    prompt=providers.system_prompt(safe_context)+'\n你在用户本机运行。不得声称已执行任何工具；只有结构化工具调用及本机返回结果才代表执行。/no_think'
    if companion:prompt+='\n只说一句自然中文，最多55字。不调用工具，不催促，不虚构观察。'
    if not tools:prompt+='\n本次没有可用工具，只能提供文字回复，不得声称已记录或执行操作。'
    body={'model':MODEL,'messages':[{'role':'system','content':prompt},*messages],'max_tokens':160 if companion else 768,'temperature':.7,'top_p':.8,'top_k':20,'min_p':0,'chat_template_kwargs':{'enable_thinking':False},'stream':False}
    if tools:body['tools']=[t if t.get('type')=='function' else {'type':'function','function':t} for t in tools];body['tool_choice']='auto'
    started=time.monotonic()
    with _LOCK:
        ensure_ready()
        try:result=_request('/v1/chat/completions',body,timeout=120)
        except (OSError,ValueError):raise ValueError('本机Qwen请求失败，未自动调用云端。') from None
    choices=result.get('choices') or []
    if not choices:raise ValueError('本地模型未返回有效结果。')
    message=choices[0].get('message') or {};text=message.get('content') or '';calls=[]
    names={t.get('function',t).get('name') for t in tools}
    for row in (message.get('tool_calls') or [])[:3]:
        function=row.get('function') or {};name=function.get('name')
        try:args=json.loads(function.get('arguments','{}'))
        except (ValueError,TypeError):raise ValueError('本地模型工具参数无效，未执行。') from None
        if name not in names or not isinstance(args,dict):raise ValueError('本地模型返回未授权工具，未执行。')
        calls.append({'name':name,'args':args})
    if '<tool_call>' in text and not calls:raise ValueError('本地模型未生成可解析的结构化工具调用，未执行。')
    if not text and not calls:raise ValueError('本地模型返回空回复。')
    usage=result.get('usage') or {}
    return {'text':text,'calls':calls,'model':MODEL,'usage':{'provider':'local','requested_model':MODEL,'returned_model':result.get('model',MODEL),'input_tokens':usage.get('prompt_tokens'),'output_tokens':usage.get('completion_tokens'),'elapsed_seconds':round(time.monotonic()-started,3),'estimate_cny':0,'price_basis':'local_inference_no_cloud_charge','tools_enabled':bool(tools),**({'purpose':'pet_chat'} if companion else {})}}
