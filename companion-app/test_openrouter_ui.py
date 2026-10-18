"""Headless settings acceptance with isolated SQLite and simulated HTTP only."""
import http.server
import pathlib
import subprocess
import tempfile
import threading
from unittest.mock import patch
import server
import providers
from test_openrouter import ROW, Response

if __name__=='__main__':
    with tempfile.TemporaryDirectory() as folder,patch.object(server,'DATA',pathlib.Path(folder)),patch.object(server,'DB',pathlib.Path(folder)/'test.db'),patch.object(providers,'CATALOG_PATH',pathlib.Path(folder)/'catalogue.json'),patch('providers.urllib.request.build_opener') as build:
        build.return_value.open.return_value=Response({'data':[ROW]})
        server.init()
        srv=http.server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        thread=threading.Thread(target=srv.serve_forever,daemon=True);thread.start()
        try:result=subprocess.run(['node','test_openrouter_ui.cjs',f'http://127.0.0.1:{srv.server_port}'],cwd=server.ROOT)
        finally:
            srv.shutdown();srv.server_close();thread.join()
            if server.MONITOR:server.MONITOR.close()
        raise SystemExit(result.returncode)
