"""Explicit learning searches: fixed transport, untrusted excerpts, selected bookmarks."""
import datetime as dt
import hashlib
import html
import ipaddress
import json
import re
import socket
import threading
import urllib.error
import urllib.parse
import urllib.request

import agent_state
import learning
from learning_diagnostics import LearningError

KINDS = {'video': '视频', 'text': '教材/讲义', 'practice': '练习题'}
SUFFIXES = {'video': '入门 教学视频', 'text': '公开教材 课程讲义', 'practice': '习题 练习'}
SEARCH_LOCK = threading.Lock()
ANALYZE_INSTRUCTION = ('你是学习资源需求整理器，只输出JSON，无工具权限。仅提取本次用户输入，不编造教材、链接或用户基础。'
    '输出且仅输出 {"course":"课程或空字符串","topic":"具体知识点或空字符串","level":"基础或未知",'
    '"kinds":["video","text","practice"]}。kinds仅包含用户需要的类型，综合或未指定时含三类。不要生成搜索结果。')
MESSAGES = {
    'missing_key': '尚未配置 Tavily Key，请在本机配置；没有执行搜索。',
    'auth': '搜索凭据无效或不可解密，未切换搜索服务。',
    'quota': '搜索额度不足或达到限额，已停止，没有升级或重试。',
    'free_only': '无法确认免费套餐且按量付费关闭，已停止搜索；请核对 Tavily 账号。',
    'timeout': '搜索超时，回执及额度状态可能不明，未自动重试。',
    'network': '搜索网络失败，回执及额度状态可能不明，未自动重试。',
    'rate_limit': '搜索服务限流，未自动重试。',
    'invalid_response': '搜索服务返回无效数据，未编造结果。',
    'pending': '原请求尚未完成或已中断，只能核对原回执；不会重新调用。',
    'model_failed': '需求解析未完成，请核对学习模型和预算，或手动填写；未自动重试。',
}


class ResourceError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(MESSAGES[code])


def stamp():
    return dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).isoformat(timespec='seconds')


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()).hexdigest()


def init(c):
    c.execute('''CREATE TABLE IF NOT EXISTS learning_resources(
        id TEXT PRIMARY KEY,url_key TEXT NOT NULL UNIQUE,payload TEXT NOT NULL,saved_at TEXT NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS learning_resource_tasks(
        resource_id TEXT NOT NULL,task_id TEXT NOT NULL,PRIMARY KEY(resource_id,task_id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS learning_search_calls(
        request_id TEXT NOT NULL,ordinal INTEGER NOT NULL,status TEXT NOT NULL,
        credits INTEGER,created_at TEXT NOT NULL,PRIMARY KEY(request_id,ordinal))''')


def requirements(body):
    if not isinstance(body, dict) or set(body) != {'course', 'topic', 'level', 'kinds'}:
        raise ValueError('请核对课程、具体知识点、基础和资源类型。')
    if not isinstance(body['course'], str):raise ValueError('课程须为文本。')
    result = {'course': learning.text(body['course'], 100) if body['course'] else '',
              'topic': learning.text(body['topic'], 120), 'level': learning.text(body['level'], 100)}
    kinds = body['kinds']
    if not isinstance(kinds, list) or not kinds or len(kinds) > 3 or any(not isinstance(k, str) or k not in KINDS for k in kinds) or len(set(kinds)) != len(kinds):
        raise ValueError('请选择视频、教材/讲义、练习题或综合资源。')
    for value in result.values():
        if any(ord(ch) < 32 for ch in value):raise ValueError('需求字段不能含控制字符。')
    result['kinds'] = [k for k in KINDS if k in kinds]
    return result


def plan(body):
    req = requirements(body)
    base = ' '.join(filter(None, [req['course'], req['topic']]))
    return {'requirements': req, 'queries': [{'kind': k, 'query': learning.text(base+' '+SUFFIXES[k], 180)} for k in req['kinds']],
            'destination': 'Tavily https://api.tavily.com/search；仅发送下列查询词，不发送基础、任务或历史。',
            'max_credits': len(req['kinds']), 'model_calls': 0}


