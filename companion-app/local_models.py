"""Verified local model catalogue and deterministic, auditable model routing."""
from __future__ import annotations
import json,math,pathlib,re,subprocess,time
import app_paths,local_runtime_setup as setup

SMALL='qwen3-4b-q4_k_m'
LARGE='qwen3-8b-q4_k_m'
GEMMA='gemma3-4b-it-q4_0'
CATALOG={
    SMALL:{'label':'Qwen3 4B · Q4_K_M','file':setup.MODEL_NAME,'size':setup.MODEL_SIZE,'sha256':setup.MODEL_SHA,'layers':37},
    LARGE:{'label':'Qwen3 8B · Q4_K_M','file':'Qwen3-8B-Q4_K_M.gguf','size':5027783488,'sha256':'d98cdcbd03e17ce47681435b5150e34c1417f50b5c0019dd560e4882c5745785','layers':37},
    GEMMA:{'label':'Gemma 3 4B · QAT Q4_0 · 图像','file':setup.GEMMA_ASSETS[0]['file'],'size':setup.GEMMA_ASSETS[0]['size'],'sha256':setup.GEMMA_ASSETS[0]['sha256'],'layers':35,'context':8192,'projector':setup.GEMMA_ASSETS[1]}}

def assets(model):
    item=CATALOG[model]
    return [item,*([item['projector']] if item.get('projector') else [])]

def capabilities(model):
    return {'text':True,'image':model==GEMMA,'tools':model!=GEMMA}

def installed(model):
    try:
        for item in assets(model):
            path=setup.BASE/item['file'];proof=json.loads(path.with_suffix('.gguf.download.json').read_text(encoding='utf-8'))
            if not (path.is_file() and path.stat().st_size==item['size'] and proof.get('state')=='verified' and proof.get('sha256')==item['sha256']):return False
        return True
    except (OSError,ValueError):return False

def selection():
    try:
        value=json.loads((app_paths.DATA/'local-model-selection.json').read_text(encoding='utf-8'))['model']
        return value if value in ('auto',*CATALOG) else 'auto'
    except (OSError,ValueError,KeyError):return 'auto'

def select(model):
    if model not in ('auto',*CATALOG):raise ValueError('本机模型选择无效。')
    if model!='auto' and not installed(model):raise ValueError('所选本机模型尚未完成下载与校验。')
    path=app_paths.DATA/'local-model-selection.json';path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps({'model':model}),encoding='utf-8');temp.replace(path)
    return model

def choose(text,companion=False,requested=None,active=None,last_used=0,history=None):
    mode=requested if requested not in (None,'auto') else selection()
    if mode!='auto':
        if mode not in CATALOG:raise ValueError('本地模型编号无效。')
        return {'model':mode,'reason':'explicit_request' if requested not in (None,'auto') else 'manual_selection','difficulty':'manual','selection':mode}
    text=str(text);complex_task=not companion and (len(text)>280 or bool(re.search(r'推导|证明|求解|微分|积分|矩阵|电路分析|信号与系统|数据结构|调试|debug|代码|编程|架构|算法|多步|逐步分析|比较.{0,20}(?:方案|优缺点|原理)|分析.{0,16}(?:原因|方案|差异)|制定.{0,12}计划|规划|为什么.{0,25}(?:电路|公式|程序)',text,re.I)))
    continuation=bool(re.match(r'^(?:继续|接着|展开|详细|上一步|这一步|为什么|那.{0,5}呢)',text))
    if continuation and not companion and history:
        earlier=' '.join(str(row.get('content','')) for row in history[-6:-1] if row.get('role')=='user')
        complex_task=complex_task or bool(re.search(r'推导|证明|代码|算法|电路|积分|矩阵|架构|规划',earlier,re.I))
    target=LARGE if complex_task else SMALL
    reason='complex_task' if complex_task else 'short_companion' if companion else 'simple_task'
    if target==SMALL and active==LARGE and time.monotonic()-last_used<180:
        target=LARGE;reason='keep_recent_8b_to_avoid_reload'
    if not installed(target):
        other=SMALL if target==LARGE else LARGE
        if installed(other):target=other;reason='preferred_model_unavailable'
    return {'model':target,'reason':reason,'difficulty':'complex' if complex_task else 'simple','selection':'auto'}

def gpu_layers(model):
    try:
        result=subprocess.run(['nvidia-smi','--query-gpu=memory.free','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=3,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        free=int(result.stdout.strip().splitlines()[0]);item=CATALOG[model]
        # Conservative F16 KV/compute allowance; Gemma additionally reserves its projector.
        per_layer=item['size']/1024**2/item['layers']+64
        reserve=1024+(item['projector']['size']/1024**2+512 if item.get('projector') else 0)
        return max(0,min(item['layers'],math.floor((free-reserve)/per_layer)))
    except (OSError,ValueError,IndexError,subprocess.SubprocessError):return 0
