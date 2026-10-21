"""Temporary SQLite and synthetic models; no private runtime or paid API."""
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
import learning_adjustments as adjust
import learning_checks
import server
import test_learning as fixtures
from test_learning_checks import QUESTIONS

MODEL={'provider':'openrouter','model':'fixture/model'}
TODAY='2026-10-20'


class AdjustmentTests(unittest.TestCase):
    setUp=fixtures.LearningTests.setUp
    tearDown=fixtures.LearningTests.tearDown
    save=fixtures.LearningTests.save
    listing=fixtures.LearningTests.listing
    count=fixtures.LearningTests.count
    http=fixtures.LearningTests.http

    def setup_plan(self):
        if not self.listing():self.save()
        return self.listing()[0]

    def selection(self,**kw):
        s=self.setup_plan()
        return {'goal_id':s['goal']['id'],'revision':s['revision'],'include_plan':True,'include_remaining':False,'progress_ids':[],'check_ids':[],'note':'请适当增加节点法练习',**kw}

    def change(self, selection=None):
        selected=selection or self.selection()
        with server.connect() as c:original,_=adjust.evidence(c,selected,TODAY)
        t=next(t for t in original['tasks'] if t['status'] not in ('done','cancelled'))
        task={k:t[k] for k in adjust.TASK_FIELDS};task['minutes']+=5
        return {'action':'update','task_id':t['id'],'task':task,'reason':'根据原安排适当增加练习时间，非掌握判断','evidence':['plan:'+t['id']]}

    def generate(self, request='adjust1', selection=None, changes=None, call=None):
        selection=selection or self.selection()
        with server.connect() as c:view=adjust.preview(c,selection,TODAY,MODEL)
        value={'summary':'适当增加练习，不推断掌握程度','changes':changes if changes is not None else [self.change(selection)]}
        model=call or (lambda *a:(json.dumps(value,ensure_ascii=False),{'provider':'fixture','returned_model':'synthetic'}))
        body={'request_id':request,'selection':selection,'preview_hash':view['preview_hash'],'model':MODEL,'confirmed':True}
        return adjust.generate(server.connect,body,TODAY,MODEL,model)

    def confirm(self, draft, request='save-adjust1', changes=None):
        with server.connect() as c:return adjust.confirm(c,{'request_id':request,'adjustment_id':draft['id'],'changes':changes if changes is not None else draft['proposal']['changes']})

    def check(self,task_id,request='check'):
        r=learning_checks.execute(server.connect,'generate',{'request_id':request,'task_id':task_id},lambda *a:(json.dumps(QUESTIONS),{}))
        learning_checks.execute(server.connect,'submit',{'request_id':request+'sub','answers':{'1':0,'2':1,'3':'列式'},'evaluate_short':False},check_id=r['id'])
        return r['id']

    def test_options_do_not_read_unselected_bodies_and_empty_selection(self):
        selection=self.selection();task=self.setup_plan()['tasks'][0]
        p=server.state_write('task_progress','create',{'note':'PRIVATE_UNSELECTED','minutes':40},parent=task['id'])
        self.check(task['id'])
        with server.connect() as c:
            with patch('agent_state.get',wraps=agent_state.get) as get,patch('learning_checks.get',side_effect=AssertionError('No unselected checks')):
                options=adjust.options(c,selection['goal_id']);view=adjust.preview(c,selection,TODAY,MODEL)
                self.assertNotIn('task_progress',[call.args[1] for call in get.call_args_list])
        self.assertEqual(options['progress'][0]['id'],p['id']);self.assertNotIn('note',options['progress'][0])
        self.assertEqual(view['payload']['progress'],[]);self.assertEqual(view['payload']['checks'],[])
        self.assertNotIn('PRIVATE_UNSELECTED',json.dumps(view));self.assertEqual(self.count('learning_adjustments'),0)

    def test_only_selected_progress_and_corrected_check_sent(self):
        s=self.setup_plan();t=s['tasks'][0]
        yes=server.state_write('task_progress','create',{'note':'SELECTED_NOTE','minutes':25},parent=t['id'])
        server.state_write('task_progress','create',{'note':'UNSELECTED_NOTE','minutes':55},parent=t['id'])
        i=self.check(t['id']);other=self.check(t['id'],'other')
        learning_checks.execute(server.connect,'correct',{'request_id':'correct','question_id':'2','verdict':'uncertain','note':'人工更正'},check_id=i)
        selected=self.selection(progress_ids=[yes['id']],check_ids=[i]);seen=[]
        def call(content,*a):seen.append(content);return json.dumps({'summary':'建议核对','changes':[self.change(selected)]}),{}
        self.generate(selection=selected,call=call)
        body=json.loads(seen[0]);self.assertEqual([p['id'] for p in body['progress']],[yes['id']]);self.assertEqual([r['id'] for r in body['checks']],[i])
        self.assertIn('人工更正',seen[0]);self.assertNotIn('UNSELECTED_NOTE',seen[0]);self.assertNotIn(other,seen[0])
        self.assertIn('用户自报',body['evidence_types']['progress'])

    def test_cross_course_missing_duplicate_and_over_twenty_rejected(self):
        s=self.setup_plan();other=self.save(request='other-plan');other_saved=next(p for p in self.listing() if p['goal']['id']==other['goal_id']);t=other_saved['tasks'][0]
        p=server.state_write('task_progress','create',{'note':'OTHER_COURSE'},parent=t['id']);i=self.check(t['id'])
        for kw in ({'progress_ids':[p['id']]},{'check_ids':[i]},{'check_ids':['missing']},{'check_ids':['x']*21},{'progress_ids':['x','x']},{'include_plan':False}):
            selection={'goal_id':s['goal']['id'],'revision':s['revision'],'include_plan':True,'include_remaining':False,'progress_ids':[],'check_ids':[],'note':'',**kw}
            with server.connect() as c:
                with self.assertRaises(ValueError):adjust.preview(c,selection,TODAY,MODEL)

    def test_cancel_and_model_failure_do_not_change_plan(self):
        self.setup_plan();before=self.listing();draft=self.generate()
        self.assertEqual(self.listing(),before)
        with server.connect() as c:adjust.cancel(c,draft['id'])
        self.assertEqual(self.listing(),before)
        with self.assertRaises(ValueError):self.confirm(draft)
        for request,call in [('broken',lambda *a:('not json',{})),('budget',lambda *a:(_ for _ in ()).throw(ValueError('预算不足')))]:
            with self.assertRaisesRegex(ValueError,'正式计划未改变'):self.generate(request,call=call)
            self.assertEqual(self.listing(),before)

    def test_confirm_original_goal_ids_completed_progress_checks_unchanged(self):
        s=self.setup_plan();done=s['tasks'][0]
        server.state_write('tasks','update',{'status':'done','scheduled_at':'2026-10-20T09:00:00'},done['id'])
        progress=server.state_write('task_progress','create',{'minutes':20,'note':'已有历史'},parent=done['id']);check=self.check(done['id'])
        learning_checks.execute(server.connect,'correct',{'request_id':'keep-correction','question_id':'1','verdict':'uncertain','note':'保留原有人工更正'},check_id=check)
        with server.connect() as c:
            frozen=agent_state.get(c,'tasks',done['id']);check_before=learning_checks.get(c,check)
        original_ids={t['id'] for t in self.setup_plan()['tasks']};draft=self.generate();r=self.confirm(draft)
        s=self.setup_plan();self.assertEqual(r['goal_id'],s['goal']['id']);self.assertEqual(self.count('goals'),1);self.assertEqual({t['id'] for t in s['tasks']},original_ids)
        with server.connect() as c:
            self.assertEqual(agent_state.get(c,'tasks',done['id']),frozen);self.assertEqual(agent_state.get(c,'task_progress',progress['id']),progress);self.assertEqual(learning_checks.get(c,check),check_before)
        self.assertIn('已实际保存',r['summary'])

    def test_add_cancel_rest_days_preserve_history_and_normal_constraints(self):
        selection=self.selection();s=self.setup_plan();old=next(t for t in s['tasks'] if t['scheduled_at']=='2026-10-20')
        # Moving remaining work off a day is valid only for an existing plan.
        update=self.change(selection);update['task_id']=old['id'];update['task']={k:next(t for t in adjust.original_plan(s)['tasks'] if t['id']==old['id'])[k] for k in adjust.TASK_FIELDS};update['task']['date']='2026-10-21'
        draft=self.generate(changes=[update]);self.confirm(draft)
        s=self.setup_plan();self.assertEqual(len({t['scheduled_at'][:10] for t in s['tasks']}),1)
        with self.assertRaises(ValueError):learning.plan({**copy.deepcopy(fixtures.PLAN),'tasks':[{**t,'date':'2026-10-21'} for t in fixtures.PLAN['tasks']]})
        selected=self.selection();t=next(t for t in s['tasks'] if t['id']==old['id'])
        added={k:adjust.original_plan(s)['tasks'][0][k] for k in adjust.TASK_FIELDS};added.update(title='补充复习',kind=t['learning']['kind'],minutes=10)
        changes=[{'action':'cancel','task_id':t['id'],'task':None,'reason':'合并复习','evidence':['plan:'+t['id']]},
                 {'action':'add','task_id':'','task':added,'reason':'针对原知识点复习','evidence':['plan:'+t['id']]}]
        draft=self.generate('second',selected,changes);self.confirm(draft,'save-second')
        after=self.setup_plan();self.assertEqual(self.count('goals'),1);self.assertEqual(len(after['tasks']),3);self.assertEqual(next(t for t in after['tasks'] if t['id']==old['id'])['status'],'cancelled')

    def test_reject_completed_modification_foreign_id_invalid_budget_fields_dates(self):
        selection=self.selection();good=self.change(selection)
        invalid=[]
        for key,value in [('date','2026-10-19'),('date','2026-11-25'),('minutes',999),('minutes',True),('content','x'*501),('kind','unknown')]:
            row=copy.deepcopy(good);row['task'][key]=value;invalid.append([row])
        row=copy.deepcopy(good);row['task_id']='foreign';invalid.append([row])
        row=copy.deepcopy(good);row['evidence']=['check:unselected'];invalid.append([row])
        invalid += [[],[good]*13,[good,good]]
        for n,changes in enumerate(invalid):
            with self.assertRaises(ValueError):self.generate('bad'+str(n),selection,changes)
        server.state_write('tasks','update',{'status':'done'},good['task_id']);selection=self.selection()
        with self.assertRaises(ValueError):self.generate('done',selection,[good])
        self.assertEqual(self.count('goals'),1)

    def test_stale_plan_selected_progress_and_selected_correction_block_save(self):
        draft=self.generate();task=self.setup_plan()['tasks'][0]
        server.state_write('tasks','update',{'status':'active'},task['id'])
        with self.assertRaisesRegex(ValueError,'计划已变化'):self.confirm(draft)
        p=server.state_write('task_progress','create',{'note':'选中记录'},parent=task['id'])
        draft=self.generate('next',self.selection(progress_ids=[p['id']]))
        server.state_write('task_progress','update',{'note':'用户更正'},p['id'])
        with self.assertRaisesRegex(ValueError,'所选记录'):self.confirm(draft,'next-save')
        i=self.check(task['id']);draft=self.generate('check-draft',self.selection(check_ids=[i]))
        learning_checks.execute(server.connect,'correct',{'request_id':'fix-feedback','question_id':'1','verdict':'uncertain','note':'待核'},check_id=i)
        with self.assertRaisesRegex(ValueError,'所选记录'):self.confirm(draft,'check-save')

    def test_save_trigger_failure_rolls_back_plan_and_adjustment_and_receipt(self):
        change=self.change();added=copy.deepcopy(change);added.update(action='add',task_id='');added['task']['title']='需要回滚的新增练习';added['task']['minutes']=10
        draft=self.generate(changes=[change,added]);before=self.listing()
        with server.connect() as c:c.execute("CREATE TRIGGER fail_adjust BEFORE UPDATE ON learning_adjustments WHEN NEW.state='confirmed' BEGIN SELECT RAISE(ABORT,'private SQL error'); END")
        with self.assertRaises(sqlite3.DatabaseError):self.confirm(draft)
        self.assertEqual(before,self.listing())
        with server.connect() as c:
            self.assertEqual(adjust.get(c,draft['id'])['state'],'draft');self.assertIsNone(c.execute("SELECT 1 FROM agent_state_requests WHERE id='save-adjust1'").fetchone());c.execute('DROP TRIGGER fail_adjust')
        self.confirm(draft)

    def test_save_retry_concurrent_and_restart_no_duplicate_new_tasks(self):
        selection=self.selection();base=self.change(selection);added=copy.deepcopy(base);added.update(action='add',task_id='');added['task']['title']='新增复习';added['task']['minutes']=10
        draft=self.generate(changes=[added])
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:responses=list(pool.map(lambda _:self.confirm(draft),range(3)))
        self.assertTrue(all(r==responses[0] for r in responses));self.assertEqual(self.count('tasks'),3);server.init();self.assertEqual(self.confirm(draft),responses[0]);self.assertEqual(self.count('tasks'),3)
        with server.connect() as c:c.execute("CREATE TRIGGER no_repeat_adjust BEFORE UPDATE ON learning_adjustments BEGIN SELECT RAISE(ABORT,'No repeated adjustment writes'); END")
        self.assertEqual(self.confirm(draft),responses[0])
        changed=copy.deepcopy(draft['proposal']['changes']);changed[0]['task']['minutes']=11
        with self.assertRaises(ValueError):self.confirm(draft,changes=changed)
        changed=copy.deepcopy(draft['proposal']['changes']);changed[0]['reason']='同样计划但篡改原因'
        with self.assertRaises(ValueError):self.confirm(draft,changes=changed)
        code='import sqlite3,sys,learning_adjustments;c=sqlite3.connect(sys.argv[1]);c.row_factory=sqlite3.Row;print(len(learning_adjustments.confirmed(c,sys.argv[2])))'
        out=subprocess.run([sys.executable,'-c',code,str(server.DB),selection['goal_id']],capture_output=True,text=True,check=True)
        self.assertEqual(out.stdout.strip(),'1')

    def test_generation_dedup_preview_change_and_consent_guard(self):
        selection=self.selection()
        with server.connect() as c:view=adjust.preview(c,selection,TODAY,MODEL)
        body={'request_id':'repeat','selection':selection,'preview_hash':view['preview_hash'],'model':MODEL,'confirmed':True}
        calls=[]
        def call(*a):calls.append(1);return json.dumps({'summary':'调整','changes':[self.change(selection)]}),{}
        first=adjust.generate(server.connect,body,TODAY,MODEL,call);second=adjust.generate(server.connect,body,TODAY,MODEL,call)
        self.assertEqual(first,second);self.assertEqual(len(calls),1)
        for change in ({'confirmed':False},{'preview_hash':'wrong'},{'model':{'provider':'different','model':'other'}}):
            with self.assertRaises(ValueError):adjust.generate(server.connect,{**body,'request_id':str(len(change))+next(iter(change)),**change},TODAY,MODEL,lambda *a:self.fail('not authorized'))

    def test_generation_pending_after_restart_no_paid_retry(self):
        selection=self.selection();started,release=threading.Event(),threading.Event();calls=[]
        with server.connect() as c:view=adjust.preview(c,selection,TODAY,MODEL)
        body={'request_id':'inflight','selection':selection,'preview_hash':view['preview_hash'],'model':MODEL,'confirmed':True}
        def call(*a):calls.append(1);started.set();release.wait(5);return json.dumps({'summary':'调整','changes':[self.change(selection)]}),{}
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            first=pool.submit(adjust.generate,server.connect,body,TODAY,MODEL,call);self.assertTrue(started.wait(5))
            with self.assertRaises(ValueError):adjust.generate(server.connect,body,TODAY,MODEL,call)
            release.set();first.result()
        self.assertEqual(len(calls),1)
        with server.connect() as c:c.execute("UPDATE learning_adjustments SET state='generating' WHERE id='inflight'")
        server.init()
        with self.assertRaises(ValueError):adjust.generate(server.connect,body,TODAY,MODEL,lambda *a:self.fail('restart retry'))

    def test_model_selection_changed_blocks_before_budget_or_network(self):
        with patch('server.settings',return_value={'provider':'openrouter','chat_models':{'openrouter':'other/model'},'api_generation_enabled':True}),patch('server.reserve',side_effect=AssertionError('must not reserve')):
            with self.assertRaisesRegex(ValueError,'模型选择已变化'):server.learning_model('{}','JSON',8192,expected_selection=MODEL)

    def test_selected_record_changes_after_preview_rejected_before_model(self):
        s=self.setup_plan();p=server.state_write('task_progress','create',{'note':'选中依据'},parent=s['tasks'][0]['id']);selection=self.selection(progress_ids=[p['id']])
        with server.connect() as c:view=adjust.preview(c,selection,TODAY,MODEL)
        server.state_write('task_progress','update',{'note':'更正依据'},p['id'])
        body={'request_id':'stale-preview','selection':selection,'preview_hash':view['preview_hash'],'model':MODEL,'confirmed':True}
        with self.assertRaisesRegex(ValueError,'依据或模型已变化'):adjust.generate(server.connect,body,TODAY,MODEL,lambda *a:self.fail('must not send'))
        self.assertEqual(self.count('learning_adjustments'),0)

    def test_unselected_progress_changes_do_not_block_or_enter_confirm(self):
        s=self.setup_plan();p=server.state_write('task_progress','create',{'note':'不选此条'},parent=s['tasks'][0]['id']);draft=self.generate()
        server.state_write('task_progress','update',{'note':'无关记录更正'},p['id'])
        with patch('agent_state.get',wraps=agent_state.get) as get:
            self.confirm(draft)
            self.assertNotIn('task_progress',[call.args[1] for call in get.call_args_list])

    def test_additive_migration_preserves_existing_state_and_check_corrections(self):
        s=self.setup_plan();p=server.state_write('task_progress','create',{'note':'迁移前','minutes':22},parent=s['tasks'][0]['id']);i=self.check(s['tasks'][0]['id'])
        with server.connect() as c:
            before=learning.listing(c);check=learning_checks.get(c,i);c.execute('DROP TABLE learning_adjustments')
        server.init();server.init()
        with server.connect() as c:
            self.assertEqual(learning.listing(c),before);self.assertEqual(learning_checks.get(c,i),check);self.assertEqual(agent_state.get(c,'task_progress',p['id']),p)
        self.assertEqual(self.count('learning_adjustments'),0)

    def test_real_reservation_budget_guard_does_not_call_model(self):
        selected={'provider':'openrouter','chat_models':{'openrouter':MODEL['model']},'api_generation_enabled':True}
        with patch('server.settings',return_value=selected),patch('server.budget',return_value={'remaining_cny':0}),patch('providers.reservation',return_value=.1),patch('providers.chat',side_effect=AssertionError('No paid request')) as model:
            with self.assertRaisesRegex(ValueError,'预算剩余不足'):server.learning_model('{}','JSON',8192,expected_selection=server.learning_selection(selected))
            model.assert_not_called()

    def test_future_reminder_reader_no_notes_or_checks_and_confirmed_only(self):
        draft=self.generate()
        with server.connect() as c:
            view=adjust.reminder_view(c,draft['goal_id'],TODAY);self.assertEqual(view['confirmed_adjustments'],[]);self.assertTrue(view['today_and_overdue']);self.assertTrue(view['future']);self.assertNotIn('progress',view)
        self.confirm(draft)
        with server.connect() as c:self.assertEqual(len(adjust.reminder_view(c,draft['goal_id'],TODAY)['confirmed_adjustments']),1)

    def test_http_auth_generate_confirm_cancel_and_sanitized_failure(self):
        selection=self.selection()
        with self.http() as (base,request),patch('server.learning_selection',return_value=MODEL),patch('server.now',return_value=TODAY+'T10:00:00+08:00'):
            path='/api/learning/adjustments'
            with self.assertRaises(urllib.error.HTTPError) as exc:urllib.request.urlopen(base+path+'/options?goal_id='+selection['goal_id'])
            self.assertEqual(exc.exception.code,403)
            with self.assertRaises(urllib.error.HTTPError) as exc:request(path+'/preview',{'selection':selection},'POST',{'Origin':'https://evil.test'})
            self.assertEqual(exc.exception.code,403)
            options=request(path+'/options?goal_id='+selection['goal_id']);self.assertEqual(options['goal_id'],selection['goal_id'])
            view=request(path+'/preview',{'selection':selection},'POST')
            value={'summary':'调整','changes':[self.change(selection)]}
            with patch('server.learning_model',return_value=(json.dumps(value),{'provider':'fixture'})) as call:
                draft=request(path+'/generate',{'request_id':'httpgen','selection':selection,'preview_hash':view['preview_hash'],'model':MODEL,'confirmed':True},'POST')
                self.assertEqual(call.call_args.kwargs['expected_selection'],MODEL)
            body={'request_id':'httpsave','adjustment_id':draft['id'],'changes':draft['proposal']['changes']}
            first=request(path+'/confirm',body,'POST');self.assertEqual(first,request(path+'/confirm',body,'POST'));self.assertIn('已实际保存',first['summary'])
            self.assertEqual(len(request(path+'?goal_id='+selection['goal_id'])['adjustments']),1)
            with patch('learning_adjustments.confirm',side_effect=sqlite3.OperationalError('private SQL')):
                with self.assertRaises(urllib.error.HTTPError) as exc:request(path+'/confirm',body,'POST')
                self.assertEqual(exc.exception.code,500);self.assertNotIn('private SQL',exc.exception.read().decode())


if __name__=='__main__':unittest.main()
