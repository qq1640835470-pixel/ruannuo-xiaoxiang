"""Stage05 deterministic clock and isolated SQLite only; no credentials or models."""
import concurrent.futures
import contextlib
import copy
import datetime as dt
import json
import pathlib
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch
import agent_state
import learning
import learning_adjustments
import learning_reminders as reminders
from test_learning import PLAN

NOW=dt.datetime.fromisoformat('2026-10-20T10:00:00+08:00')

class ReminderTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.db=pathlib.Path(self.tmp.name)/'reminders.sqlite3';self.now=NOW
        with self.connect() as c:
            c.executescript('CREATE TABLE tasks(id TEXT PRIMARY KEY,title TEXT,details TEXT,scheduled_at TEXT,status TEXT,created_at TEXT);CREATE TABLE settings(key TEXT PRIMARY KEY,value TEXT);')
            agent_state.init(c);learning_adjustments.init(c);reminders.init(c)
        self.counter=0

    def tearDown(self):self.tmp.cleanup()

    @contextlib.contextmanager
    def connect(self):
        c=sqlite3.connect(self.db,timeout=10);c.row_factory=sqlite3.Row
        try:
            with c:yield c
        finally:c.close()

    def call(self,operation,body=None):
        with self.connect() as c:
            if operation=='check':return reminders.check(c,body or {},self.now)
            if operation=='view':return reminders.view(c,self.now)
            self.counter+=1;return reminders.write(c,operation,{'request_id':'r'+str(self.counter),**body},self.now)

    def enable(self,**kwargs):return self.call('settings',{'enabled':True,**kwargs})
    def check(self,current=None):return self.call('check',{'current_id':current} if current else {})['reminder']
    def action(self,action,delivery=None,**kwargs):return self.call('action',{'action':action,**({'reminder_id':delivery['id']} if delivery else {}),**kwargs})
    def plan(self):
        with self.connect() as c:return learning.save(c,{'request_id':'plan','plan':copy.deepcopy(PLAN)})
    def tasks(self):
        with self.connect() as c:return sorted(agent_state.read(c,'tasks'),key=lambda t:t['scheduled_at'])
    def update(self,ident,body):
        with self.connect() as c:return agent_state.mutate(c,'tasks','update',body,ident)
    def progress(self,ident,**body):
        with self.connect() as c:return agent_state.mutate(c,'task_progress','create',body,parent=ident)

    def test_default_off_no_tasks_and_due_pending(self):
        self.plan();self.assertFalse(self.call('view')['settings']['enabled']);self.assertIsNone(self.check())
        self.enable();delivery=self.check();self.assertEqual(len(delivery['tasks']),1);self.assertEqual(delivery['tasks'][0]['date'],'2026-10-20')
        self.assertEqual(self.check(delivery['id'])['id'],delivery['id']);self.assertIsNone(self.check())
        self.assertIsNone(self.call('view')['summary']['actual_minutes'])

    def test_empty_and_finished_cancelled_goals(self):
        self.enable();self.assertIsNone(self.check());self.plan()
        first,second=self.tasks();self.update(first['id'],{'status':'done'});self.update(second['id'],{'status':'cancelled'})
        self.assertIsNone(self.check());summary=self.call('view')['summary'];self.assertEqual(summary['completed'],1);self.assertEqual(summary['remaining'],0)
        with self.assertRaisesRegex(ValueError,'已完成或已取消'):self.update(first['id'],{'status':'pending'})
        with self.connect() as c:
            agent_state.mutate(c,'tasks','create',{k:first[k] for k in ('title','details','scheduled_at','goal_id')})
        with self.connect() as c:agent_state.mutate(c,'goals','update',{'status':'cancelled'},first['goal_id'])
        self.assertIsNone(self.check())

    def test_active_deferred_overdue_aggregate(self):
        self.plan();self.enable();a,b=self.tasks();self.update(a['id'],{'status':'active'});self.update(b['id'],{'status':'deferred','scheduled_at':'2026-10-19'})
        delivery=self.check();self.assertEqual(len(delivery['tasks']),2);self.assertEqual(delivery['tasks'][0]['status'],'active')
        summary=self.call('view')['summary'];self.assertEqual(summary['overdue'],1);self.assertEqual(summary['deferred'],1)

    def test_snooze_15_and_60_exact_time_and_cap(self):
        self.plan();self.enable(daily_limit=3);first=self.check();self.action('snooze',first,minutes=15)
        self.now+=dt.timedelta(minutes=14,seconds=59);self.assertIsNone(self.check());self.now+=dt.timedelta(seconds=1)
        second=self.check();self.assertIsNotNone(second);self.action('snooze',second,minutes=60)
        self.now+=dt.timedelta(minutes=59);self.assertIsNone(self.check());self.now+=dt.timedelta(minutes=1)
        third=self.check();self.action('snooze',third,minutes=15);self.now+=dt.timedelta(minutes=15);self.assertIsNone(self.check())
        self.assertEqual(self.tasks()[0]['status'],'pending')

    def test_pause_survives_reinitialization_and_next_day(self):
        self.plan();self.enable();first=self.check();self.action('pause')
        with self.connect() as c:reminders.init(c)
        self.assertIsNone(self.check(first['id']));self.now+=dt.timedelta(days=1);self.assertIsNotNone(self.check())

    def test_dismiss_restart_and_no_immediate_repopup(self):
        self.plan();self.enable();first=self.check();self.action('dismiss',first)
        self.now+=dt.timedelta(hours=3)
        with self.connect() as c:reminders.init(c)
        self.assertIsNone(self.check())
        code='import sqlite3,sys,datetime as dt,learning_reminders as r;c=sqlite3.connect(sys.argv[1]);c.row_factory=sqlite3.Row;print(r.check(c,{},dt.datetime.fromisoformat(sys.argv[2]))["reminder"])'
        out=subprocess.run([sys.executable,'-c',code,str(self.db),self.now.isoformat()],capture_output=True,text=True,check=True)
        self.assertEqual(out.stdout.strip(),'None')

    def test_quiet_cross_midnight_boundaries(self):
        self.plan();self.enable(window_start='00:00',window_end='23:59')
        for hour,minute in [(23,0),(0,1),(7,59)]:
            self.now=NOW.replace(hour=hour,minute=minute);self.assertIsNone(self.check())
        self.now=NOW.replace(hour=8,minute=0);self.assertIsNotNone(self.check())

    def test_daytime_quiet_and_cross_midnight_window(self):
        self.plan();self.enable(window_start='20:00',window_end='10:00',quiet_start='12:00',quiet_end='14:00')
        for hour in (10,12,14,19):self.now=NOW.replace(hour=hour);self.assertIsNone(self.check())
        self.now=NOW.replace(hour=20);self.assertIsNotNone(self.check())

    def test_sleep_coalesces_snoozes_and_clock_backward_guard(self):
        self.plan();self.enable();first=self.check();self.action('snooze',first,minutes=15)
        self.now=NOW.replace(hour=19);second=self.check();self.assertIsNotNone(second);self.assertIsNone(self.check())
        self.action('dismiss',second);self.now=NOW.replace(hour=11);self.assertIsNone(self.check())
        self.now=NOW+dt.timedelta(days=3);self.assertIsNotNone(self.check());self.assertIsNone(self.check())

    def test_snooze_waits_for_quiet_end_without_queue(self):
        self.plan();self.enable(window_start='00:00',window_end='23:59');self.now=NOW.replace(hour=21,minute=50)
        first=self.check();self.action('snooze',first,minutes=15);self.now=NOW.replace(hour=22,minute=30);self.assertIsNone(self.check())
        self.now=(NOW+dt.timedelta(days=1)).replace(hour=8);delivery=self.check();self.assertEqual(len(delivery['tasks']),2);self.assertIsNone(self.check())

    def test_edited_deleted_and_done_tasks_reject_start(self):
        self.plan();self.enable();delivery=self.check();ident=delivery['tasks'][0]['id']
        self.update(ident,{'title':'new'})
        with self.assertRaises(ValueError):self.action('start',delivery,task_id=ident)
        self.assertIsNone(self.check(delivery['id']))
        self.update(ident,{'status':'done'})
        with self.assertRaises(ValueError):self.action('start',delivery,task_id=ident)
        with self.connect() as c:agent_state.mutate(c,'tasks','delete',{},ident)
        with self.assertRaises(ValueError):self.action('start',delivery,task_id=ident)

    def test_start_true_receipt_retry_conflict_and_rollback(self):
        self.plan();self.enable();delivery=self.check();ident=delivery['tasks'][0]['id']
        body={'action':'start','reminder_id':delivery['id'],'task_id':ident,'request_id':'start1'}
        with self.connect() as c:c.execute("CREATE TRIGGER fail_start BEFORE UPDATE ON tasks BEGIN SELECT RAISE(ABORT,'failure'); END")
        with self.assertRaises(sqlite3.DatabaseError):self.call('action',body)
        self.assertEqual(self.tasks()[0]['status'],'pending')
        with self.connect() as c:
            self.assertEqual(c.execute('SELECT state FROM learning_reminders').fetchone()[0],'open');c.execute('DROP TRIGGER fail_start')
        result=self.call('action',body);self.assertEqual(result['status'],'active');self.assertEqual(self.call('action',body),result)
        self.assertEqual(self.tasks()[0]['status'],'active');self.assertIn('learning_reminder:start1',self.tasks()[0]['updated_source_id'])
        with self.assertRaises(ValueError):self.call('action',{**body,'action':'dismiss'})

    def test_summary_minutes_dates_unknown_and_correction(self):
        self.plan();a,b=self.tasks();self.update(a['id'],{'status':'done'});self.update(b['id'],{'status':'deferred'})
        self.assertIsNone(self.call('view')['summary']['actual_minutes'])
        p=self.progress(a['id'],minutes=20,note='PRIVATE_NOTE',recorded_at='2026-10-19T17:00:00+00:00')
        self.progress(b['id'],minutes=99,recorded_at='2026-10-19T00:00:00+08:00')
        self.progress(a['id'],note='unknown minutes',recorded_at=NOW.isoformat())
        with self.connect() as c:agent_state.mutate(c,'task_progress','update',{'minutes':15},p['id'])
        summary=self.call('view')['summary'];self.assertEqual(summary['actual_minutes'],15);self.assertEqual(summary['unfilled_records'],1);self.assertEqual(summary['completed'],1)
        self.assertNotIn('PRIVATE_NOTE',json.dumps(self.call('view')))

    def test_minimal_schema_validation_and_no_model_calls(self):
        self.plan()
        with self.connect() as c:
            before=c.execute('SELECT count(*) FROM tasks').fetchone()[0];reminders.init(c);reminders.init(c)
            self.assertEqual(c.execute('SELECT count(*) FROM tasks').fetchone()[0],before)
        for body in ({'enabled':1},{'daily_limit':True},{'daily_limit':9},{'quiet_start':'24:00'},{'window_start':'09:00','window_end':'09:00'},{'paused_on':'2026-10-20'}):
            with self.assertRaises(ValueError):self.call('settings',body)
        with patch('providers.chat',side_effect=AssertionError('No model')),patch('providers.hub.load_keys',side_effect=AssertionError('No real keys')):
            self.enable();delivery=self.check();self.action('dismiss',delivery);self.call('view')

    def test_parallel_connections_claim_only_one_delivery(self):
        self.plan();self.enable()
        def claim(_):
            with self.connect() as c:return reminders.check(c,{},NOW)['reminder']
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:items=list(pool.map(claim,range(4)))
        self.assertEqual(sum(i is not None for i in items),1)

    def test_content_edit_with_same_timestamp_still_invalidates_button(self):
        self.plan();self.enable();delivery=self.check();ident=delivery['tasks'][0]['id']
        with self.connect() as c:c.execute("UPDATE tasks SET title='same clock edit' WHERE id=?",(ident,))
        with self.assertRaises(ValueError):self.action('start',delivery,task_id=ident)
        self.assertEqual(self.tasks()[0]['status'],'pending')

    def test_reader_cannot_access_private_notes_questions_or_chat(self):
        self.plan();self.enable();self.progress(self.tasks()[0]['id'],note='PRIVATE',minutes=0,recorded_at=NOW.isoformat())
        with self.connect() as c:
            def allow(action,table,column,*args):
                if action==sqlite3.SQLITE_READ and (table in ('messages','learning_checks') or table=='task_progress' and column in ('note','percent')):return sqlite3.SQLITE_DENY
                return sqlite3.SQLITE_OK
            c.set_authorizer(allow)
            value=reminders.check(c,{},NOW)
            self.assertIsNotNone(value['reminder']);self.assertEqual(value['summary']['actual_minutes'],0)

    def test_new_task_after_dismiss_waits_for_minimum_gap(self):
        self.plan();self.enable();delivery=self.check();self.action('dismiss',delivery)
        second=self.tasks()[1];self.update(second['id'],{'scheduled_at':'2026-10-20'})
        self.now+=dt.timedelta(minutes=29);self.assertIsNone(self.check())
        self.now+=dt.timedelta(minutes=1);next_delivery=self.check()
        self.assertEqual([t['id'] for t in next_delivery['tasks']],[second['id']])

    def test_http_security_error_receipt_and_summary(self):
        from test_learning_system_034 import Fixture
        with tempfile.TemporaryDirectory() as folder,Fixture(folder) as fixture,patch('learning_reminders.local_now',return_value=NOW):
            r=fixture.request
            r('/api/learning/confirm',{'plan':PLAN,'request_id':'http-plan'},'POST')
            r('/api/learning/reminders/settings',{'request_id':'setting','enabled':True},'PATCH')
            delivery=r('/api/learning/reminders/check',{},'POST')['reminder'];self.assertIsNotNone(delivery)
            with patch('learning_reminders.check',side_effect=sqlite3.OperationalError('PRIVATE_DB_ERROR')):
                with self.assertRaises(urllib.error.HTTPError) as exc:r('/api/learning/reminders/check',{},'POST')
                self.assertEqual(exc.exception.code,500);self.assertNotIn('PRIVATE_DB_ERROR',exc.exception.read().decode())
            with self.assertRaises(urllib.error.HTTPError) as exc:urllib.request.urlopen(fixture.base+'/api/learning/reminders')
            self.assertEqual(exc.exception.code,403)
            body={'request_id':'http-start','action':'start','task_id':delivery['tasks'][0]['id'],'reminder_id':delivery['id']}
            result=r('/api/learning/reminders/action',body,'POST');self.assertEqual(result,r('/api/learning/reminders/action',body,'POST'))
            self.assertEqual(r('/api/tasks/'+result['task_id'])['status'],'active');self.assertEqual(r('/api/learning/reminders')['summary']['planned'],1)


if __name__=='__main__':unittest.main()
