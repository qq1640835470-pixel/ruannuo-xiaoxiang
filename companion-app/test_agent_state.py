"""Offline state acceptance, isolated SQLite only; no live model or user data."""
import concurrent.futures
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

import agent_state
import server


class AgentStateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = server.DATA, server.DB, server.MONITOR
        server.DATA = pathlib.Path(self.tmp.name)
        server.DB = server.DATA / 'state.sqlite3'
        server.MONITOR = None
        self.no_cloud = patch('providers.chat', side_effect=AssertionError('No paid API'))
        self.no_cloud.start()
        self.no_local = patch('local_runtime.chat', side_effect=AssertionError('No real model'))
        self.no_local.start()
        server.init()

    def tearDown(self):
        if server.MONITOR:
            server.MONITOR.close()
        server.DATA, server.DB, server.MONITOR = self.old
        self.no_local.stop()
        self.no_cloud.stop()
        self.tmp.cleanup()

    def write(self, table, action, body, ident=None, parent=None):
        return server.state_write(table, action, body, ident, parent)

    def read(self, table, ident=None, parent=None):
        with server.connect() as c:
            return agent_state.read(c, table, ident, parent)

    def test_goal_task_progress_restart_and_separate_process(self):
        goal = self.write('goals', 'create', {'title': '完成课程', 'deadline': '2026-12-31T23:59:00+08:00'})
        task = server.add_task({'title': '第一章', 'goal_id': goal['id']})
        for status in agent_state.STATUSES:
            result = server.task_update(task['id'], {'status': status})
            self.assertEqual(result['task']['status'], status)
        progress = self.write('task_progress', 'create', {'note': '完成例题', 'percent': 35, 'minutes': 25}, parent=task['id'])
        server.init()
        self.assertEqual(self.read('goals', goal['id'])['task_ids'], [task['id']])
        self.assertEqual(self.read('tasks', parent=goal['id'])[0]['status'], 'cancelled')
        self.assertEqual(self.read('task_progress', parent=task['id']), [progress])
        code = 'import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); print(c.execute("SELECT count(*) FROM goals").fetchone()[0],c.execute("SELECT minutes FROM task_progress").fetchone()[0])'
        result = subprocess.run([sys.executable, '-c', code, str(server.DB)], capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout.strip(), '1 25')

    def test_legacy_migration_idempotent_and_old_task_edit(self):
        legacy = server.DATA / 'legacy.sqlite3'
        with contextlib.closing(sqlite3.connect(legacy)) as c, c:
            c.row_factory = sqlite3.Row
            c.execute('CREATE TABLE tasks(id TEXT PRIMARY KEY,title TEXT,details TEXT,scheduled_at TEXT,status TEXT,created_at TEXT)')
            c.execute("INSERT INTO tasks VALUES('old','旧任务','原备注','','paused','2026-01-01')")
            agent_state.init(c)
            c.commit()
            agent_state.init(c)
            c.commit()
            row = agent_state.read(c, 'tasks', 'old')
            self.assertEqual([row[k] for k in ('title', 'details', 'status', 'created_at')], ['旧任务', '原备注', 'paused', '2026-01-01'])
            self.assertEqual(row['source_id'], 'legacy')
            self.assertEqual(row['updated_at'], row['created_at'])
            updated = agent_state.mutate(c, 'tasks', 'update', {'status': 'done'}, 'old')
            self.assertEqual(updated['status'], 'done')
        task = server.add_task({'title': '旧接口'})
        self.assertTrue(server.task_update(task['id'], {'details': '仍可编辑'})['ok'])

    def test_correction_and_delete_with_provenance(self):
        goal = self.write('goals', 'create', {'title': '错误目标', 'request_id': 'g1'})
        corrected = self.write('goals', 'update', {'title': '正确目标', 'request_id': 'g2'}, goal['id'])
        self.assertEqual(corrected['source_id'], 'local_api:g1')
        self.assertEqual(corrected['updated_source_id'], 'local_api:g2')
        self.assertGreaterEqual(corrected['updated_at'], corrected['created_at'])
        task = server.add_task({'title': '任务', 'goal_id': goal['id']})
        progress = self.write('task_progress', 'create', {'note': '错误备注', 'minutes': 100, 'request_id': 'p1'}, parent=task['id'])
        corrected = self.write('task_progress', 'update', {'note': '更正', 'minutes': 10}, progress['id'])
        self.assertEqual(corrected['minutes'], 10)
        self.write('task_progress', 'delete', {}, progress['id'])
        self.assertEqual(self.read('task_progress', parent=task['id']), [])
        self.write('goals', 'delete', {}, goal['id'])
        self.assertEqual(self.read('tasks', task['id'])['goal_id'], '')
        with server.connect() as c:
            receipts = str([tuple(r) for r in c.execute('SELECT response FROM agent_state_requests')])
        self.assertNotIn('错误', receipts)
        self.assertNotIn('正确目标', receipts)

    def test_receipts_conflicts_retry_and_no_resurrection(self):
        body = {'title': '幂等', 'request_id': 'same'}
        first = server.add_task(body)
        self.assertEqual(first, server.add_task(body))
        self.assertEqual(len(server.list_tasks()), 1)
        with self.assertRaises(ValueError):
            server.add_task({**body, 'title': '冲突'})
        self.write('tasks', 'update', {'status': 'active', 'request_id': 'u1'}, first['id'])
        self.write('tasks', 'update', {'status': 'done'}, first['id'])
        self.write('tasks', 'update', {'status': 'active', 'request_id': 'u1'}, first['id'])
        self.assertEqual(self.read('tasks', first['id'])['status'], 'done')
        pbody = {'minutes': 15, 'request_id': 'p1'}
        p = self.write('task_progress', 'create', pbody, parent=first['id'])
        self.assertEqual(p, self.write('task_progress', 'create', pbody, parent=first['id']))
        self.write('tasks', 'delete', {'request_id': 'd1'}, first['id'])
        self.assertTrue(self.write('tasks', 'delete', {'request_id': 'd1'}, first['id'])['deleted'])
        self.assertTrue(server.add_task(body)['deleted'])
        self.assertTrue(self.write('task_progress', 'create', pbody, parent=first['id'])['deleted'])
        self.assertEqual(self.read('task_progress'), [])

    def test_concurrent_requests_use_single_receipt(self):
        def write_without_server_lock(_):
            with server.connect() as c:
                return agent_state.mutate(c, 'tasks', 'create', {'title': '一次', 'request_id': 'concurrent'})
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(write_without_server_lock, range(8)))
        self.assertEqual(len({r['id'] for r in results}), 1)
        self.assertEqual(len(server.list_tasks()), 1)

    def test_bad_inputs_and_missing_links_never_write(self):
        invalid = [{'title': ''}, {'title': 1}, {'title': 'a' * 201}, {'title': 'x', 'shell': 'calc'},
                   {'title': 'x', 'status': []}, {'title': 'x', 'goal_id': 'missing'},
                   {'title': 'x', 'scheduled_at': 'bad'}, {'title': 'x', 'request_id': None}]
        for body in invalid:
            with self.subTest(body=body), self.assertRaises(ValueError):
                server.add_task(body)
        task = server.add_task({'title': '有效'})
        for body in ({'percent': True}, {'percent': -1}, {'percent': 101}, {'percent': float('nan')},
                     {'minutes': 1.5}, {'minutes': -1}, {'minutes': True}, {'note': []}, {}, {'recorded_at': 'bad'}):
            with self.subTest(body=body), self.assertRaises(ValueError):
                self.write('task_progress', 'create', body, parent=task['id'])
        with self.assertRaises(ValueError):
            self.write('task_progress', 'create', {'note': 'x'}, parent='missing')
        with self.assertRaises(ValueError):
            server.task_update('missing', {'status': 'done'})
        self.assertEqual(self.read('task_progress'), [])

    def test_database_failure_rolls_back_state_and_receipt(self):
        with server.connect() as c:
            c.execute("CREATE TRIGGER deny_receipt BEFORE INSERT ON agent_state_requests BEGIN SELECT RAISE(ABORT,'fixture'); END")
        with self.assertRaises(sqlite3.DatabaseError):
            server.add_task({'title': '不能成功', 'request_id': 'failure'})
        self.assertEqual(server.list_tasks(), [])
        with server.connect() as c:
            self.assertEqual(c.execute('SELECT count(*) FROM agent_state_requests').fetchone()[0], 0)
            c.execute('DROP TRIGGER deny_receipt')
        self.assertTrue(server.add_task({'title': '可以重试', 'request_id': 'failure'})['id'])

    def test_model_proposal_does_not_save_and_explicit_command_deduplicates(self):
        response = {'text': '我已完成计划', 'calls': [{'name': 'create_task', 'args': {'title': '学习'}}], 'model': 'fixture', 'usage': {}}
        for text in ('帮我生成学习计划', '不要添加任务', '例如添加任务学习'):
            result = server.consume_model_result(response, text, 'source', 'local', {})
            self.assertEqual(result['execution'][0]['status'], 'failed')
            self.assertNotIn('我已完成计划', result['reply'])
        self.assertEqual(server.list_tasks(), [])
        for _ in range(2):
            result = server.consume_model_result(response, '请添加任务学习', 'source', 'local', {})
            self.assertIn('记好', result['reply'])
        self.assertEqual(len(server.list_tasks()), 1)
        self.assertTrue(server.list_tasks()[0]['source_id'].startswith('user_message:source:msg_'))

    def test_structured_state_stays_out_of_model_context(self):
        goal = self.write('goals', 'create', {'title': 'PRIVATE_GOAL'})
        task = server.add_task({'title': 'PRIVATE_TASK', 'goal_id': goal['id']})
        self.write('task_progress', 'create', {'note': 'PRIVATE_PROGRESS'}, parent=task['id'])
        payload = server.context()
        self.assertNotIn('PRIVATE_', payload)
        self.assertNotIn('tasks', json.loads(payload))
        self.assertEqual(server.budget()['requests'], 0)

    @contextlib.contextmanager
    def http(self):
        srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        thread = threading.Thread(target=srv.serve_forever, daemon=True)
        thread.start()
        base = f'http://127.0.0.1:{srv.server_port}'
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        opener.open(base + '/').close()
        def request(path, body=None, method='GET', headers=None):
            req = urllib.request.Request(base + path, data=json.dumps(body).encode() if body is not None else None,
                                         method=method, headers={'Content-Type': 'application/json', **(headers or {})})
            with opener.open(req) as response:
                return json.load(response)
        try:
            yield base, request
        finally:
            srv.shutdown()
            srv.server_close()
            thread.join()

    def test_http_lifecycle_and_access_boundaries(self):
        with self.http() as (base, request):
            with self.assertRaises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(base + '/api/goals')
            self.assertEqual(error.exception.code, 403)
            with self.assertRaises(urllib.error.HTTPError) as error:
                request('/api/goals', {'title': 'x'}, 'POST', {'Origin': 'https://attacker.test'})
            self.assertEqual(error.exception.code, 403)
            goal = request('/api/goals', {'title': '学习', 'request_id': 'http-g'}, 'POST')
            self.assertEqual(request('/api/goals')['goals'], [goal])
            task = request('/api/tasks', {'title': '章节', 'goal_id': goal['id']}, 'POST')
            self.assertEqual(request('/api/goals/' + goal['id'])['task_ids'], [task['id']])
            self.assertEqual(request('/api/goals/' + goal['id'] + '/tasks')['tasks'][0]['id'], task['id'])
            result = request('/api/tasks/' + task['id'], {'status': 'active'}, 'PATCH')
            self.assertEqual(result['task']['status'], 'active')
            p = request('/api/tasks/' + task['id'] + '/progress', {'note': '例题', 'minutes': 20}, 'POST')
            self.assertEqual(request('/api/tasks/' + task['id'] + '/progress')['progress'], [p])
            self.assertEqual(request('/api/progress/' + p['id'])['minutes'], 20)
            request('/api/progress/' + p['id'], {'minutes': 10}, 'PATCH')
            request('/api/progress/' + p['id'], {}, 'DELETE')
            request('/api/goals/' + goal['id'], {'details': '修正'}, 'PATCH')
            request('/api/goals/' + goal['id'], {}, 'DELETE')
            request('/api/tasks/' + task['id'], {}, 'DELETE')
            self.assertEqual(request('/api/tasks')['tasks'], [])
            self.assertEqual(request('/api/health')['version'], '0.3.4')
            with self.assertRaises(urllib.error.HTTPError) as error:
                request('/api/goals', {'title': []}, 'POST')
            self.assertEqual(error.exception.code, 400)
            with patch('agent_state.mutate', side_effect=sqlite3.OperationalError('private fixture')):
                with self.assertRaises(urllib.error.HTTPError) as error:
                    request('/api/goals', {'title': '失败'}, 'POST')
            self.assertEqual(error.exception.code, 500)
            self.assertNotIn('private fixture', error.exception.read().decode())
            with self.assertRaises(urllib.error.HTTPError) as error:
                request('/api/tasks/fake/extra', {'status': 'done'}, 'PATCH')
            self.assertEqual(error.exception.code, 404)


if __name__ == '__main__':
    unittest.main()
