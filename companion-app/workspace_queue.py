"""Local public-page workspace requests. Remote pages have no native bridge."""
import app_paths
import hashlib,json,os,pathlib,subprocess,sys,time,uuid
ROOT=pathlib.Path(__file__).resolve().parent
DATA=app_paths.DATA

def host_build():
    files=[ROOT/'app_paths.py',ROOT/'workspace_host.py',ROOT/'workspace_queue.py',*ROOT.glob('web/*.js'),*ROOT.glob('web/*.css'),ROOT/'web/index.html']
    return hashlib.sha256(b''.join(p.read_bytes() for p in sorted(files))).hexdigest()[:12]

def start_host():
    heartbeat=DATA/'workspace-heartbeat.json'
    try:
        info=json.loads(heartbeat.read_text())
        if time.time()-info['time']<8:
            if info.get('host_build')==host_build():return
            (DATA/'workspace-restart.request').touch()
    except (OSError,ValueError,KeyError):pass
    exe=pathlib.Path(sys.executable).with_name('pythonw.exe')
    if not exe.exists():exe=pathlib.Path(sys.executable)
    subprocess.Popen([str(exe),str(ROOT/'workspace_host.py')],cwd=ROOT,shell=False,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))

def queue(kind,url='',query=''):
    if kind not in ('browser','map','file_picker','close','focus'):raise ValueError('工作区类型不支持。')
    if kind=='browser':
        from local_features import browser_url
        url=browser_url(url)
    ident=uuid.uuid4().hex
    folder=DATA/'workspace-queue';folder.mkdir(parents=True,exist_ok=True)
    payload={'id':ident,'kind':kind,'url':url,'query':str(query)[:160],'created_at':time.time()}
    temp=folder/(ident+'.tmp');temp.write_text(json.dumps(payload,ensure_ascii=False),encoding='utf-8');temp.replace(folder/(ident+'.json'))
    start_host()
    return {'id':ident,'status':'requested','detail':'已交给软件右侧工作区，等待实际加载回执。'}
