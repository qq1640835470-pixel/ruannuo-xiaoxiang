"""Integrated real handlers/adapters with synthetic transport; never real credentials."""
import contextlib
import datetime as dt
import http.cookiejar
import http.server
import json
import pathlib
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.request
from unittest.mock import patch


def desktop_host(folder, base):
    folder=pathlib.Path(folder).resolve(strict=True)
    control=folder/'control.json'
    if not (folder/'ISOLATED-034').is_file() or not base.startswith('http://127.0.0.1:') or not control.is_file() or json.loads(control.read_text(encoding='utf-8'))['base']!=base:
        raise ValueError('Only an explicitly marked isolated fixture can host this test.')
    import app_paths
    app_paths.HOME=folder;app_paths.DATA=folder/'data';app_paths.MODELS=folder/'models'
    import workspace_host
    workspace_host.DATA=app_paths.DATA;workspace_host.BASE=base
    import webview
    original=webview.create_window
    def create(title,*args,**kwargs):return original('软糯小祥 · 0.3.4隔离验收',*args,**kwargs)
    webview.create_window=create
    start=webview.start
    def diagnostic_start(*args,**kwargs):
        try:return start(*args,**kwargs)
        except Exception:
            import traceback
            (folder/'host-diagnostic.txt').write_text(traceback.format_exc(),encoding='utf-8')
            raise
    webview.start=diagnostic_start
    workspace_host.main()


if __name__=='__main__' and len(sys.argv)>1 and sys.argv[1]=='--host':
    desktop_host(sys.argv[2],sys.argv[3]);raise SystemExit()

if __name__=='__main__' and len(sys.argv)>1 and sys.argv[1]=='--serve':
    import app_paths
    isolated=pathlib.Path(sys.argv[2]).resolve()
    isolated.mkdir(parents=True,exist_ok=False);(isolated/'ISOLATED-034').touch()
    app_paths.HOME=isolated;app_paths.DATA=isolated/'data';app_paths.MODELS=isolated/'models'

import server
import learning
import learning_checks
import learning_adjustments
import providers
from test_learning_checks import QUESTIONS

MODEL='fixture/learning-034'
RETURNED='fixture/returned-034'


