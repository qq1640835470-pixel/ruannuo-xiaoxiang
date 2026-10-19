"""Headless Edge and isolated temporary HTTP/SQLite; all model responses synthetic."""
import copy
import http.server
import json
import pathlib
import subprocess
import tempfile
import threading
from unittest.mock import patch
import server
from test_learning import PLAN
from test_learning_checks import QUESTIONS


if __name__=='__main__':
    calls=[]
    def model(content,instruction,tokens,**kwargs):
        calls.append(json.loads(content))
        if isinstance(calls[-1],list):
            return json.dumps({'feedback':[{'id':'3','verdict':'needs_review','basis':'需要节点电压定义','missing':'遗漏定义','improvement':'先写变量定义'}]}),{'provider':'fixture','returned_model':'synthetic-judge'}
        return json.dumps(QUESTIONS),{'provider':'fixture','returned_model':'synthetic-generator'}
    with tempfile.TemporaryDirectory() as folder, patch.object(server,'DATA',pathlib.Path(folder)),patch.object(server,'DB',pathlib.Path(folder)/'ui.sqlite3'),patch.object(server,'MONITOR',None),patch.object(server,'learning_model',side_effect=model),patch('providers.chat',side_effect=AssertionError('No live API')),patch('local_runtime._request',side_effect=AssertionError('No real local model')):
        server.init()
        server.learning_save({'request_id':'ui-plan','plan':copy.deepcopy(PLAN)})
        srv=http.server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        thread=threading.Thread(target=srv.serve_forever,daemon=True);thread.start()
        try:
            result=subprocess.run(['node','test_learning_checks_ui.cjs',f'http://127.0.0.1:{srv.server_port}'],cwd=server.ROOT,check=False)
            assert len(calls)==3, f'Unexpected model calls: {len(calls)}'
            assert set(calls[0])=={'title','content','outcome'}
            assert isinstance(calls[1],list) and len(calls[1])==1 and calls[1][0]['id']=='3'
            assert calls[2]['content']=='节点法' and calls[2]['title']=='自选知识点'
        finally:
            srv.shutdown();srv.server_close();thread.join()
            if server.MONITOR:server.MONITOR.close()
        raise SystemExit(result.returncode)
