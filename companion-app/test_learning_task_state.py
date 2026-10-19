"""Task state acceptance with synthetic history, temporary SQLite and no model calls."""
import datetime as dt
import json
import pathlib
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error

import app_paths

# Redirect auxiliary stores before importing the application, including desktop profiles.
ISOLATED = tempfile.TemporaryDirectory(prefix='xiaoxiang-task-state-')
HOME = pathlib.Path(ISOLATED.name)
app_paths.HOME = HOME
app_paths.DATA = HOME / 'data'
app_paths.MODELS = HOME / 'models'

def reject_private_access(event, args):
    if event in ('open', 'sqlite3.connect', 'os.listdir', 'os.scandir') and args and isinstance(args[0], (str, bytes)):
        path = str(args[0]).replace('\\', '/').lower()
        if path.startswith('d:/studylifeplan/companion-data'):
            raise AssertionError('Formal private data access forbidden')

sys.addaudithook(reject_private_access)

import agent_state
import learning_checks
import learning_reminders
import server
from test_learning_checks import QUESTIONS
from test_learning_system_034 import Fixture


def seed(fixture):
    fixture.request('/api/learning/confirm', {'request_id': 'plan', 'plan': {'requirements': fixture.req, **fixture.plan}}, 'POST')
    task = fixture.request('/api/learning/plans')['plans'][0]['tasks'][0]
    fixture.request('/api/tasks/' + task['id'] + '/progress', {'request_id': 'history', 'minutes': 17, 'note': '合成原学习记录'}, 'POST')
    learning_checks.execute(server.connect, 'generate', {'request_id': 'quiz-history', 'task_id': task['id']}, lambda *args: (json.dumps(QUESTIONS), {'provider': 'synthetic'}))
    return task['id']


class TaskStateTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(dir=HOME)
        self.fixture = Fixture(self.folder.name).__enter__()
        self.task_id = seed(self.fixture)
        self.path = '/api/tasks/' + self.task_id

    def tearDown(self):
        self.assertEqual(self.fixture.calls, [])
        self.fixture.__exit__(None, None, None)
        self.folder.cleanup()

    def update(self, status, request):
        receipt = self.fixture.request(self.path, {'status': status, 'request_id': request}, 'PATCH')
        self.assertTrue(receipt['ok'])
        current = self.fixture.request(self.path)
        self.assertEqual(receipt['task'], current)
        self.assertEqual(current['status'], status)
        return current

    def test_pause_resume_done_receipts_history_and_restart(self):
        history = self.fixture.request(self.path + '/progress')
        quizzes = self.fixture.request('/api/learning/checks')
        with server.connect() as c:
            originals = {table: [tuple(r) for r in c.execute('SELECT * FROM ' + table + ' ORDER BY id')] for table in ('task_progress', 'learning_checks', 'learning_check_requests')}
        self.update('active', 'start')
        paused = self.update('paused', 'pause')
        server.init()
        self.assertEqual(self.fixture.request(self.path), paused)
        code = 'import sqlite3,sys;c=sqlite3.connect(sys.argv[1]);print(c.execute("SELECT status FROM tasks WHERE id=?",(sys.argv[2],)).fetchone()[0])'
        result = subprocess.run([sys.executable, '-c', code, str(server.DB), self.task_id], capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout.strip(), 'paused')
        self.update('active', 'resume')
        done = self.update('done', 'done')
        self.assertEqual(self.fixture.request(self.path + '/progress'), history)
        self.assertEqual(self.fixture.request('/api/learning/checks'), quizzes)
        with server.connect() as c:
            for table, rows in originals.items():
                self.assertEqual([tuple(r) for r in c.execute('SELECT * FROM ' + table + ' ORDER BY id')], rows)
        # A stale successful receipt cannot change the later completed task.
        self.fixture.request(self.path, {'status': 'active', 'request_id': 'resume'}, 'PATCH')
        self.assertEqual(self.fixture.request(self.path), done)

    def test_same_status_does_not_update_row_or_trigger(self):
        active = self.update('active', 'start')
        with server.connect() as c:
            c.execute("CREATE TRIGGER no_update BEFORE UPDATE ON tasks BEGIN SELECT RAISE(ABORT,'must not write'); END")
        self.assertEqual(self.update('active', 'same-state'), active)
        self.assertEqual(self.update('active', 'start'), active)

    def test_terminal_states_reject_start_pause_defer_including_legacy_rows(self):
        for status in ('done', 'cancelled'):
            task = self.fixture.request('/api/tasks', {'title': '合成历史任务', 'status': status}, 'POST')
            for target in ('active', 'paused', 'pending', 'deferred'):
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    self.fixture.request('/api/tasks/' + task['id'], {'status': target, 'request_id': status + target}, 'PATCH')
                self.assertEqual(caught.exception.code, 400)
                self.assertIn('已完成或已取消', json.load(caught.exception)['error'])
            self.assertEqual(self.fixture.request('/api/tasks/' + task['id']), task)

    def test_failed_transaction_rolls_back_task_and_receipt(self):
        active = self.update('active', 'start')
        with server.connect() as c:
            c.execute("CREATE TRIGGER fail_pause BEFORE UPDATE ON tasks WHEN NEW.status='paused' BEGIN SELECT RAISE(ABORT,'synthetic write failure'); END")
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.fixture.request(self.path, {'status': 'paused', 'request_id': 'fail'}, 'PATCH')
        self.assertEqual(caught.exception.code, 500)
        self.assertEqual(json.load(caught.exception)['category'], 'database')
        self.assertEqual(self.fixture.request(self.path), active)
        with server.connect() as c:
            self.assertIsNone(c.execute("SELECT * FROM agent_state_requests WHERE id='fail'").fetchone())

    def test_reminder_stale_pause_snapshot_rejected_fresh_start_preserves_history(self):
        stamp = dt.datetime.fromisoformat(self.fixture.req['start_date'] + 'T10:00:00+08:00')
        with server.connect() as c:
            learning_reminders.write(c, 'settings', {'request_id': 'enable', 'enabled': True}, stamp)
        with server.connect() as c:
            delivery = learning_reminders.check(c, {}, stamp)['reminder']
        self.update('active', 'start')
        self.update('paused', 'pause')
        with self.assertRaisesRegex(ValueError, '任务已修改'):
            with server.connect() as c:
                learning_reminders.write(c, 'action', {'request_id': 'stale-reminder', 'action': 'start', 'reminder_id': delivery['id'], 'task_id': self.task_id}, stamp)
        with server.connect() as c:
            delivery = learning_reminders.check(c, {}, stamp + dt.timedelta(days=1))['reminder']
        before = self.fixture.request(self.path + '/progress')
        with server.connect() as c:
            result = learning_reminders.write(c, 'action', {'request_id': 'fresh-reminder', 'action': 'start', 'reminder_id': delivery['id'], 'task_id': self.task_id}, stamp + dt.timedelta(days=1))
        self.assertEqual(result['status'], 'active')
        self.assertEqual(self.fixture.request(self.path)['status'], 'active')
        self.assertEqual(self.fixture.request(self.path + '/progress'), before)


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] in ('--ui', '--failure', '--baseline', '--serve'):
        mode = sys.argv[1]
        with Fixture(HOME) as fixture:
            task_id = seed(fixture)
            before = fixture.request('/api/learning/checks')
            if mode == '--serve':
                (HOME / 'ISOLATED-034').touch()
                (HOME / 'control.json').write_text(json.dumps({'base': fixture.base, 'task_id': task_id}), encoding='utf-8')
                print(json.dumps({'folder': str(HOME), 'base': fixture.base, 'task_id': task_id}), flush=True)
                while not (HOME / 'STOP').exists():
                    time.sleep(.25)
            else:
                if mode == '--failure':
                    with server.connect() as c:
                        c.execute("CREATE TRIGGER fail_pause BEFORE UPDATE ON tasks WHEN NEW.status='paused' BEGIN SELECT RAISE(ABORT,'synthetic write failure'); END")
                baseline = HOME / 'baseline-learning.js'
                if mode == '--baseline':
                    repo = server.ROOT.parent if (server.ROOT.parent / '.git').exists() else server.ROOT.parent / 'github-export' / 'ruannuo-xiaoxiang'
                    baseline.write_bytes(subprocess.run(['git', '-C', str(repo), 'show', '91f18e631db40a6a9d8ec0bd655645b0f3ec4af8:companion-app/web/learning.js'], check=True, capture_output=True).stdout)
                result = subprocess.run(['node', 'test_learning_task_state_ui.cjs', fixture.base, task_id, mode, str(baseline)], cwd=server.ROOT)
                if result.returncode:
                    raise SystemExit(result.returncode)
            assert fixture.request('/api/learning/checks') == before
            assert len(fixture.request('/api/tasks/' + task_id + '/progress')['progress']) == 1
            assert fixture.calls == [], 'No model calls allowed'
    else:
        unittest.main()