def queries(body, req):
    if not isinstance(body, list) or len(body) != len(req['kinds']):raise ValueError('查询数量无效。')
    rows = []
    for row, kind in zip(body, req['kinds']):
        if not isinstance(row, dict) or set(row) != {'kind', 'query'} or row['kind'] != kind:raise ValueError('查询类型无效。')
        text = learning.text(row['query'], 180)
        if any(ord(ch) < 32 for ch in text):raise ValueError('查询词不能含控制字符。')
        rows.append({'kind': kind, 'query': text})
    return rows


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ResourceError('network')


def request_json(path, key, body=None):
    if path not in ('usage', 'search'):raise ValueError('不支持的搜索端点。')
    request = urllib.request.Request('https://api.tavily.com/'+path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={'Authorization': 'Bearer '+key, 'Content-Type': 'application/json'},
        method='POST' if body is not None else 'GET')
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=12) as reply:
            raw = reply.read(1024*1024+1)
        if len(raw) > 1024*1024:raise ResourceError('invalid_response')
        result = json.loads(raw)
        if not isinstance(result, dict):raise ResourceError('invalid_response')
        return result
    except urllib.error.HTTPError as exc:
        raise ResourceError('auth' if exc.code in (401, 403) else 'quota' if exc.code in (402, 432, 433) else 'rate_limit' if exc.code == 429 else 'network') from None
    except (TimeoutError, socket.timeout):
        raise ResourceError('timeout') from None
    except urllib.error.URLError as exc:
        raise ResourceError('timeout' if isinstance(exc.reason, TimeoutError) else 'network') from None
    except OSError:
        raise ResourceError('network') from None
    except (ValueError, UnicodeError) as exc:
        if isinstance(exc, ResourceError):raise
        raise ResourceError('invalid_response') from None


def load_key(hub):
    if not hub.VAULT.exists():raise ResourceError('missing_key')
    try:key = hub.load_keys().get('tavily', '')
    except Exception:raise ResourceError('auth') from None
    if not key:raise ResourceError('missing_key')
    if not isinstance(key, str) or not key.startswith('tvly-') or len(key) > 256 or any(ch.isspace() for ch in key):raise ResourceError('auth')
    return key


def free_allowance(value, needed):
    account = value.get('account', {});key = value.get('key', {})
    if not isinstance(account, dict) or not isinstance(key, dict):raise ResourceError('free_only')
    fields = [account.get(k) for k in ('plan_usage', 'plan_limit', 'paygo_usage', 'paygo_limit')]+[key.get(k) for k in ('usage', 'limit')]
    if any(type(n) is not int or n < 0 for n in fields):raise ResourceError('free_only')
    used, limit, pay_used, pay_limit, key_used, key_limit = fields
    if str(account.get('current_plan', '')).lower() not in ('researcher', 'free') or not 0 < limit <= 1000 or pay_used != 0 or pay_limit != 0:
        raise ResourceError('free_only')
    if limit-used < needed or (key_limit > 0 and key_limit-key_used < needed):raise ResourceError('quota')


