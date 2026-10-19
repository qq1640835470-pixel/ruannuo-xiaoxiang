"""Structured local state. No model context, scheduling or inference side effects."""
from __future__ import annotations
import datetime as dt
import hashlib
import json
import math
import re
import uuid

STATUSES = ('pending', 'active', 'paused', 'deferred', 'done', 'cancelled')
FIELDS = {
    'goals': {'title': 200, 'details': 2000, 'deadline': 40, 'status': 20},
    'tasks': {'title': 200, 'details': 2000, 'scheduled_at': 40, 'status': 20, 'goal_id': 64},
    'task_progress': {'note': 2000, 'percent': None, 'minutes': None, 'recorded_at': 40},
}


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec='microseconds')


def init(c):
    # Existing task IDs and statuses are retained; no positional INSERTs after migration.
    columns = {r[1] for r in c.execute('PRAGMA table_info(tasks)')}
    for name, definition in {'goal_id': "TEXT NOT NULL DEFAULT ''", 'updated_at': "TEXT NOT NULL DEFAULT ''",
                             'source_id': "TEXT NOT NULL DEFAULT 'legacy'",
                             'updated_source_id': "TEXT NOT NULL DEFAULT 'legacy'"}.items():
        if name not in columns:
            c.execute('ALTER TABLE tasks ADD COLUMN ' + name + ' ' + definition)
    c.execute("UPDATE tasks SET updated_at=created_at WHERE updated_at=''")
    c.execute('''CREATE TABLE IF NOT EXISTS goals(
        id TEXT PRIMARY KEY,title TEXT NOT NULL,details TEXT NOT NULL,deadline TEXT NOT NULL,
        status TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,
        source_id TEXT NOT NULL,updated_source_id TEXT NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS task_progress(
        id TEXT PRIMARY KEY,task_id TEXT NOT NULL,note TEXT NOT NULL,percent REAL,minutes INTEGER,
        recorded_at TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,
        source_id TEXT NOT NULL,updated_source_id TEXT NOT NULL)''')
    c.execute('CREATE INDEX IF NOT EXISTS tasks_goal ON tasks(goal_id)')
    c.execute('CREATE INDEX IF NOT EXISTS progress_task ON task_progress(task_id,created_at)')
    c.execute('''CREATE TABLE IF NOT EXISTS agent_state_requests(
        id TEXT PRIMARY KEY,fingerprint TEXT NOT NULL,response TEXT NOT NULL,
        entity TEXT NOT NULL,entity_id TEXT NOT NULL,created_at TEXT NOT NULL)''')


def ident(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', value):
        raise ValueError('记录或请求ID格式无效。')
    return value


def validate(table, body, creating=False):
    if not isinstance(body, dict) or set(body) - set(FIELDS[table]) - {'request_id'}:
        raise ValueError('状态参数不在支持清单中。')
    result = {}
    for key, value in body.items():
        if key == 'request_id':
            ident(value)
            continue
        limit = FIELDS[table][key]
        if limit is not None:
            if not isinstance(value, str) or len(value) > limit:
                raise ValueError('状态字段须为长度受限的文本。')
            value = value.strip()
            if key == 'title' and not value:
                raise ValueError('名称不能为空。')
            if key == 'status' and value not in STATUSES:
                raise ValueError('状态无效。')
            if key == 'goal_id' and value:
                ident(value)
            if key in ('deadline', 'scheduled_at', 'recorded_at') and value:
                try:
                    dt.datetime.fromisoformat(value)
                except ValueError:
                    raise ValueError('日期格式无效，请使用ISO日期时间。') from None
        elif key == 'percent':
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))
                                      or not math.isfinite(value) or not 0 <= value <= 100):
                raise ValueError('进度须为0至100的数字或null。')
        elif key == 'minutes':
            if value is not None and (type(value) is not int or not 0 <= value <= 1000000):
                raise ValueError('实际时长须为0至1000000的整数分钟或null。')
        result[key] = value
    if not result:
        raise ValueError('没有修改内容。')
    if creating and table != 'task_progress' and 'title' not in result:
        raise ValueError('缺少名称。')
    if table == 'task_progress' and creating and not (result.get('note') or result.get('percent') is not None or result.get('minutes') is not None):
        raise ValueError('进度记录需要备注、进度或实际时长。')
    return result


def get(c, table, record_id):
    ident(record_id)
    row = c.execute('SELECT * FROM ' + table + ' WHERE id=?', (record_id,)).fetchone()
    if row is None:
        raise ValueError('未找到记录。')
    return dict(row)


