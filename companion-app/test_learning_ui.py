"""Run headless Edge acceptance against a temporary local service, never private data."""
import pathlib
import subprocess
import tempfile
import threading
import http.server
from unittest.mock import patch
import server

if __name__=='__main__':
    with tempfile.TemporaryDirectory() as folder, patch.object(server,'DATA',pathlib.Path(folder)), patch.object(server,'DB',pathlib.Path(folder)/'ui.sqlite3'),patch.object(server,'MONITOR',None):
        server.init()
        srv=http.server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        thread=threading.Thread(target=srv.serve_forever,daemon=True);thread.start()
        try:
            result=subprocess.run(['node','test_learning_ui.cjs',f'http://127.0.0.1:{srv.server_port}'],cwd=server.ROOT,check=False)
        finally:
            srv.shutdown();srv.server_close();thread.join()
            if server.MONITOR:server.MONITOR.close()
        raise SystemExit(result.returncode)
