"""Restart only this project's identified localhost service; never kill other apps."""
import http.cookiejar,json,pathlib,subprocess,sys,time,urllib.request,urllib.error
base='http://127.0.0.1:18764'
try:
    with urllib.request.urlopen(base+'/api/health',timeout=2) as r:info=json.load(r)
except OSError:info=None
if info:
    if info.get('app')!='study-life-companion':raise RuntimeError('端口属于其他应用，停止')
    op=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    op.open(base+'/').read()
    with op.open(urllib.request.Request(base+'/api/shutdown',data=b'{}',headers={'Content-Type':'application/json'}),timeout=3) as r:json.load(r)
    for _ in range(40):
        try:urllib.request.urlopen(base+'/api/health',timeout=.3).close()
        except OSError:break
        time.sleep(.1)
    else:raise RuntimeError('旧服务尚未退出，停止重复启动')
pythonw=pathlib.Path(sys.executable).with_name('pythonw.exe')
subprocess.Popen([str(pythonw),str(pathlib.Path(__file__).with_name('server.py'))],creationflags=subprocess.CREATE_NO_WINDOW)
for _ in range(50):
    try:
        with urllib.request.urlopen(base+'/api/health',timeout=.5) as r:info=json.load(r)
        if info.get('auto_open'):
            print(json.dumps(info,ensure_ascii=False));break
    except OSError:pass
    time.sleep(.1)
else:raise RuntimeError('新版服务尚未响应')
