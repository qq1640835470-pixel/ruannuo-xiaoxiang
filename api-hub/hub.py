"""Local, read-only provider checks. API keys are Windows DPAPI protected."""
from __future__ import annotations
import argparse, concurrent.futures, ctypes, ctypes.wintypes as wt
import datetime as dt, html, json, os, pathlib, sys, urllib.request, urllib.error, webbrowser
from decimal import Decimal, InvalidOperation

ROOT = pathlib.Path(__file__).resolve().parent
VAULT = pathlib.Path(os.environ.get('LOCALAPPDATA', pathlib.Path.home())) / 'StudyLifeAssistant' / 'secrets' / 'providers.dpapi'
PROVIDERS = ('gemini', 'deepseek', 'fish_audio')
ENDPOINTS = {
    'gemini': 'https://generativelanguage.googleapis.com/v1beta/models?pageSize=100',
    'deepseek': 'https://api.deepseek.com/user/balance',
    'fish_audio': 'https://api.fish.audio/wallet/self/api-credit',
}

class Blob(ctypes.Structure):
    _fields_ = [('cbData', wt.DWORD), ('pbData', ctypes.POINTER(ctypes.c_ubyte))]

def protect(data: bytes, decrypt=False) -> bytes:
    if sys.platform != 'win32':
        raise RuntimeError('Windows DPAPI required')
    buf = ctypes.create_string_buffer(data)
    src = Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_ubyte)))
    dst = Blob()
    crypt = ctypes.WinDLL('crypt32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    if decrypt:
        fn = crypt.CryptUnprotectData
        fn.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, wt.DWORD, ctypes.POINTER(Blob)]
        ok = fn(ctypes.byref(src), None, None, None, None, 1, ctypes.byref(dst))
    else:
        fn = crypt.CryptProtectData
        fn.argtypes = [ctypes.POINTER(Blob), wt.LPCWSTR, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, wt.DWORD, ctypes.POINTER(Blob)]
        ok = fn(ctypes.byref(src), 'StudyLifeAssistant provider credentials', None, None, None, 1, ctypes.byref(dst))
    if not ok:
        raise RuntimeError('Windows credential encryption unavailable')
    try:
        return ctypes.string_at(dst.pbData, dst.cbData)
    finally:
        kernel.LocalFree(ctypes.cast(dst.pbData, ctypes.c_void_p))

def import_keys():
    keys = json.load(sys.stdin)
    if set(keys) != set(PROVIDERS) or not all(isinstance(v,str) and len(v)>10 and '\n' not in v and '\r' not in v for v in keys.values()):
        raise ValueError('Expected three provider credentials')
    raw = json.dumps(keys).encode()
    encrypted = protect(raw)
    if protect(encrypted, decrypt=True) != raw:
        raise RuntimeError('Credential encryption verification failed')
    VAULT.parent.mkdir(parents=True, exist_ok=True)
    if VAULT.exists():
        raise RuntimeError('Credential vault already exists; use a deliberate replacement workflow')
    VAULT.write_bytes(encrypted)
    print('Saved three credentials using Windows current-user DPAPI; verified round trip.')

def load_keys():
    return json.loads(protect(VAULT.read_bytes(), decrypt=True))

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # An authenticated request must never follow a redirect to another host.
        raise urllib.error.HTTPError(req.full_url, code, 'Redirect not permitted', headers, fp)

def request_json(provider, key):
    headers = {'Accept':'application/json', 'User-Agent':'StudyLifeAssistantBalance/0.1'}
    if provider == 'gemini': headers['x-goog-api-key'] = key
    else: headers['Authorization'] = 'Bearer '+key
    req = urllib.request.Request(ENDPOINTS[provider], headers=headers, method='GET')
    with urllib.request.build_opener(NoRedirect()).open(req, timeout=20) as response:
        if response.headers.get_content_type() != 'application/json':
            raise ValueError('Unexpected response format')
        data = response.read(1024*1024+1)
        if len(data)>1024*1024: raise ValueError('Response exceeds safe limit')
        return json.loads(data)

def number(value):
    if value is None or isinstance(value,bool): return None
    try:
        n = Decimal(str(value))
        return str(n) if n.is_finite() else None
    except (InvalidOperation, ValueError): return None

def normalize(provider, data):
    if provider == 'deepseek':
        rows = data.get('balance_infos')
        if not isinstance(rows,list) or not rows: raise ValueError('No balance data')
        balances=[]
        for row in rows:
            if row.get('currency') not in ('CNY','USD') or number(row.get('total_balance')) is None:
                raise ValueError('Invalid balance schema')
            balances.append({'currency':row['currency'],'total':number(row['total_balance']),
                'granted':number(row.get('granted_balance')),'topped_up':number(row.get('topped_up_balance'))})
        return {'status':'ok','balances':balances,'is_available':data.get('is_available'),'source':'官方余额API'}
    if provider == 'fish_audio':
        credit=number(data.get('credit'))
        if credit is None: raise ValueError('No API credit data')
        return {'status':'ok','api_credit':credit,'unit':'API credit 原始单位；货币口径待账单核对',
            'cumulative_top_up':number(data.get('cumulative_top_up')),'source':'官方API credit接口'}
    models=data.get('models')
    if not isinstance(models,list): raise ValueError('No model data')
    return {'status':'ok','authentication':'模型列表读取成功','model_count_first_page':len(models),
        'balance':None,'balance_status':'需从已登录的AI Studio结算页核对','source':'官方模型列表API；不是余额API'}

