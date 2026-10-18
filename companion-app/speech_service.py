"""Bounded local cache; only the explicitly free Fish model is allowed."""
import datetime as dt, hashlib, json, pathlib, re, threading, time
import providers,local_runtime

MODEL='s2.1-pro-free'
VOICE='318022ada9074bde869df6a5eef748a1'
FREE_UNTIL=dt.date(2026,11,30)
SOURCE='https://docs.fish.audio/developer-guide/models-pricing/pricing-and-rate-limits'
LOCK=threading.Lock()

def status(data_dir):
    path=pathlib.Path(data_dir)/'speech-state.json'
    saved=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    return {'model':MODEL,'voice':'丰川祥子（用户提供的音色目录）','free_only':True,
            'free_valid':dt.date.today()<=FREE_UNTIL,'free_until':FREE_UNTIL.isoformat(),
            'account_verified':saved.get('account_verified',False),'last_error':saved.get('last_error'),
            'source':SOURCE,'languages':['auto',*local_runtime.TRANSLATION_LANGUAGES],'translation_provider':'local',
            'note':'仅指定免费模型，不回退付费。选择目标语言时先用本机模型翻译，失败不发送原文冒充译文；实际口音需试听。'}

def generate(text,data_dir,trigger='manual',language='auto'):
    if not isinstance(text,str) or not text.strip() or len(text)>600:raise ValueError('语音文本需为1至600字。')
    text=re.sub(r'(?<![A-Za-z0-9_])xy(?![A-Za-z0-9_])','叉歪',text.replace('*','').strip(),flags=re.I)
    if not text:raise ValueError('语音文本需为1至600字。')
    if trigger not in ('manual','idle'):raise ValueError('语音请求类型无效。')
    if not isinstance(language,str) or language not in ('auto',*local_runtime.TRANSLATION_LANGUAGES):raise ValueError('请选择原文、中、日、粤或英语音。')
    directory=pathlib.Path(data_dir);cache=directory/'speech-cache';cache.mkdir(parents=True,exist_ok=True)
    identifier=hashlib.sha256((MODEL+'\0'+VOICE+'\0'+('translate-v1\0'+language+'\0' if language!='auto' else '')+text).encode()).hexdigest()
    target=cache/(identifier+'.mp3');record=directory/'speech-state.json'
    metadata=target.with_suffix('.json')
    with LOCK:
        saved=json.loads(record.read_text(encoding='utf-8')) if record.exists() else {}
        if target.is_file() and (language=='auto' or metadata.is_file()):
            details=json.loads(metadata.read_text(encoding='utf-8')) if language!='auto' else {'translated_text':text,'translation':None}
            return {'url':'/api/speech/audio/'+identifier,'cached':True,'model':MODEL,'free_only':True,'language':language,**details}
        if dt.date.today()>FREE_UNTIL:raise ValueError('免费语音期限需重新核实，已暂停生成；没有使用付费模型。')
        if saved.get('paused'):raise ValueError('免费语音上次未成功，已暂停自动生成；请在设置手动重试验证。')
        if trigger=='idle' and time.time()-saved.get('last_idle',0)<900:return {'skipped':'cooldown'}
        translation=None
        if language!='auto':
            translation=local_runtime.translate(text,language)
            text=translation['text'].replace('*','').strip()
            text=re.sub(r'(?<![A-Za-z0-9_])xy(?![A-Za-z0-9_])','叉歪',text,flags=re.I)
            if not text or len(text)>600:raise ValueError('译文为空或超过600字，未生成语音；请使用更短的文本。')
        details={'translated_text':text,'translation':({k:translation[k] for k in ('model','usage')} if translation else None)}
        if trigger=='idle':saved['last_idle']=time.time()
        try:
            audio=providers.speech(text,reference_id=VOICE,**({'language':language} if language!='auto' else {}))
            if language!='auto':metadata.write_text(json.dumps(details,ensure_ascii=False),encoding='utf-8')
            target.with_suffix('.tmp').write_bytes(audio);target.with_suffix('.tmp').replace(target)
            saved.update(account_verified=True,last_error=None,paused=False,last_success=time.time())
        except Exception as exc:
            saved.update(paused=True,last_error='免费语音请求失败（HTTP '+str(getattr(exc,'code','未知'))+'）；未回退收费型号。')
            raise ValueError(saved['last_error']) from None
        finally:record.write_text(json.dumps(saved,ensure_ascii=False),encoding='utf-8')
        # Evict only generated cache entries; never touch user audio.
        entries=sorted(cache.glob('[0-9a-f]'*64+'.mp3'),key=lambda p:p.stat().st_mtime,reverse=True)
        for path in entries[100:]:path.unlink();path.with_suffix('.json').unlink(missing_ok=True)
        return {'url':'/api/speech/audio/'+identifier,'cached':False,'model':MODEL,'free_only':True,'language':language,**details}

def audio_path(identifier,data_dir):
    if not re.fullmatch('[0-9a-f]{64}',identifier):raise ValueError('音频编号无效。')
    path=pathlib.Path(data_dir)/'speech-cache'/(identifier+'.mp3')
    if not path.is_file():raise ValueError('本机音频已过期，请重新生成。')
    return path

def retry(data_dir):
    path=pathlib.Path(data_dir)/'speech-state.json'
    with LOCK:
        saved=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
        saved.update(paused=False,last_error=None);path.write_text(json.dumps(saved),encoding='utf-8')
    return status(data_dir)