def public_url(value):
    if not isinstance(value, str) or len(value) > 2000 or re.search(r'[\s\x00-\x20\x7f\\]', value):return None
    try:
        parts = urllib.parse.urlsplit(value);host = (parts.hostname or '').encode('idna').decode().lower().rstrip('.')
        if parts.scheme not in ('https', 'http') or parts.username or parts.password or parts.port not in (None, 80, 443):return None
        if '.' not in host or host.endswith(('.local', '.internal', '.localhost')) or not re.fullmatch(r'[a-z0-9.-]+', host) or not re.search(r'[a-z]', host.split('.')[-1]):return None
        if any(not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', p) for p in host.split('.')):return None
        try:ipaddress.ip_address(host);return None
        except ValueError:pass
        if re.fullmatch(r'[0-9.]+', host) or host.startswith('127.') or host == 'localhost':return None
        tracking = {'fbclid', 'gclid', 'spm_id_from', 'vd_source'}
        params = [(k, v) for k, v in urllib.parse.parse_qsl(parts.query, keep_blank_values=True) if not k.lower().startswith('utm_') and k.lower() not in tracking]
        canonical = urllib.parse.urlunsplit((parts.scheme, host+(':'+str(parts.port) if parts.port and parts.port != (443 if parts.scheme == 'https' else 80) else ''), parts.path or '/', urllib.parse.urlencode(sorted(params)), ''))
        return value, canonical, host
    except (ValueError, UnicodeError):return None


def plain(value, limit):
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]*>', ' ', html.unescape(value))).strip()[:limit] if isinstance(value, str) else ''


def classify(title, url, snippet):
    text = (title+' '+snippet).lower();parts = urllib.parse.urlsplit(url)
    host = (parts.hostname or '').lower()
    video_host = any(host == domain or host.endswith('.'+domain) for domain in ('bilibili.com', 'youtube.com', 'youtu.be'))
    if re.search(r'习题|练习|试题|题库|problem\s*set|exercises?|worksheet', text):return 'practice'
    if re.search(r'视频|教学录像|video|lecture video', text) or video_host and re.search(r'/video/|/watch|youtu.be/', url):return 'video'
    if re.search(r'教材|讲义|课件|教科书|textbook|lecture notes|\.pdf(?:[?#]|$)', text+' '+url.lower()):return 'text'
    return 'other'


def select_results(raw_rows, req, searched_at):
    terms = list(dict.fromkeys(t.lower() for t in re.findall(r'[A-Za-z0-9]{2,}|[\u4e00-\u9fff]+', req['topic'])))
    terms = [part for t in terms for part in ([t[i:i+2] for i in range(len(t)-1)] if re.fullmatch(r'[\u4e00-\u9fff]{3,}', t) else [t])]
    if not terms:return []
    seen = set();rows = []
    for row, query in raw_rows:
        if not isinstance(row, dict):continue
        link = public_url(row.get('url'));title = plain(row.get('title'), 220);snippet = plain(row.get('content'), 600)
        if not link or not title:continue
        url, canonical, host = link
        hits = [t for t in terms if t in (title+' '+snippet).lower()]
        if len(hits)/len(terms) < .5 or canonical in seen:continue
        kind = classify(title, url, snippet)
        if kind not in req['kinds']:continue
        seen.add(canonical)
        difficulty = '入门（初步判断）' if re.search(r'入门|基础|beginner|introduct', title, re.I) else '进阶（初步判断）' if re.search(r'进阶|高级|advanced', title, re.I) else '未知'
        rows.append({'id': digest(canonical)[:32], 'url': url, 'url_key': canonical, 'title': title,
            'source': host, 'kind': kind, 'snippet': snippet, 'reason': '标题或搜索摘录匹配知识点词：'+ '、'.join(hits[:5])+'；类型线索为'+KINDS[kind]+'。',
            'difficulty': difficulty, 'difficulty_confidence': '低，仅据标题' if difficulty != '未知' else '证据不足',
            'accessibility': '未核验；可能有登录、付费或地区限制', 'content_read': False,
            'excerpt_kind': 'search_result_excerpt', 'search_provider': 'Tavily Basic', 'searched_at': searched_at,
            'query': query, 'relevance': len(hits)/len(terms)})
    groups = [sorted((r for r in rows if r['kind'] == kind), key=lambda r: r['relevance'], reverse=True) for kind in req['kinds']]
    ordered = []
    while any(groups) and len(ordered) < 8:
        for group in groups:
            if group and len(ordered) < 8:ordered.append(group.pop(0))
    return ordered


