"""Temporary databases and synthetic models only; no real model or private data."""
import concurrent.futures
import copy
import json
import sqlite3
import subprocess
import sys
import threading
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch
import agent_state
import learning
import learning_checks as checks
import server
import test_learning as fixtures

QUESTIONS={'questions':[
    {'type':'choice','prompt':'节点法首先需要选定什么？','options':['参考节点','材料密度','颜色'],'answer':0,'explanation':'选参考节点以定义节点电压。','evidence':'节点法'},
    {'type':'choice','prompt':'节点方程依据哪个定律？','options':['KCL','光的折射'],'answer':0,'explanation':'按节点电流守恒列方程。','evidence':'节点法'},
    {'type':'short','prompt':'说明列出节点方程的基本过程。','options':[],'answer':'选参考节点，标电压，按KCL列方程。','explanation':'重点核对变量定义和电流方向。','evidence':'节点法'}]}


class CheckTests(unittest.TestCase):
    setUp=fixtures.LearningTests.setUp
    tearDown=fixtures.LearningTests.tearDown
    save=fixtures.LearningTests.save
    listing=fixtures.LearningTests.listing
    count=fixtures.LearningTests.count
    http=fixtures.LearningTests.http

    def model(self,*args,**kwargs):return json.dumps(QUESTIONS,ensure_ascii=False),{'provider':'fixture','returned_model':'synthetic'}

    def generate(self,request='gen1',**kw):
        if not kw:
            if not self.listing():self.save()
            kw={'task_id':self.listing()[0]['tasks'][0]['id']}
        return checks.execute(server.connect,'generate',{'request_id':request,**kw},self.model)

    def get(self,i,public=True):
        with server.connect() as c:return checks.get(c,i,public)

    def submit(self,i,request='sub1',evaluate=False,call=None):
        return checks.execute(server.connect,'submit',{'request_id':request,'answers':{'1':0,'2':1,'3':'选参考节点再按KCL列式'},'evaluate_short':evaluate},call,i)

    def test_task_scope_snapshot_no_history_or_goal_context(self):
        self.save();task=self.listing()[0]['tasks'][0]
        server.add_message('user','UNRELATED_CHAT')
        server.state_write('task_progress','create',{'note':'PRIVATE_PROGRESS'},parent=task['id'])
        seen=[]
        def model(content,*args):seen.append(content);return self.model()
        r=checks.execute(server.connect,'generate',{'task_id':task['id'],'request_id':'scope'},model)
        item=self.get(r['id']);payload=json.loads(seen[0])
        self.assertEqual(set(payload),{'title','content','outcome'})
        for token in ('UNRELATED_CHAT','PRIVATE_PROGRESS','daily_minutes','requirements'):
            self.assertNotIn(token,seen[0])
        self.assertEqual(item['task_id'],task['id']);self.assertEqual(item['goal_id'],task['goal_id'])
        self.assertNotIn('answer',item['questions'][0]);self.assertEqual(item['schema_version'],1)
        original=self.get(r['id'],False)['questions']
        server.state_write('tasks','update',{'title':'后来修改'},task['id'])
        self.assertEqual(self.get(r['id'])['scope']['title'],task['title'])
        self.assertEqual(self.get(r['id'],False)['questions'],original)

    def test_explicit_topic_not_linked_and_exclusive(self):
        r=self.generate(topic='节点法');item=self.get(r['id'])
        self.assertEqual(item['task_id'],'');self.assertEqual(item['goal_id'],'')
        with self.assertRaises(ValueError):self.generate('both',task_id='fake',topic='节点法')
        with self.assertRaises(ValueError):self.generate('empty',topic='')
        with self.assertRaises(ValueError):self.generate('missing',task_id='missing')

    def test_invalid_generation_never_creates_valid_check(self):
        invalid=[]
        for field,value in [('type','essay'),('options',['same','same']),('answer',True),('answer',8),('explanation',''),('evidence','无关知识'),('prompt','x'*1001)]:
            q=copy.deepcopy(QUESTIONS);q['questions'][0][field]=value;invalid.append(q)
        invalid += [{'questions':[]},{'questions':QUESTIONS['questions']*2},{'error':'范围不足'},'not-json']
        for i,value in enumerate(invalid):
            call=lambda *a,v=value:(json.dumps(v),{})
            with self.assertRaises(ValueError):checks.execute(server.connect,'generate',{'request_id':f'bad{i}','topic':'节点法'},call)
        self.assertEqual(self.count('learning_checks'),0)
        call=lambda *a:(_ for _ in ()).throw(TimeoutError('secret provider error'))
        with self.assertRaises(ValueError) as exc:checks.execute(server.connect,'generate',{'request_id':'timeout','topic':'节点法'},call)
        self.assertNotIn('secret',str(exc.exception));self.assertEqual(self.count('learning_checks'),0)

    def test_deterministic_choices_reference_and_unassessed_short(self):
        i=self.generate()['id'];self.submit(i);item=self.get(i)
        self.assertEqual([r['verdict'] for r in item['results']],['correct','incorrect','uncertain'])
        self.assertEqual(item['results'][2]['source'],'not_assessed')
        self.assertEqual(item['questions'][0]['answer'],0);self.assertIsNone(item['mastery'])
        self.assertEqual(item['answers']['2'],1);self.assertTrue(item['submitted_at'])

    def test_subjective_assistance_only_selected_short_no_choices_or_history(self):
        i=self.generate()['id'];seen=[]
        response={'feedback':[{'id':'3','verdict':'needs_review','basis':'参考要求标注节点电压','missing':'未标电压','improvement':'补出电压定义'}]}
        def model(content,*args):seen.append(json.loads(content));return json.dumps(response),{'provider':'fixture','returned_model':'judge'}
        self.submit(i,evaluate=True,call=model);item=self.get(i)
        self.assertEqual(len(seen),1);self.assertEqual(len(seen[0]),1);self.assertEqual(seen[0][0]['id'],'3')
        self.assertIn('reference',seen[0][0]);self.assertEqual(item['results'][0]['verdict'],'correct')
        self.assertEqual(item['questions'][0]['answer'],0);self.assertEqual(item['results'][2]['missing'],'未标电压')

    def test_subjective_failure_or_invalid_output_saved_without_fake_grade(self):
        for n,value in enumerate([TimeoutError('private'),{'feedback':[]},{'feedback':[{'id':'1','verdict':'correct'}]},'bad']):
            i=self.generate(f'gen{n}')['id']
            def model(*a):
                if isinstance(value,Exception):raise value
                return json.dumps(value),{}
            self.submit(i,f'sub{n}',True,model);item=self.get(i)
            self.assertEqual(item['status'],'submitted');self.assertEqual(item['results'][2]['verdict'],'uncertain')
            self.assertEqual(item['results'][2]['source'],'not_assessed');self.assertEqual(item['evaluation_model']['status'],'failed')
            self.assertEqual(item['results'][0]['verdict'],'correct')

    def test_answer_validation_no_model_no_submit(self):
        i=self.generate()['id']
        for n,a in enumerate([{}, {'1':True,'2':1,'3':'a'},{'1':4,'2':1,'3':'a'},{'1':0,'2':1,'3':''},{'1':0,'2':1,'3':'a'*2001}]):
            with self.assertRaises(ValueError):checks.execute(server.connect,'submit',{'request_id':f'invalid{n}','answers':a,'evaluate_short':True},lambda *a:self.fail('model called'),i)
        self.assertEqual(self.get(i)['status'],'generated')

    def test_generate_retry_no_model_conflict_and_deleted_task(self):
        self.save();task=self.listing()[0]['tasks'][0];body={'request_id':'repeat','task_id':task['id']}
        with patch('test_learning_checks.CheckTests.model',side_effect=self.model) as model:
            r=checks.execute(server.connect,'generate',body,model)
            server.state_write('tasks','delete',{},task['id'])
            self.assertEqual(checks.execute(server.connect,'generate',body,model),r);self.assertEqual(model.call_count,1)
        with self.assertRaises(ValueError):checks.execute(server.connect,'generate',{**body,'count':4},self.model)

    def test_failed_and_interrupted_request_never_auto_retries_after_restart(self):
        body={'request_id':'failed','topic':'节点法'}
        with self.assertRaises(ValueError):checks.execute(server.connect,'generate',body,lambda *a:('oops',{}))
        with self.assertRaises(ValueError):checks.execute(server.connect,'generate',body,lambda *a:self.fail('retry'))
        body={'request_id':'crashed','topic':'节点法'}
        with server.connect() as c:checks.claim(c,'generate','',body)
        server.init()
        with self.assertRaises(ValueError):checks.execute(server.connect,'generate',body,lambda *a:self.fail('restart retry'))

    def test_concurrent_generation_one_model_call_and_record(self):
        started,release=threading.Event(),threading.Event();body={'request_id':'concurrent','topic':'节点法'};calls=[]
        def model(*a):calls.append(1);started.set();release.wait(5);return self.model()
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            first=pool.submit(checks.execute,server.connect,'generate',body,model);self.assertTrue(started.wait(5))
            with self.assertRaises(ValueError):checks.execute(server.connect,'generate',body,model)
            release.set();result=first.result()
        self.assertEqual(len(calls),1);self.assertEqual(self.count('learning_checks'),1)
        self.assertEqual(checks.execute(server.connect,'generate',body,model),result)

    def test_concurrent_submit_different_ids_no_duplicate_evaluation(self):
        i=self.generate()['id'];started,release=threading.Event(),threading.Event();calls=[]
        def model(*a):calls.append(1);started.set();release.wait(5);return '{}',{}
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            first=pool.submit(self.submit,i,'subA',True,model);self.assertTrue(started.wait(5))
            with self.assertRaises(ValueError):self.submit(i,'subB',True,model)
            release.set();first.result()
        self.assertEqual(len(calls),1)
        self.submit(i,'subA',True,lambda *a:self.fail('retry'))

    def test_correction_delete_tombstone_no_resurrection(self):
        i=self.generate()['id'];self.submit(i)
        body={'request_id':'fix','question_id':'1','verdict':'uncertain','note':'模型参考答案有争议，待查教材'}
        r=checks.execute(server.connect,'correct',body,check_id=i)
        self.assertEqual(checks.execute(server.connect,'correct',body,check_id=i),r)
        item=self.get(i);self.assertEqual(len(item['corrections']),1);self.assertEqual(item['results'][0]['verdict'],'correct')
        self.assertEqual(item['questions'][0]['answer'],0)
        checks.execute(server.connect,'delete',{'request_id':'delete'},check_id=i)
        self.assertTrue(checks.execute(server.connect,'correct',body,check_id=i)['deleted'])
        self.assertTrue(self.submit(i)['deleted']);self.assertTrue(self.generate()['deleted'])
        with self.assertRaises(ValueError):self.get(i)
        with server.connect() as c:
            receipts=[dict(r) for r in c.execute('SELECT * FROM learning_check_requests')]
        self.assertNotIn('节点法',json.dumps(receipts,ensure_ascii=False));self.assertEqual(self.count('learning_checks'),0)

    def test_migration_repeat_init_restart_process_and_old_state_unchanged(self):
        self.save();task=self.listing()[0]['tasks'][0]
        server.state_write('tasks','update',{'status':'done'},task['id'])
        server.state_write('task_progress','create',{'minutes':23,'note':'原有学习记录'},parent=task['id'])
        before=self.listing();i=self.generate()['id'];self.submit(i)
        server.init();server.init();self.assertEqual(before,self.listing());self.assertEqual(self.get(i)['status'],'submitted')
        code='import sqlite3,sys,learning_checks;c=sqlite3.connect(sys.argv[1]);c.row_factory=sqlite3.Row;print(learning_checks.listing(c)[0]["status"])'
        out=subprocess.run([sys.executable,'-c',code,str(server.DB)],capture_output=True,text=True,check=True)
        self.assertEqual(out.stdout.strip(),'submitted')
        # Simulate the legacy database without these two additive tables.
        with server.connect() as c:
            c.execute('DROP TABLE learning_checks');c.execute('DROP TABLE learning_check_requests')
        server.init();self.assertEqual(before,self.listing());self.assertEqual(self.count('learning_checks'),0)

    def test_atomic_save_failure_no_partial_record_or_retry_model(self):
        with server.connect() as c:c.execute("CREATE TRIGGER fail_check BEFORE INSERT ON learning_checks BEGIN SELECT RAISE(ABORT,'private error'); END")
        with self.assertRaises(ValueError):self.generate(topic='节点法')
        self.assertEqual(self.count('learning_checks'),0)
        with self.assertRaises(ValueError):self.generate(topic='节点法')

    def test_explicit_future_selection_only(self):
        i=self.generate()['id'];self.submit(i);other=self.generate('other')['id']
        with server.connect() as c:
            self.assertEqual([r['id'] for r in checks.selected_results(c,[i])],[i])
            with self.assertRaises(ValueError):checks.selected_results(c,[])
            with self.assertRaises(ValueError):checks.selected_results(c,[other])

    def test_three_to_five_and_scope_preview_conflict(self):
        for n in (3,4,5):
            value=copy.deepcopy(QUESTIONS)
            value['questions'] += [copy.deepcopy(value['questions'][0]) for _ in range(n-3)]
            r=checks.execute(server.connect,'generate',{'request_id':f'count{n}','topic':'节点法','count':n},lambda *a:(json.dumps(value),{}))
            self.assertEqual(len(self.get(r['id'])['questions']),n)
        for n in (2,6,True):
            with self.assertRaises(ValueError):self.generate(f'badcount{n}',topic='节点法',count=n)
        self.save();task=self.listing()[0]['tasks'][0]
        with self.assertRaisesRegex(ValueError,'范围已变化'):
            checks.execute(server.connect,'generate',{'request_id':'changed','task_id':task['id'],'scope_snapshot':{'title':'old'}},lambda *a:self.fail('must not call model'))

    def test_submit_claim_rechecks_state_under_transaction(self):
        i=self.generate()['id'];self.submit(i)
        body={'request_id':'raced','answers':{'1':0,'2':1,'3':'x'},'evaluate_short':True}
        with server.connect() as c:
            with self.assertRaisesRegex(ValueError,'未再次调用模型'):checks.claim(c,'submit',i,body)

    def test_http_permissions_flow_and_errors(self):
        self.save();task=self.listing()[0]['tasks'][0]
        with self.http() as (base,request):
            with self.assertRaises(urllib.error.HTTPError) as exc:urllib.request.urlopen(base+'/api/learning/checks')
            self.assertEqual(exc.exception.code,403)
            with self.assertRaises(urllib.error.HTTPError) as exc:request('/api/learning/checks',{},'POST',{'Origin':'https://evil.test'})
            self.assertEqual(exc.exception.code,403)
            with patch('server.learning_model',side_effect=self.model):r=request('/api/learning/checks',{'task_id':task['id'],'request_id':'http'},'POST')
            i=r['id'];self.assertEqual(len(request('/api/learning/checks')['checks']),1)
            request(f'/api/learning/checks/{i}/submit',{'request_id':'httpsub','answers':{'1':0,'2':1,'3':'列方程'},'evaluate_short':False},'POST')
            self.assertEqual(request(f'/api/learning/checks/{i}')['status'],'submitted')
            request(f'/api/learning/checks/{i}',{'request_id':'httpfix','question_id':'2','verdict':'uncertain','note':'待核'},'PATCH')
            request(f'/api/learning/checks/{i}',{'request_id':'httpdel'},'DELETE')
            self.assertEqual(request('/api/learning/checks')['checks'],[])
            with patch('learning_checks.listing',side_effect=sqlite3.OperationalError('private SQL')):
                with self.assertRaises(urllib.error.HTTPError) as exc:request('/api/learning/checks')
                self.assertEqual(exc.exception.code,500);self.assertNotIn('private SQL',exc.exception.read().decode())


if __name__=='__main__':unittest.main()
