"""Opt-in local process-name timing. Never reads titles, text, images or keys."""
from __future__ import annotations
import contextlib, ctypes, datetime as dt, json, os, pathlib, sqlite3, threading, time

INTERVAL=5
RETENTION_DAYS=14


def windows_sample():
    if os.name!='nt':return {'app':'unknown','idle_seconds':None}
    from ctypes import wintypes
    user=ctypes.WinDLL('user32',use_last_error=True)
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    user.GetForegroundWindow.restype=wintypes.HWND
    user.GetWindowThreadProcessId.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.DWORD)]
    kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
    kernel.OpenProcess.restype=wintypes.HANDLE
    kernel.QueryFullProcessImageNameW.argtypes=[wintypes.HANDLE,wintypes.DWORD,wintypes.LPWSTR,ctypes.POINTER(wintypes.DWORD)]
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    class LASTINPUTINFO(ctypes.Structure):
        _fields_=[('cbSize',wintypes.UINT),('dwTime',wintypes.DWORD)]
    user.GetLastInputInfo.argtypes=[ctypes.POINTER(LASTINPUTINFO)]
    kernel.GetTickCount.restype=wintypes.DWORD
    info=LASTINPUTINFO();info.cbSize=ctypes.sizeof(info)
    idle=((kernel.GetTickCount()-info.dwTime)&0xffffffff)/1000 if user.GetLastInputInfo(ctypes.byref(info)) else None
    hwnd=user.GetForegroundWindow();pid=wintypes.DWORD()
    app='unknown'
    if hwnd:
        user.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
        handle=kernel.OpenProcess(0x1000,False,pid.value)
        if handle:
            try:
                size=wintypes.DWORD(32768);buf=ctypes.create_unicode_buffer(size.value)
                if kernel.QueryFullProcessImageNameW(handle,0,buf,ctypes.byref(size)):
                    app=pathlib.PureWindowsPath(buf.value).name[:120].lower()
            finally:kernel.CloseHandle(handle)
    return {'app':app,'idle_seconds':idle}


class Monitor:
    def __init__(self,data_dir,sampler=windows_sample):
        self.path=pathlib.Path(data_dir)/'activity.sqlite3'
        self.config=pathlib.Path(data_dir)/'activity-settings.json'
        self.sampler=sampler;self.lock=threading.RLock();self.stop_event=threading.Event()
        self.thread=None;self.current={};self.last=None;self.error=None
        self.enabled=False
        if self.config.exists():self.enabled=json.loads(self.config.read_text(encoding='utf-8')).get('enabled') is True
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with contextlib.closing(sqlite3.connect(self.path)) as c,c:
            c.execute('CREATE TABLE IF NOT EXISTS totals(day TEXT,app TEXT,foreground_seconds REAL,idle_seconds REAL,PRIMARY KEY(day,app))')
        self.pruned_day=None;self.prune()

    def prune(self):
        today=dt.date.today()
        if self.pruned_day==today:return
        with contextlib.closing(sqlite3.connect(self.path)) as c,c:
            c.execute('DELETE FROM totals WHERE day<?',((today-dt.timedelta(days=RETENTION_DAYS-1)).isoformat(),))
        self.pruned_day=today

    def configure(self,enabled):
        if not isinstance(enabled,bool):raise ValueError('监测开关必须是布尔值。')
        with self.lock:
            self.enabled=enabled;self.last=None;self.current={}
            temporary=self.config.with_suffix('.tmp');temporary.write_text(json.dumps({'enabled':enabled}),encoding='utf-8');temporary.replace(self.config)
        if enabled:self.start()
        return self.status()

    def start(self):
        with self.lock:
            if self.thread and self.thread.is_alive():return
            self.stop_event.clear();self.thread=threading.Thread(target=self._run,daemon=True,name='app-name-monitor');self.thread.start()

    def sample(self,stamp=None,day=None):
        with self.lock:
            if not self.enabled:return
            value=self.sampler();stamp=time.monotonic() if stamp is None else stamp
            day=day or dt.date.today().isoformat()
            # Attribute only short observed intervals; suspend/resume gaps are unknown.
            if self.last and 0<stamp-self.last[0]<=INTERVAL*3 and day==self.last[1]:
                elapsed=stamp-self.last[0];previous=self.current
                idle=min(elapsed,max(0,float(value['idle_seconds'] or 0))) if value.get('idle_seconds') is not None else 0
                with contextlib.closing(sqlite3.connect(self.path)) as c,c:
                    c.execute('INSERT INTO totals VALUES(?,?,?,?) ON CONFLICT(day,app) DO UPDATE SET foreground_seconds=foreground_seconds+excluded.foreground_seconds,idle_seconds=idle_seconds+excluded.idle_seconds',(day,previous.get('app','unknown'),elapsed,idle))
            self.current=value;self.last=(stamp,day);self.error=None

    def _run(self):
        while not self.stop_event.is_set():
            try:self.prune();self.sample()
            except Exception:
                with self.lock:self.error='暂时无法读取前台应用；未尝试提升权限。';self.last=None
            self.stop_event.wait(INTERVAL)

    def status(self):
        with self.lock:
            with contextlib.closing(sqlite3.connect(self.path)) as c,c:
                c.row_factory=sqlite3.Row
                rows=[dict(r) for r in c.execute('SELECT app,foreground_seconds,idle_seconds FROM totals WHERE day=? ORDER BY foreground_seconds DESC',(dt.date.today().isoformat(),))]
            return {'enabled':self.enabled,'running':bool(self.enabled and self.thread and self.thread.is_alive()),'current':self.current if self.enabled else {},'today':rows,'error':self.error,'interval_seconds':INTERVAL,'retention_days':RETENTION_DAYS,'scope':['foreground_app_name','duration','system_idle'],'storage':'local_only','note':'只记录程序名称和时长；闲置时间是前台时长的一部分。不能据此判断是否学习、专注或离开。锁屏等不可读取状态记为unknown。'}

    def close(self):self.stop_event.set()
