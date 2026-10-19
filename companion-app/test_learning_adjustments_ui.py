"""Headless Edge, a real temporary local HTTP/SQLite service, and synthetic models."""
import copy
import datetime as dt
import http.server
import json
import pathlib
import subprocess
import tempfile
import threading
from unittest.mock import patch
import server
import learning
import learning_checks
from test_learning_checks import QUESTIONS

MODEL={'provider':'openrouter','model':'fixture/model'}


if __name__=='__main__':
    calls=[]
    def model(content,instruction,tokens,**kwargs):
        value=json.loads(content);calls.append(value)
        assert kwargs.get('expected_selection')==MODEL
        if value['user_request']=='模拟无效':return 'not JSON',{}
        if value['user_request']=='模拟预算不足':raise ValueError('预算不足')
        remaining=min((t for t in value['plan']['tasks'] if t['status'] not in ('done','cancelled')),key=lambda t:(t['date'],t['id']))
        task={k:remaining[k] for k in ('title','content','date','minutes','outcome','kind')};task['minutes']+=5
        changes=[{'action':'update','task_id':remaining['id'],'task':task,'reason':'根据所选记录补充节点法练习，不能据此认定掌握','evidence':['plan:'+remaining['id']]}]
        future=next((t for t in value['plan']['tasks'] if t['date']>value['today'] and t['status'] not in ('done','cancelled')),None)
        if future:changes.append({'action':'cancel','task_id':future['id'],'task':None,'reason':'优先处理当前练习，保留原任务历史','evidence':['plan:'+future['id']]})
        extra={**task,'title':'补充节点法练习','minutes':10,'kind':'practice'}
        changes.append({'action':'add','task_id':'','task':extra,'reason':'在原时间预算内补充练习','evidence':['plan:'+remaining['id']]})
        return json.dumps({'summary':'保留已完成复习，适当补充当前练习','changes':changes},ensure_ascii=False),{'provider':'fixture','returned_model':'synthetic'}
    with tempfile.TemporaryDirectory() as folder,patch.object(server,'DATA',pathlib.Path(folder)),patch.object(server,'DB',pathlib.Path(folder)/'ui.sqlite3'),patch.object(server,'MONITOR',None),patch.object(server,'learning_model',side_effect=model),patch.object(server,'learning_selection',return_value=MODEL),patch('providers.chat',side_effect=AssertionError('No live paid API')),patch('local_runtime._request',side_effect=AssertionError('No live local model')):
        server.init();today=dt.date.fromisoformat(server.now()[:10]);start=(today-dt.timedelta(days=1)).isoformat();end=(today+dt.timedelta(days=1)).isoformat()
        plan={'title':'三天节点法学习','outcome':'列出方程与疑问','requirements':{'course':'电路分析','scope':'节点法','start_date':start,'deadline':end,'daily_minutes':120,'level':'尚不清楚'},'tasks':[
            {'title':'已完成节点法复习','content':'回看节点法定义','date':start,'minutes':40,'outcome':'写出变量定义','kind':'review'},
            {'title':'延期节点法练习','content':'按KCL列式','date':today.isoformat(),'minutes':20,'outcome':'记录列式过程','kind':'practice'},
            {'title':'后续节点法学习','content':'整理节点法疑问','date':end,'minutes':30,'outcome':'列出疑问','kind':'study'}]}
        server.learning_save({'request_id':'ui-plan','plan':plan})
        with server.connect() as c:saved=learning.listing(c)[0]
        done=next(t for t in saved['tasks'] if t['title'].startswith('已完成'));remaining=next(t for t in saved['tasks'] if t['title'].startswith('延期'))
        server.state_write('tasks','update',{'status':'done'},done['id']);server.state_write('tasks','update',{'status':'deferred'},remaining['id'])
        server.state_write('task_progress','create',{'note':'SELECTED_NOTE_需要补充电压定义','minutes':25},parent=remaining['id'])
        server.state_write('task_progress','create',{'note':'UNSELECTED_PRIVATE_NOTE','minutes':10},parent=remaining['id'])
        for suffix in ('1','2'):
            r=learning_checks.execute(server.connect,'generate',{'request_id':'check'+suffix,'task_id':remaining['id']},lambda *a:(json.dumps(QUESTIONS),{}))
            learning_checks.execute(server.connect,'submit',{'request_id':'submit'+suffix,'answers':{'1':0,'2':1,'3':'列式'},'evaluate_short':False},check_id=r['id'])
        srv=http.server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler);thread=threading.Thread(target=srv.serve_forever,daemon=True);thread.start()
        try:
            result=subprocess.run(['node','test_learning_adjustments_ui.cjs',f'http://127.0.0.1:{srv.server_port}'],cwd=server.ROOT,check=False)
            assert len(calls)==5, len(calls)
            for payload in calls:
                assert 'UNSELECTED_PRIVATE_NOTE' not in json.dumps(payload,ensure_ascii=False)
                assert len(payload['progress'])<=1 and len(payload['checks'])<=1
        finally:
            srv.shutdown();srv.server_close();thread.join()
            if server.MONITOR:server.MONITOR.close()
        raise SystemExit(result.returncode)