def read(c, table, record_id=None, parent=None):
    if table not in FIELDS:
        raise ValueError('记录类型无效。')
    if record_id:
        row = get(c, table, record_id)
        if table == 'goals':
            row['task_ids'] = [r[0] for r in c.execute('SELECT id FROM tasks WHERE goal_id=? ORDER BY created_at,id', (record_id,))]
        return row
    if parent:
        get(c, 'tasks' if table == 'task_progress' else 'goals', parent)
        key = 'task_id' if table == 'task_progress' else 'goal_id'
        return [dict(r) for r in c.execute('SELECT * FROM ' + table + ' WHERE ' + key + '=? ORDER BY created_at,id', (parent,))]
    return [dict(r) for r in c.execute('SELECT * FROM ' + table + ' ORDER BY created_at DESC,id')]


def mutate(c, table, action, body, record_id=None, parent=None, source='local_api', *, begin=True):
    """Caller commits; begin=False joins an already opened batch transaction."""
    if table not in FIELDS or action not in ('create', 'update', 'delete'):
        raise ValueError('状态操作无效。')
    if not isinstance(body, dict):
        raise ValueError('请求必须是对象。')
    if record_id is not None:
        ident(record_id)
    request_id = body.get('request_id')
    if 'request_id' in body:
        ident(request_id)
    fingerprint = hashlib.sha256(json.dumps([table, action, record_id, parent, body, source], sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()
    # Serialize across connections as well as HTTP threads, before reading receipts.
    if begin:
        c.execute('BEGIN IMMEDIATE')
    if request_id:
        receipt = c.execute('SELECT * FROM agent_state_requests WHERE id=?', (request_id,)).fetchone()
        if receipt:
            if receipt['fingerprint'] != fingerprint:
                raise ValueError('请求ID已用于不同内容，请使用新ID。')
            return json.loads(receipt['response'])
    stamp = now()
    source_id = source + ':' + (request_id or uuid.uuid4().hex)
    if action == 'delete':
        if set(body) - {'request_id'}:
            raise ValueError('删除仅接受request_id。')
        get(c, table, record_id)
        if table == 'goals':
            c.execute("UPDATE tasks SET goal_id='',updated_at=?,updated_source_id=? WHERE goal_id=?", (stamp, source_id, record_id))
        if table == 'tasks':
            for row in c.execute('SELECT id FROM task_progress WHERE task_id=?', (record_id,)).fetchall():
                erase_receipts(c, 'task_progress', row[0])
            c.execute('DELETE FROM task_progress WHERE task_id=?', (record_id,))
        c.execute('DELETE FROM ' + table + ' WHERE id=?', (record_id,))
        erase_receipts(c, table, record_id)
        result = {'ok': True, 'deleted': True, 'id': record_id}
    else:
        values = validate(table, body, action == 'create')
        if table == 'tasks' and values.get('goal_id'):
            get(c, 'goals', values['goal_id'])
        if action == 'create':
            record_id = uuid.uuid4().hex
            if table == 'task_progress':
                get(c, 'tasks', parent)
                row = dict(task_id=parent, note='', percent=None, minutes=None, recorded_at=stamp)
            else:
                row = dict(title='', details='', status='pending', **({'deadline': ''} if table == 'goals' else {'scheduled_at': '', 'goal_id': ''}))
            row.update(values, id=record_id, created_at=stamp, updated_at=stamp, source_id=source_id, updated_source_id=source_id)
            keys = list(row)
            c.execute('INSERT INTO ' + table + '(' + ','.join(keys) + ') VALUES(' + ','.join('?' for _ in keys) + ')', list(row.values()))
        else:
            current = get(c, table, record_id)
            if (table == 'tasks' and current['status'] in ('done', 'cancelled')
                    and 'status' in values and values['status'] not in ('done', 'cancelled')):
                raise ValueError('已完成或已取消的任务不能重新开始、暂停或延期。')
            if table != 'tasks' or values != {'status': current['status']}:
                values.update(updated_at=stamp, updated_source_id=source_id)
                c.execute('UPDATE ' + table + ' SET ' + ','.join(k + '=?' for k in values) + ' WHERE id=?', [*values.values(), record_id])
        result = get(c, table, record_id)
    if request_id:
        c.execute('INSERT INTO agent_state_requests VALUES(?,?,?,?,?,?)', (request_id, fingerprint, json.dumps(result, ensure_ascii=False), table, record_id, stamp))
    return result


def erase_receipts(c, table, record_id):
    # Keep deduplication tombstones without retaining deleted notes or titles.
    c.execute('UPDATE agent_state_requests SET response=? WHERE entity=? AND entity_id=?',
              (json.dumps({'ok': True, 'deleted': True, 'id': record_id}), table, record_id))