def receipt(c, ident, fingerprint=None):
    row = c.execute('SELECT * FROM agent_state_requests WHERE id=?', (agent_state.ident(ident),)).fetchone()
    if not row or row['entity'] not in ('resource_analyze', 'resource_search', 'resource_save'):raise ValueError('没有该资源请求回执。')
    if fingerprint is not None and row['fingerprint'] != fingerprint:raise ValueError('请求ID内容冲突。')
    return json.loads(row['response'])


def execute(connect, operation, body, hub=None, model=None):
    allowed = {'analyze': {'request_id', 'text', 'model_selection', 'confirmed'},
               'search': {'request_id', 'requirements', 'queries', 'confirmed'}}
    if operation not in allowed or not isinstance(body, dict) or set(body) != allowed[operation] or body['confirmed'] is not True:raise ValueError('请核对并确认本次请求。')
    ident = agent_state.ident(body['request_id']);fingerprint = digest([operation, body])
    if operation == 'search':
        req = requirements(body['requirements']);qs = queries(body['queries'], req)
    else:learning.text(body['text'], 2500)
    with connect() as c:
        c.execute('BEGIN IMMEDIATE')
        if c.execute('SELECT 1 FROM agent_state_requests WHERE id=?', (ident,)).fetchone():return receipt(c, ident, fingerprint)
        c.execute('INSERT INTO agent_state_requests VALUES(?,?,?,?,?,?)', (ident, fingerprint, '{"state":"pending"}', 'resource_'+operation, '', stamp()))
    try:
        if operation == 'analyze':
            raw, metadata = model(body['text'], ANALYZE_INSTRUCTION, 1200)
            parsed = learning.parse_model(raw)
            if not isinstance(parsed, dict) or set(parsed) != {'course', 'topic', 'level', 'kinds'}:raise ResourceError('model_failed')
            result = {'requirements': requirements(parsed), 'model': metadata}
        else:
            with SEARCH_LOCK:
                key = load_key(hub);raw_rows = [];errors = [];credits = 0;uncertain = False
                for index, query in enumerate(qs):
                    try:
                        free_allowance(request_json('usage', key), len(qs)-index)
                        with connect() as c:c.execute('INSERT INTO learning_search_calls VALUES(?,?,?,?,?)', (ident, index, 'pending', None, stamp()))
                        data = request_json('search', key, {'query': query['query'], 'topic': 'general', 'search_depth': 'basic',
                            'max_results': 8, 'auto_parameters': False, 'include_answer': False, 'include_raw_content': False,
                            'include_images': False, 'include_usage': True})
                        reported = data.get('usage', {}).get('credits') if isinstance(data.get('usage', {}), dict) else None
                        known = type(reported) is int and reported == 1
                        with connect() as c:c.execute('UPDATE learning_search_calls SET status=?,credits=? WHERE request_id=? AND ordinal=?', ('completed' if known else 'unknown', 1 if known else None, ident, index))
                        if known:credits += 1
                        else:uncertain = True
                        rows = data.get('results')
                        if not isinstance(rows, list):raise ResourceError('invalid_response')
                        raw_rows.extend((row, query['query']) for row in rows[:20])
                        if not known:
                            errors.append({'code': 'usage_unknown', 'detail': '供应商未返回预期的1 credit用量，已停止后续查询；用量待核对。'});break
                    except ResourceError as exc:
                        with connect() as c:
                            c.execute("UPDATE learning_search_calls SET status='unknown' WHERE request_id=? AND ordinal=? AND status='pending'", (ident, index))
                        errors.append({'code': exc.code, 'detail': str(exc)});break
                found = select_results(raw_rows, req, stamp())
                with connect() as c:uncertain = uncertain or bool(c.execute("SELECT 1 FROM learning_search_calls WHERE request_id=? AND status='unknown'", (ident,)).fetchone())
                result = {'results': found, 'status': 'partial' if errors and found else 'unavailable' if errors else 'ok' if found else 'empty',
                    'errors': errors, 'missing_kinds': [KINDS[k] for k in req['kinds'] if not any(r['kind'] == k for r in found)],
                    'credits_reported': credits, 'usage_uncertain': uncertain, 'max_credits': len(qs),
                    'note': '仅搜索标题与摘录，未读取原文或核验链接；分类和难度为本机初判，无结果不会补造。'}
        response = {'state': 'completed', 'request_id': ident, 'result': result}
    except Exception as exc:
        code = exc.code if isinstance(exc, ResourceError) else 'model_failed' if operation == 'analyze' else 'invalid_response'
        response = {'state': 'failed', 'request_id': ident, 'code': code, 'detail': MESSAGES[code]}
        if isinstance(exc, LearningError):response.update(category=exc.category, detail=str(exc))
    with connect() as c:c.execute('UPDATE agent_state_requests SET response=? WHERE id=?', (json.dumps(response, ensure_ascii=False), ident))
    return response