class Fixture:
    def __init__(self,folder):
        self.folder=pathlib.Path(folder);self.data=self.folder/'data';self.data.mkdir(parents=True,exist_ok=True)
        self.calls=[];self.stack=contextlib.ExitStack();self.original_socket=socket.create_connection
        today=dt.date.fromisoformat(server.now()[:10])
        self.req={'course':'合成电路分析','scope':'节点法与KCL','start_date':today.isoformat(),'deadline':(today+dt.timedelta(days=1)).isoformat(),'daily_minutes':120,'level':'尚不清楚'}
        self.plan={'title':'隔离验收节点法计划','outcome':'列出方程与疑问','tasks':[
            {'title':'复习节点法','content':'回顾参考节点与节点电压','date':self.req['start_date'],'minutes':40,'outcome':'说明节点法的变量定义','kind':'review'},
            {'title':'练习节点法','content':'按KCL列式练习','date':self.req['deadline'],'minutes':40,'outcome':'保留列式过程','kind':'practice'}]}

    def local_only(self,address,*args,**kwargs):
        if address[0] not in ('127.0.0.1','localhost','::1'):raise AssertionError('External network forbidden in isolated acceptance')
        return self.original_socket(address,*args,**kwargs)

    def post(self,url,key,body,provider,*args,**kwargs):
        if provider!='openrouter' or url!='https://openrouter.ai/api/v1/chat/completions':raise AssertionError('Unexpected simulated transport')
        if body['model']!=MODEL or body['provider']!={'require_parameters':True,'allow_fallbacks':False} or 'tools' in body:raise AssertionError('Incorrect route or parameters')
        instruction=body['messages'][0]['content'];raw=body['messages'][-1]['content'];stage='chat'
        if '学习需求整理器' in instruction:stage='analyze';value={'requirements':self.req,'questions':[]}
        elif '学习计划规划器' in instruction:stage='plan';value=self.plan
        elif '简短测验生成器' in instruction:stage='check';value=QUESTIONS
        elif '仅按给定参考答案辅助评价' in instruction:
            stage='evaluate';value={'feedback':[{'id':'3','verdict':'needs_review','basis':'参考要求定义节点电压','missing':'遗漏电压定义','improvement':'补充变量定义'}]}
        elif '学习计划调整助手' in instruction:
            stage='adjust';selected=json.loads(raw)
            task=next(t for t in selected['plan']['tasks'] if t['status'] not in ('done','cancelled'))
            fields={k:task[k] for k in learning_adjustments.TASK_FIELDS};fields['minutes']+=5
            value={'summary':'根据所选记录补充练习，保留已完成复习','changes':[{'action':'update','task_id':task['id'],'task':fields,'reason':'所选记录与测验建议核对变量定义，不判断真实掌握程度','evidence':['check:'+selected['checks'][0]['id']] if selected['checks'] else ['plan:'+task['id']]}]}
        else:value='模拟连接成功'
        if stage!='chat':
            if stage!='analyze':json.loads(raw)
            if body.get('response_format')!={'type':'json_object'}:raise AssertionError('Missing JSON parameter')
        expected_limit={'chat':1536,'analyze':2048,'plan':8192,'check':4096,'evaluate':4096,'adjust':8192}[stage]
        if body.get('max_tokens')!=expected_limit:raise AssertionError('Incorrect stage output limit')
        self.calls.append({'stage':stage,'body':body})
        return {'model':RETURNED,'choices':[{'message':{'content':json.dumps(value,ensure_ascii=False) if stage!='chat' else value},'finish_reason':'stop'}],
                'usage':{'prompt_tokens':20,'completion_tokens':10,'cost':.00004}}

    def __enter__(self):
        for change in [patch.object(server,'DATA',self.data),patch.object(server,'DB',self.data/'assistant.sqlite3'),patch.object(server,'MONITOR',None),
                       patch.object(providers,'CATALOG_PATH',self.data/'model-catalogue.json'),patch.object(providers.hub,'VAULT',self.folder/'no-real-vault.dpapi'),
                       patch('providers.hub.load_keys',return_value={'openrouter':'synthetic-fixture-only'}),patch('providers.post',side_effect=self.post),
                       patch('socket.create_connection',side_effect=self.local_only),patch('local_runtime._request',side_effect=AssertionError('No real local model')),
                       patch('local_runtime.status',return_value={'installed':False,'ready':False,'models':[],'selection':'auto'}),patch('local_models.selection',return_value='auto')]:self.stack.enter_context(change)
        row={'id':MODEL,'name':'隔离验收模型（模拟）','architecture':{'input_modalities':['text'],'output_modalities':['text']},'context_length':200000,'top_provider':{'max_completion_tokens':10000},'supported_parameters':['max_tokens','response_format'],'pricing':{'prompt':'0.000001','completion':'0.000002'}}
        providers.CATALOG_PATH.write_text(json.dumps({'openrouter':{'models':providers.normalize_models('openrouter',{'data':[row]}),'fetched_at':server.now()}}),encoding='utf-8')
        server.init()
        settings={'provider':'openrouter','chat_models':{**providers.MODELS,'openrouter':MODEL},'pet_provider':'local','pet_ai_enabled':False,'api_generation_enabled':True,'routing_enabled':False,'local_fallback_enabled':False}
        with server.connect() as c:
            for k,v in settings.items():c.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',(k,json.dumps(v)))
        class Handler(server.Handler):
            def do_GET(self):
                if self.path=='/api/acceptance-034':
                    self.begin_request()
                    if not self.permitted():return self.send(403,{'error':'仅限隔离会话'})
                    return self.send(200,{'isolated_synthetic_fixture':True})
                return super().do_GET()
        self.srv=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler);self.base=f'http://127.0.0.1:{self.srv.server_port}'
        self.thread=threading.Thread(target=self.srv.serve_forever,daemon=True);self.thread.start()
        self.opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()));self.opener.open(self.base+'/').close()
        return self

    def request(self,path,body=None,method='GET'):
        request=urllib.request.Request(self.base+path,data=json.dumps(body,ensure_ascii=False).encode() if body is not None else None,method=method,headers={'Content-Type':'application/json'})
        with self.opener.open(request) as reply:return json.load(reply)

    def __exit__(self,*args):
        self.srv.shutdown();self.srv.server_close();self.thread.join()
        if server.MONITOR:server.MONITOR.close()
        self.stack.close()


