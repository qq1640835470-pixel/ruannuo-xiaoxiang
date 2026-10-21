"""Learning workbench: temporary SQLite, synthetic services, deny formal data access."""
import datetime as dt
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

import app_paths

ISOLATED = tempfile.TemporaryDirectory(prefix='xiaoxiang-workbench-')
HOME = pathlib.Path(ISOLATED.name)
app_paths.HOME = HOME
app_paths.DATA = HOME / 'data'
app_paths.MODELS = HOME / 'models'
PRIVATE_ATTEMPTS = []


def reject_private_access(event, args):
    if event in ('open', 'sqlite3.connect', 'os.listdir', 'os.scandir') and args and isinstance(args[0], (str, bytes)):
        path = str(args[0]).replace('\\', '/').lower()
        if path.startswith('d:/studylifeplan/companion-data'):
            PRIVATE_ATTEMPTS.append(event)
            raise AssertionError('Formal private data access forbidden')


sys.addaudithook(reject_private_access)
from test_learning_resources import ResourceFixture
import learning
import server


class WorkbenchFixture(ResourceFixture):
    def tavily(self, path, key, body=None):
        result = super().tavily(path, key, body)
        if path == 'search':
            result['results'] = [
                {'title': '回顾参考节点与节点电压 '+kind, 'url': url, 'content': '合成电路分析 回顾参考节点与节点电压 '+kind}
                for kind, url in [('教学视频', 'https://www.bilibili.com/video/BVfixture'), ('教材讲义', 'https://example.org/node.pdf'), ('练习题', 'https://example.org/practice')]]
        return result


def seed(fixture):
    today = dt.date.fromisoformat(fixture.req['start_date'])
    plan = {**fixture.plan, 'requirements': fixture.req}
    fixture.request('/api/learning/confirm', {'request_id': 'workbench-plan', 'plan': plan}, 'POST')
    saved = fixture.request('/api/learning/plans')['plans'][0]
    task = next(t for t in saved['tasks'] if t['learning']['kind'] == 'review')
    fixture.request('/api/tasks', {'title': '昨日学习任务', 'goal_id': saved['goal']['id'], 'scheduled_at': (today-dt.timedelta(days=1)).isoformat(), 'details': json.dumps({'type': learning.MARKER, 'content': '参考节点', 'outcome': '说明变量', 'minutes': 20, 'kind': 'review'})}, 'POST')
    with server.connect() as c:
        row = {'id': 'workbench-resource', 'url': 'https://example.org/learning/node', 'url_key': 'https://example.org/learning/node', 'title': '节点法合成讲义', 'source': 'example.org', 'kind': 'text', 'searched_at': '2026-01-01', 'snippet': '合成节点法', 'reason': '合成匹配', 'query': '节点法', 'difficulty': '未知', 'difficulty_confidence': '未读取原文', 'accessibility': '待核对'}
        c.execute('INSERT INTO learning_resources VALUES(?,?,?,?)', (row['id'], row['url_key'], json.dumps(row), '2026-01-01'))
        c.execute('INSERT INTO learning_resource_tasks VALUES(?,?)', (row['id'], task['id']))
        for i in range(101):
            filler = {**row, 'id': f'filler-{i}', 'url_key': f'https://example.org/{i}', 'url': f'https://example.org/{i}', 'title': '其他任务资源'}
            c.execute('INSERT INTO learning_resources VALUES(?,?,?,?)', (filler['id'], filler['url_key'], json.dumps(filler), '2026-10-01'))
    return task['id']


class WorkbenchTests(unittest.TestCase):
    def test_task_resources_not_limited_by_global_recent_100(self):
        with tempfile.TemporaryDirectory() as folder, WorkbenchFixture(folder) as fixture:
            ident = seed(fixture)
            self.assertEqual(len(fixture.request('/api/learning/resources')['resources']), 100)
            rows = fixture.request('/api/learning/resources?task_id='+ident)['resources']
            self.assertEqual([r['id'] for r in rows], ['workbench-resource'])
            self.assertEqual(rows[0]['tasks'][0]['id'], ident)
            other = next(t for t in fixture.request('/api/learning/plans')['plans'][0]['tasks'] if t['id'] != ident)
            self.assertEqual(fixture.request('/api/learning/resources?task_id='+other['id'])['resources'], [])
            self.assertEqual(fixture.calls, [])
            self.assertEqual(fixture.search_calls, [])
        self.assertEqual(PRIVATE_ATTEMPTS, [])


if __name__ == '__main__':
    if len(sys.argv)>1 and sys.argv[1] in ('--ui', '--serve'):
        with WorkbenchFixture(HOME) as fixture:
            ident = seed(fixture)
            if sys.argv[1] == '--ui':
                result = subprocess.run(['node', 'test_learning_workbench_ui.cjs', fixture.base, ident], cwd=server.ROOT)
                assert not PRIVATE_ATTEMPTS
                print(json.dumps({'private_path_attempts': len(PRIVATE_ATTEMPTS), 'synthetic_models': [c['stage'] for c in fixture.calls], 'synthetic_searches': len([c for c in fixture.search_calls if c[0]=='search'])}))
                raise SystemExit(result.returncode)
            (HOME/'ISOLATED-034').touch()
            (HOME/'control.json').write_text(json.dumps({'base': fixture.base, 'task_id': ident}), encoding='utf-8')
            print(json.dumps({'folder':str(HOME),'base':fixture.base,'task_id':ident}), flush=True)
            import time
            while not (HOME/'STOP').exists(): time.sleep(.25)
    else: unittest.main()