def save(c, body):
    if not isinstance(body, dict) or set(body) != {'request_id', 'search_id', 'resource_ids', 'task_id'}:raise ValueError('保存参数无效。')
    ident = agent_state.ident(body['request_id']);fingerprint = digest(['save', body])
    c.execute('BEGIN IMMEDIATE')
    if c.execute('SELECT 1 FROM agent_state_requests WHERE id=?', (ident,)).fetchone():return receipt(c, ident, fingerprint)
    original = c.execute('SELECT entity FROM agent_state_requests WHERE id=?', (agent_state.ident(body['search_id']),)).fetchone()
    if not original or original['entity'] != 'resource_search':raise ValueError('必须从搜索回执选择资源。')
    search = receipt(c, body['search_id'])
    if search['state'] != 'completed':raise ValueError('搜索尚未完成。')
    ids = body['resource_ids']
    if not isinstance(ids, list) or not 1 <= len(ids) <= 8 or any(not isinstance(i, str) for i in ids) or len(set(ids)) != len(ids):raise ValueError('请选择1至8个不同资源。')
    available = {r['id']: r for r in search['result']['results']}
    if any(i not in available for i in ids):raise ValueError('所选资源不属于该搜索。')
    task_id = body['task_id']
    if not isinstance(task_id, str):raise ValueError('关联任务无效。')
    if task_id:
        task = agent_state.get(c, 'tasks', agent_state.ident(task_id))
        if not learning.decode(task['details']) or task['status'] == 'cancelled':raise ValueError('请选择有效的现有学习任务。')
    added = 0
    for ident_resource in ids:
        row = available[ident_resource]
        added += c.execute('INSERT OR IGNORE INTO learning_resources VALUES(?,?,?,?)', (row['id'], row['url_key'], json.dumps(row, ensure_ascii=False), stamp())).rowcount
        if task_id:c.execute('INSERT OR IGNORE INTO learning_resource_tasks VALUES(?,?)', (row['id'], task_id))
    result = {'state': 'completed', 'request_id': ident, 'saved': len(ids), 'added': added, 'task_id': task_id}
    c.execute('INSERT INTO agent_state_requests VALUES(?,?,?,?,?,?)', (ident, fingerprint, json.dumps(result), 'resource_save', '', stamp()))
    return result


def listing(c):
    rows = []
    for row in c.execute('SELECT * FROM learning_resources ORDER BY saved_at DESC,id LIMIT 100'):
        item = json.loads(row['payload']);item['saved_at'] = row['saved_at']
        item['tasks'] = [{'id': link['task_id'], 'title': link['title'] or '原任务已删除'} for link in c.execute('SELECT l.task_id,t.title FROM learning_resource_tasks l LEFT JOIN tasks t ON t.id=l.task_id WHERE l.resource_id=?', (row['id'],))]
        rows.append(item)
    return {'resources': rows}