class IntegratedLearningTests(unittest.TestCase):
    def test_complete_http_flow_real_adapter_selected_evidence_usage_and_restart(self):
        with tempfile.TemporaryDirectory() as folder,Fixture(folder) as fixture:
            r=fixture.request
            analyzed=r('/api/learning/generate',{'stage':'analyze','text':'合成节点法学习要求'},'POST')
            draft=r('/api/learning/generate',{'stage':'plan','requirements':analyzed['requirements']},'POST')
            plan_body={'request_id':'integrated-plan','plan':draft['plan']}
            goal=r('/api/learning/confirm',plan_body,'POST');self.assertEqual(goal,r('/api/learning/confirm',plan_body,'POST'))
            saved=r('/api/learning/plans')['plans'][0];task=next(t for t in saved['tasks'] if t['learning']['kind']=='review')
            progress=r(f"/api/tasks/{task['id']}/progress",{'request_id':'integrated-progress','minutes':25,'note':'节点电压定义练习。'*180+'SELECTED_END'},'POST')
            r(f"/api/tasks/{task['id']}/progress",{'request_id':'unselected-progress','minutes':9,'note':'UNSELECTED_NOTE'},'POST')
            r(f"/api/tasks/{task['id']}",{'status':'done','request_id':'integrated-done'},'PATCH')
            check_body={'request_id':'integrated-check','task_id':task['id']}
            check=r('/api/learning/checks',check_body,'POST');self.assertEqual(check,r('/api/learning/checks',check_body,'POST'))
            submit={'request_id':'integrated-submit','answers':{'1':0,'2':1,'3':'先选参考节点并列式'},'evaluate_short':True}
            r(f"/api/learning/checks/{check['id']}/submit",submit,'POST');r(f"/api/learning/checks/{check['id']}/submit",submit,'POST')
            r(f"/api/learning/checks/{check['id']}",{'request_id':'integrated-fix','question_id':'3','verdict':'uncertain','note':'人工更正待核'},'PATCH')
            check_before=r(f"/api/learning/checks/{check['id']}");done_before=next(t for t in r('/api/learning/plans')['plans'][0]['tasks'] if t['id']==task['id'])
            selection={'goal_id':goal['goal_id'],'revision':r('/api/learning/plans')['plans'][0]['revision'],'include_plan':True,'include_remaining':True,'progress_ids':[progress['id']],'check_ids':[check['id']],'note':'只按本次选择微调'}
            preview=r('/api/learning/adjustments/preview',{'selection':selection},'POST')
            adjustment=r('/api/learning/adjustments/generate',{'request_id':'integrated-adjust','selection':selection,'preview_hash':preview['preview_hash'],'model':preview['model'],'confirmed':True},'POST')
            confirm={'request_id':'integrated-adjust-save','adjustment_id':adjustment['id'],'changes':adjustment['proposal']['changes']}
            result=r('/api/learning/adjustments/confirm',confirm,'POST');self.assertEqual(result,r('/api/learning/adjustments/confirm',confirm,'POST'))
            after=r('/api/learning/plans')['plans'];self.assertEqual(len(after),1);self.assertEqual(after[0]['goal']['id'],goal['goal_id'])
            self.assertEqual(next(t for t in after[0]['tasks'] if t['id']==task['id']),done_before);self.assertEqual(r(f"/api/learning/checks/{check['id']}"),check_before)
            sent=next(c['body']['messages'][-1]['content'] for c in fixture.calls if c['stage']=='adjust')
            self.assertGreater(len(sent),3000);self.assertIn('SELECTED_END',sent);self.assertNotIn('UNSELECTED_NOTE',sent)
            usage=r('/api/usage')['usage'];self.assertEqual(len(usage),5)
            for record in usage:
                metadata=json.loads(record['metadata']);self.assertEqual(metadata['requested_model'],MODEL);self.assertEqual(metadata['returned_model'],RETURNED);self.assertEqual(metadata['input_tokens'],20)
                self.assertEqual(metadata['output_tokens'],10);self.assertEqual(metadata['provider_reported_cost_usd'],.00004);self.assertFalse(metadata['billing_amount_confirmed'])
            server.init();self.assertEqual(r('/api/learning/plans')['plans'],after)
            code='import sqlite3,sys,learning,learning_checks;c=sqlite3.connect(sys.argv[1]);c.row_factory=sqlite3.Row;print(len(learning.listing(c)),len(learning_checks.listing(c)))'
            out=subprocess.run([sys.executable,'-c',code,str(server.DB)],capture_output=True,text=True,check=True);self.assertEqual(out.stdout.strip(),'1 1')


if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--serve':
        with Fixture(isolated) as fixture:
            (isolated/'control.json').write_text(json.dumps({'base':fixture.base,'pid':__import__('os').getpid()}),encoding='utf-8')
            print('Isolated synthetic fixture ready:',fixture.base,flush=True)
            import time
            while not (isolated/'STOP').exists():time.sleep(.25)
            (isolated/'transport-summary.json').write_text(json.dumps({'calls':[{'stage':c['stage'],'model':c['body']['model'],'input_length':len(c['body']['messages'][-1]['content'])} for c in fixture.calls]},indent=2),encoding='utf-8')
    elif len(sys.argv)>1 and sys.argv[1]=='--ui':
        with tempfile.TemporaryDirectory() as folder,Fixture(folder) as fixture:
            completed=subprocess.run(['node','test_learning_system_034_ui.cjs',fixture.base],cwd=server.ROOT,check=False)
            assert [c['stage'] for c in fixture.calls]==['analyze','plan','check','evaluate','adjust']
            selected=next(c['body']['messages'][-1]['content'] for c in fixture.calls if c['stage']=='adjust')
            assert 'SELECTED_END' in selected and 'UNSELECTED_NOTE' not in selected
            raise SystemExit(completed.returncode)
    else:unittest.main()
