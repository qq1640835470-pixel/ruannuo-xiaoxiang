"""Bounded, allowlisted runtime metadata. Never store bodies, headers, keys or raw exceptions."""
from __future__ import annotations
import contextvars,datetime as dt,json,pathlib,re,threading,traceback

request_id=contextvars.ContextVar('request_id',default='')
_path=None
_lock=threading.RLock()
MAX_BYTES=1024*1024
BACKUPS=3
FIELDS={'request_id','method','route','status','duration_ms','error_type','http_status','provider',
        'requested_model','returned_model','input_tokens','output_tokens','elapsed_seconds','estimate_cny',
        'action_id','draft_id','feedback_id','source_id','app','kind','count','version','file','line','frames'}

def configure(directory):
    global _path
    with _lock:
        folder=pathlib.Path(directory)/'logs';folder.mkdir(parents=True,exist_ok=True);_path=folder/'runtime.jsonl'

def safe_value(key,value):
    if isinstance(value,(int,float,bool)) or value is None:return value
    if key=='frames' and isinstance(value,list):return value[:6]
    if not isinstance(value,str):return None
    value=value[:120]
    if re.search(r'(sk-|AIza|AQ\.|Bearer\s|password|token=|key=)',value,re.I):return '[redacted]'
    if key in ('requested_model','returned_model') and not re.fullmatch(r'(?:gemini|deepseek|qwen|gpt-)[\w.:-]{1,90}',value):return 'unverified'
    if key=='route':return value.split('?',1)[0][:90]
    return re.sub(r'[\r\n\x00-\x1f]',' ',value)

def event(name,level='info',**fields):
    if not _path:return
    try:
        record={'time':dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).isoformat(timespec='milliseconds'),
                'level':level if level in ('info','warning','error') else 'info','event':re.sub(r'[^a-z0-9_]','',name)[:64]}
        fields.setdefault('request_id',request_id.get())
        for key,value in fields.items():
            if key in FIELDS and value is not None:record[key]=safe_value(key,value)
        line=json.dumps(record,ensure_ascii=False)+'\n'
        with _lock:
            if _path.exists() and _path.stat().st_size+len(line.encode())>MAX_BYTES:
                for n in range(BACKUPS,0,-1):
                    source=_path if n==1 else pathlib.Path(str(_path)+'.'+str(n-1))
                    if source.exists():source.replace(pathlib.Path(str(_path)+'.'+str(n)))
            with _path.open('a',encoding='utf-8') as output:output.write(line)
    except (OSError,ValueError,TypeError):pass

def error(name,exc,**fields):
    frames=[{'file':pathlib.Path(f.filename).name[:60],'line':f.lineno,'function':f.name[:60]}
            for f in traceback.extract_tb(exc.__traceback__)[-6:]]
    event(name,'error',error_type=type(exc).__name__,http_status=getattr(exc,'code',None),frames=frames,**fields)

def recent(limit=100):
    if not _path:return []
    records=[]
    with _lock:
        files=[pathlib.Path(str(_path)+'.'+str(n)) for n in range(BACKUPS,0,-1)]+[_path]
        for file in files:
            if not file.is_file():continue
            try:
                for line in file.read_text(encoding='utf-8').splitlines():
                    try:
                        r=json.loads(line)
                        if isinstance(r,dict):records.append({k:safe_value(k,v) if k in FIELDS else v for k,v in r.items() if k in FIELDS|{'time','level','event'}})
                    except (ValueError,TypeError):continue
            except OSError:continue
    return records[-min(max(int(limit),1),200):]