def check_one(provider, key):
    result={'provider':provider,'checked_at':dt.datetime.now(dt.timezone.utc).isoformat()}
    try:
        result.update(normalize(provider,request_json(provider,key)))
    except urllib.error.HTTPError as error:
        # Never record provider response bodies: they can echo credentials.
        result.update(status='error',http_status=error.code,
            error='认证未通过，请核对密钥或权限' if error.code in (401,403) else '接口返回错误，稍后再查询')
    except urllib.error.URLError:
        result.update(status='error',error='网络连接失败，余额未知')
    except Exception:
        result.update(status='error',error='响应无法核对，余额未知')
    return result

def refresh():
    keys=load_keys()
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        results=list(pool.map(lambda p:check_one(p,keys[p]),PROVIDERS))
    payload={'checked_at':dt.datetime.now(dt.timezone.utc).isoformat(),'mode':'on_demand_read_only','providers':results}
    if (ROOT/'google-observation.json').exists():
        payload['google_billing_observation']=json.loads((ROOT/'google-observation.json').read_text(encoding='utf-8'))
    # Keep only allowlisted normalized fields. No credentials, account IDs or raw replies.
    (ROOT/'latest.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    render(payload)
    return payload

def render(data):
    esc=lambda v:html.escape(str(v))
    localtime=lambda value:dt.datetime.fromisoformat(value).astimezone(dt.timezone(dt.timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S 北京时间')
    names={'gemini':'Google Gemini','deepseek':'DeepSeek','fish_audio':'Fish Audio'}
    cards=[]
    for p in data['providers']:
        details=[]
        if p['status'] != 'ok': details=[p.get('error','状态未知')]
        elif p['provider']=='deepseek':
            details=[f"可用余额 {b['total']} {b['currency']}；充值 {b['topped_up']}；赠金 {b['granted']}" for b in p['balances']]
        elif p['provider']=='fish_audio':
            details=[f"API credit {p['api_credit']}",p['unit']]
        else:
            details=[p['authentication'],'余额待结算页面确认；认证成功不代表余额充足']
        badge='查询成功' if p['status']=='ok' else '待处理'
        if p['provider']=='fish_audio' and p.get('api_credit') is not None and Decimal(p['api_credit'])<=0:badge='API credit 为零'
        cards.append('<article><h2>'+names[p['provider']]+'</h2><p class="badge">'+badge+'</p>'+''.join('<p>'+esc(t)+'</p>' for t in details)+'<small>查询时间 '+esc(localtime(p['checked_at']))+'</small></article>')
    obs=data.get('google_billing_observation')
    observed=''
    if obs:
        observed='<section><h2>Google 账单页面记录</h2><p>'+esc(obs.get('summary',''))+'</p><small>页面观察时间 '+esc(obs['observed_at'])+'；当前记录不会随本次API刷新自动更新。</small></section>'
    page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>API 余额查询</title><style>body{font:16px/1.7 "Microsoft YaHei",sans-serif;background:#f5f6fa;color:#172238;max-width:1120px;margin:48px auto;padding:0 24px}h1{font-size:30px}h2{font-size:21px}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:20px}article,section{padding:24px;background:white;border:1px solid #dee3ed;border-radius:12px;margin:18px 0}small{color:#596477}.badge{display:inline-block;background:#edf1f8;padding:3px 12px;border-radius:20px}a{color:#245bb2}footer{margin:28px 0}</style><h1>API 余额查询</h1><p>当前为按需查询版本。双击桌面的“API余额查询”可重新读取官方接口。金额与额度按各平台原始口径展示。</p><main>'''+''.join(cards)+'</main>'+observed+'''<footer><a href="https://aistudio.google.com/billing">Google 结算</a> · <a href="https://platform.deepseek.com/">DeepSeek 控制台</a> · <a href="https://fish.audio/app/billing">Fish Audio 结算</a><p>密钥由 Windows 当前用户加密保管。本页不包含密钥。网络错误不代表余额为零；跨平台币种和额度不合并。账单更新可能延迟。</p></footer></html>'''
    (ROOT/'balances.html').write_text(page,encoding='utf-8')

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--import-keys',action='store_true')
    parser.add_argument('--refresh',action='store_true')
    parser.add_argument('--open',action='store_true')
    args=parser.parse_args()
    if args.import_keys: import_keys();return
    if args.refresh:
        try: payload=refresh()
        except Exception:
            payload={'providers':[{'provider':p,'status':'error','error':'本机凭据暂不可用，需重新配置','checked_at':dt.datetime.now(dt.timezone.utc).isoformat()} for p in PROVIDERS]}
            render(payload)
        if sys.stdout:print(json.dumps(payload,ensure_ascii=False,indent=2))
    if args.open:webbrowser.open((ROOT/'balances.html').as_uri())

if __name__=='__main__': main()
