"""Offline learning acceptance: temporary SQLite, synthetic model/HTTP responses only."""
import concurrent.futures
import copy
import contextlib
import http.cookiejar
import http.server
import json
import pathlib
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch
import learning
import server
import providers
import local_runtime
import local_models

REQ=dict(course='电路分析',scope='直流电路和节点法',start_date='2026-10-20',deadline='2026-10-21',daily_minutes=120,level='尚不清楚')
PLAN=dict(requirements=REQ,title='两天复习',outcome='整理公式并独立完成练习',tasks=[
    dict(title='复习节点法',content='回看定义与笔记',date='2026-10-20',minutes=40,kind='review',outcome='写出节点方程'),
    dict(title='练习节点法',content='选已有例题练习',date='2026-10-21',minutes=50,kind='practice',outcome='记录解题过程和疑问')])


class LearningTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.old=server.DATA,server.DB,server.MONITOR
        server.DATA=pathlib.Path(self.tmp.name);server.DB=server.DATA/'test.sqlite3';server.MONITOR=None
        self.cloud=patch('providers.chat',side_effect=AssertionError('No live API'));self.cloud.start()
        self.local=patch('local_runtime._request',side_effect=AssertionError('No live local model'));self.local.start()
        server.init()

    def tearDown(self):
        if server.MONITOR:server.MONITOR.close()
        server.DATA,server.DB,server.MONITOR=self.old
        self.local.stop();self.cloud.stop();self.tmp.cleanup()

    def save(self,plan=None,request='confirm1',**kw):
        return server.learning_save({'request_id':request,'plan':copy.deepcopy(PLAN if plan is None else plan),**kw})

    def listing(self):
        with server.connect() as c:return learning.listing(c)

    def count(self,table):
        with server.connect() as c:return c.execute('SELECT count(*) FROM '+table).fetchone()[0]

    def model(self,content,instruction,tokens,**kwargs):
        return json.dumps({k:v for k,v in PLAN.items() if k!='requirements'},ensure_ascii=False),{'provider':'fixture','returned_model':'fake'}

    def test_analyze_missing_information_then_generate_without_saving(self):
        response={'requirements':{**REQ,'scope':'','level':''},'questions':['具体复习哪些章节？','目前基础如何？']}
        call=lambda *args:(json.dumps(response),{'provider':'fixture'})
        result=learning.generate({'stage':'analyze','text':'两天复习电路，每天两小时'},call,'2026-10-20')
        self.assertEqual(result['requirements']['scope'],'');self.assertEqual(len(result['questions']),2)
        with self.assertRaises(ValueError):learning.generate({'stage':'plan','requirements':result['requirements']},self.model,'2026-10-20')
        draft=learning.generate({'stage':'plan','requirements':REQ},self.model,'2026-10-20')['plan']
        self.assertEqual(draft,PLAN)
        self.assertEqual(self.count('goals'),0);self.assertEqual(self.count('tasks'),0)
        # Discarding this browser-owned draft has nothing to roll back in SQLite.
        del draft
        self.assertEqual(self.listing(),[])

    def test_edit_confirm_link_sources_restart_and_process(self):
        draft=copy.deepcopy(PLAN);draft['tasks'][0]['title']='编辑后的复习任务'
        result=self.save(draft);saved=self.listing()[0]
        self.assertEqual(saved['goal']['id'],result['goal_id']);self.assertEqual(len(saved['tasks']),2)
        for task in saved['tasks']:
            self.assertEqual(task['goal_id'],saved['goal']['id']);self.assertIn('learning_confirm:confirm1:',task['source_id'])
        self.assertIn('编辑后的复习任务',[t['title'] for t in saved['tasks']])
        server.init();self.assertEqual(self.listing()[0]['goal']['id'],result['goal_id'])
        code='import sys,sqlite3,learning;c=sqlite3.connect(sys.argv[1]);c.row_factory=sqlite3.Row;p=learning.listing(c);print(len(p),len(p[0]["tasks"]))'
        run=subprocess.run([sys.executable,'-c',code,str(server.DB)],capture_output=True,text=True,check=True)
        self.assertEqual(run.stdout.strip(),'1 2')

    def test_duplicate_receipt_conflict_and_deletion_tombstone(self):
        first=self.save();self.assertEqual(first,self.save());self.assertEqual(self.count('tasks'),2)
        other=copy.deepcopy(PLAN);other['title']='不同目标'
        with self.assertRaises(ValueError):self.save(other)
        server.state_write('goals','delete',{},first['goal_id'])
        self.assertTrue(self.save()['deleted']);self.assertEqual(self.count('goals'),0)

    def test_concurrent_connections_exactly_once(self):
        body={'request_id':'parallel','plan':PLAN}
        def save(_):
            with server.connect() as c:return learning.save(c,body)
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(save,range(4)))
        self.assertTrue(all(r==results[0] for r in results));self.assertEqual(self.count('goals'),1);self.assertEqual(self.count('tasks'),2)

    def test_atomic_failure_rolls_back_and_same_request_can_retry(self):
        with server.connect() as c:c.execute("CREATE TRIGGER fail_task BEFORE INSERT ON tasks WHEN NEW.title='练习节点法' BEGIN SELECT RAISE(ABORT,'private db fault'); END")
        with self.assertRaises(sqlite3.DatabaseError):self.save()
        for table in ('goals','tasks','agent_state_requests'):self.assertEqual(self.count(table),0)
        with server.connect() as c:c.execute('DROP TRIGGER fail_task')
        self.save();self.assertEqual(self.count('tasks'),2)

    def test_existing_plan_edit_keeps_progress_and_status_cancels_removed(self):
        self.save();current=self.listing()[0];task=current['tasks'][0]
        server.task_update(task['id'],{'status':'done'})
        server.state_write('task_progress','create',{'note':'收获与困难','minutes':25},parent=task['id'])
        current=self.listing()[0]
        updated=copy.deepcopy(PLAN);updated['tasks'][0]['id']=task['id'];updated['tasks'][0]['content']='修正内容'
        self.save(updated,'edit1',goal_id=current['goal']['id'],revision=current['revision'])
        saved=self.listing()[0];kept=next(t for t in saved['tasks'] if t['id']==task['id'])
        self.assertEqual(kept['status'],'done');self.assertEqual(kept['actual_minutes'],25);self.assertEqual(kept['learning']['content'],'修正内容')
        self.assertEqual(len([t for t in saved['tasks'] if t['status']=='cancelled']),1)
        self.assertEqual(self.count('goals'),1);self.assertEqual(self.count('tasks'),3);self.assertIsNone(saved['mastery'])
        with self.assertRaises(ValueError):self.save(updated,'stale',goal_id=current['goal']['id'],revision=current['revision'])

    def test_failed_existing_plan_edit_rolls_back_all_changes(self):
        self.save();current=self.listing()[0];updated=copy.deepcopy(PLAN)
        updated['title']='不应保存的修改'
        for task,old in zip(updated['tasks'],current['tasks']):task['id']=old['id']
        with server.connect() as c:c.execute("CREATE TRIGGER fail_update BEFORE UPDATE ON tasks WHEN NEW.title='练习节点法' BEGIN SELECT RAISE(ABORT,'fixture failure'); END")
        with self.assertRaises(sqlite3.DatabaseError):self.save(updated,'failed-edit',goal_id=current['goal']['id'],revision=current['revision'])
        self.assertEqual(self.listing()[0],current)
        with server.connect() as c:self.assertIsNone(c.execute("SELECT 1 FROM agent_state_requests WHERE id='failed-edit'").fetchone())

    def test_task_start_defer_complete_progress_correct_dedup(self):
        self.save();task=self.listing()[0]['tasks'][0]
        for status in ('active','deferred','done'):
            server.task_update(task['id'],{'status':status,'scheduled_at':'2026-10-22'})
        body={'note':'会列式，计算仍有困难','minutes':35,'request_id':'progress1'}
        p=server.state_write('task_progress','create',body,parent=task['id'])
        self.assertEqual(p,server.state_write('task_progress','create',body,parent=task['id']))
        server.state_write('task_progress','update',{'minutes':20,'note':'更正记录'},p['id'])
        saved=self.listing()[0];t=next(t for t in saved['tasks'] if t['id']==task['id'])
        self.assertEqual(t['status'],'done');self.assertEqual(t['scheduled_at'],'2026-10-22');self.assertEqual(t['actual_minutes'],20)
        self.assertEqual(t['progress'][0]['note'],'更正记录');self.assertIsNone(saved['mastery'])

    def test_invalid_plan_and_unowned_task_roll_back(self):
        for change in (lambda p:p['tasks'][0].update(minutes=121),lambda p:p['tasks'][0].update(date='2026-10-25'),lambda p:p['tasks'][1].update(kind='study'),lambda p:p.update(requirements={**REQ,'level':''}),lambda p:p['tasks'][0].update(minutes=True),lambda p:p['tasks'][0].update(id='other'),lambda p:p.update(requirements={**REQ,'deadline':'2026-10-22'})):
            draft=copy.deepcopy(PLAN);change(draft)
            with self.assertRaises(ValueError):self.save(draft)
            self.assertEqual(self.count('goals'),0)
        result=self.save();saved=self.listing()[0];draft=copy.deepcopy(PLAN);draft['tasks'][0]['id']='unowned'
        with self.assertRaises(ValueError):self.save(draft,'unowned',goal_id=result['goal_id'],revision=saved['revision'])
        self.assertEqual(self.listing()[0]['revision'],saved['revision'])

    def test_invalid_model_and_failure_do_not_report_success(self):
        for raw in ('I made a plan','{}','[]','{"tasks":null}','{"title":"bad","outcome":"bad","tasks":[]}'):
            with self.assertRaises(ValueError):learning.generate({'stage':'plan','requirements':REQ},lambda *args:(raw,{}),'2026-10-20')
        with self.assertRaises(ValueError):learning.generate({'stage':'plan','requirements':REQ},self.model,'2026-10-22')
        self.assertEqual(self.count('tasks'),0)

    def test_selected_model_only_explicit_input_no_memory_or_history(self):
        server.add_message('user','PRIVATE_CHAT');server.add_task({'title':'PRIVATE_TASK'})
        with patch('server.context',side_effect=AssertionError('No context')),patch('server.settings',return_value={'provider':'gemini','api_generation_enabled':True,'chat_models':{'gemini':'chosen-model'}}),patch('providers.chat',return_value={'text':'{}','usage':{'estimate_cny':0},'model':'actual-model'}) as call:
            result,meta=server.learning_model('explicit request','JSON instruction',2048)
            args,kwargs=call.call_args
            self.assertEqual(args,('gemini',[{'role':'user','content':'explicit request'}],{}));self.assertEqual(kwargs['model'],'chosen-model');self.assertFalse(kwargs['allow_tools']);self.assertEqual(meta['returned_model'],'actual-model')
        with patch('server.settings',return_value={'provider':'gemini','api_generation_enabled':False}):
            with self.assertRaises(ValueError):server.learning_model('x','y',2048)

    def test_model_failure_keeps_unknown_reservation(self):
        with patch('providers.chat',side_effect=RuntimeError('private provider response')):
            with self.assertRaisesRegex(ValueError,'未生成计划') as exc:server.learning_model('request','instruction',8192)
        self.assertNotIn('private provider',str(exc.exception));self.assertEqual(self.count('tasks'),0)
        with server.connect() as c:self.assertEqual(c.execute('SELECT status FROM usage').fetchone()[0],'unknown')

    def test_local_model_no_memory_no_auto_switch_no_tools(self):
        with patch('server.settings',return_value={'provider':'local'}),patch('local_runtime.status',return_value={'installed':True}),patch('local_models.selection',return_value='auto'),patch('local_models.installed',return_value=True),patch('local_runtime.choose',return_value={'model':'manual-local'}),patch('providers.chat',return_value={'text':'{}','usage':{'estimate_cny':0},'model':'manual-local'}) as call:
            server.learning_model('request','instruction',8192)
            self.assertEqual(call.call_args.kwargs['model'],'manual-local');self.assertEqual(call.call_args.args[0],'local')
        with patch('local_models.selection',return_value='auto'),patch('local_models.installed',return_value=True),patch('local_runtime.choose',return_value={'model':'manual-local'}),patch('local_runtime._chat_once',side_effect=ValueError('invalid')) as one:
            with self.assertRaises(ValueError):local_runtime.chat([{'role':'user','content':'x'}],{},instruction='JSON',max_output_tokens=8192)
            self.assertEqual(one.call_count,1);self.assertEqual(one.call_args.args[1],{})

    @contextlib.contextmanager
    def http(self):
        srv=http.server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler);thread=threading.Thread(target=srv.serve_forever,daemon=True);thread.start()
        base=f'http://127.0.0.1:{srv.server_port}';opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()));opener.open(base+'/').close()
        def request(path,body=None,method='GET',headers=None):
            if method=='POST' and body is not None and (path in ('/api/learning/generate','/api/learning/checks') or path.endswith('/submit') and body.get('evaluate_short')):
                body={**body,'model_selection':body.get('model_selection',server.learning_selection())}
                body.setdefault('request_id',__import__('uuid').uuid4().hex)
            req=urllib.request.Request(base+path,data=json.dumps(body).encode() if body is not None else None,method=method,headers={'Content-Type':'application/json',**(headers or {})})
            with opener.open(req) as r:return json.load(r)
        try:yield base,request
        finally:srv.shutdown();srv.server_close();thread.join()

    def test_http_generate_confirm_read_auth_and_sanitized_db_failure(self):
        with self.http() as (base,request),patch('server.now',return_value='2026-10-20T10:00:00+08:00'):
            with self.assertRaises(urllib.error.HTTPError) as exc:urllib.request.urlopen(base+'/api/learning/plans')
            self.assertEqual(exc.exception.code,403)
            with self.assertRaises(urllib.error.HTTPError) as exc:request('/api/learning/confirm',{},'POST',{'Origin':'https://evil.test'})
            self.assertEqual(exc.exception.code,403)
            with patch('server.learning_model',side_effect=self.model):draft=request('/api/learning/generate',{'stage':'plan','requirements':REQ},'POST')['plan']
            self.assertEqual(request('/api/learning/plans')['plans'],[])
            body={'plan':draft,'request_id':'http-confirm'}
            first=request('/api/learning/confirm',body,'POST');self.assertEqual(first,request('/api/learning/confirm',body,'POST'))
            self.assertEqual(len(request('/api/learning/plans')['plans']),1)
            with patch('learning.save',side_effect=sqlite3.OperationalError('private db error')):
                with self.assertRaises(urllib.error.HTTPError) as exc:request('/api/learning/confirm',body,'POST')
                self.assertEqual(exc.exception.code,500);self.assertNotIn('private db',exc.exception.read().decode())

    def test_cloud_transport_json_instruction_output_limit_and_no_tools(self):
        self.cloud.stop()
        try:
            response={'candidates':[{'content':{'parts':[{'text':'{}'}]}}],'usageMetadata':{'promptTokenCount':4,'candidatesTokenCount':2},'modelVersion':'fixture'}
            with patch('providers.hub.load_keys',return_value={'gemini':'fixture'}),patch('providers.post',return_value=response) as post:
                providers.chat('gemini',[{'role':'user','content':'request'}],{},model=providers.MODELS['gemini'],allow_tools=False,instruction='JSON ONLY',max_output_tokens=8192)
                body=post.call_args.args[2];self.assertTrue(body['systemInstruction']['parts'][0]['text'].startswith('JSON ONLY'));self.assertEqual(body['generationConfig']['maxOutputTokens'],8192);self.assertNotIn('tools',body)
        finally:self.cloud.start()


if __name__=='__main__':unittest.main()
