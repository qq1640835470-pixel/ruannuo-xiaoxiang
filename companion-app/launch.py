"""Double-click launcher. Local service, existing browser app window, no installation."""
import pathlib, subprocess, sys, threading, time, urllib.request, json, webbrowser
import server

URL=f'http://127.0.0.1:{server.PORT}'
APP_URL=URL+'/?ui=ruannuo-workspace-022'
def healthy():
    try:
        with urllib.request.urlopen(URL+'/api/health',timeout=1) as r:
            info=json.load(r)
            return info.get('app')=='study-life-companion' and info.get('version')==server.VERSION and info.get('build_id')==server.BUILD_ID
    except Exception:return False
def open_window():
    import workspace_queue
    workspace_queue.queue('focus')

def main():
    if healthy():open_window();return
    try:
        with urllib.request.urlopen(URL+'/api/health',timeout=2) as response:info=json.load(response)
        if info.get('app')=='study-life-companion' and (info.get('version')!=server.VERSION or info.get('build_id')!=server.BUILD_ID):
            subprocess.run([sys.executable,str(pathlib.Path(__file__).with_name('restart_local.py'))],timeout=20,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),check=True)
            if healthy():open_window();return
    except (OSError,ValueError,subprocess.SubprocessError):pass
    def later():
        for _ in range(60):
            if healthy():open_window();return
            time.sleep(.15)
    threading.Thread(target=later,daemon=True).start()
    try:server.run()
    except OSError:
        # A collision is never resolved by killing another process.
        if healthy():open_window()
        else:
            server.DATA.mkdir(parents=True,exist_ok=True)
            (server.DATA/'startup-error.txt').write_text('本机18764端口被其他程序占用。请让助手检查；未关闭其他程序。',encoding='utf-8')
if __name__=='__main__':main()
