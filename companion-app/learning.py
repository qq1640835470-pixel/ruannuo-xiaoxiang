"""Learning drafts use no private history; confirmed plans share Agent state tables."""
import datetime as dt
import hashlib
import json
import agent_state

MARKER = 'learning_mvp_v1'
REQUIREMENTS = ('course', 'scope', 'start_date', 'deadline', 'daily_minutes', 'level')


def text(value, limit=500):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError('请填写长度适当的学习内容。')
    return value.strip()


def date(value):
    try:
        if not isinstance(value, str) or len(value) != 10:raise ValueError()
        return dt.date.fromisoformat(value)
    except (ValueError, TypeError):
        raise ValueError('请使用有效的年月日。') from None


def requirements(body):
    if not isinstance(body, dict) or set(body) != set(REQUIREMENTS):
        raise ValueError('请核对课程、范围、起止日期、每日时间和当前基础。')
    result = {k: text(body[k], 500 if k == 'scope' else 200) for k in REQUIREMENTS if k != 'daily_minutes'}
    minutes = body['daily_minutes']
    if type(minutes) is not int or not 1 <= minutes <= 720:
        raise ValueError('每日学习时间须为1至720分钟。')
    start, end = date(result['start_date']), date(result['deadline'])
    if not 0 <= (end-start).days <= 30:
        raise ValueError('MVP每次支持1至31天，请调整起止日期。')
    result['daily_minutes'] = minutes
    return result


def plan(body):
    if not isinstance(body, dict) or set(body) != {'requirements', 'title', 'outcome', 'tasks'}:
        raise ValueError('计划结构无效。')
    req = requirements(body['requirements'])
    rows = body['tasks']
    if not isinstance(rows, list) or not 2 <= len(rows) <= 93:
        raise ValueError('计划需要2至93项任务，并包含复习与练习。')
    tasks, days, kinds, ids = [], {}, set(), set()
    for row in rows:
        if not isinstance(row, dict) or set(row)-{'id','title','content','date','minutes','outcome','kind'} or not {'title','content','date','minutes','outcome','kind'} <= set(row):
            raise ValueError('学习任务结构无效。')
        item = {k: text(row[k], 200 if k == 'title' else 500) for k in ('title','content','outcome')}
        day = date(row['date'])
        if not date(req['start_date']) <= day <= date(req['deadline']):raise ValueError('任务日期必须在计划起止日期内。')
        if type(row['minutes']) is not int or not 1 <= row['minutes'] <= req['daily_minutes']:raise ValueError('任务时长超出每日可用时间。')
        if row['kind'] not in ('study','review','practice'):raise ValueError('任务类型无效。')
        days[row['date']] = days.get(row['date'], 0)+row['minutes']
        if days[row['date']] > req['daily_minutes']:raise ValueError('同一天任务总时长超出可用时间。')
        item.update(date=row['date'], minutes=row['minutes'], kind=row['kind'])
        kinds.add(row['kind'])
        if 'id' in row:
            ident = agent_state.ident(row['id'])
            if ident in ids:raise ValueError('同一任务不能重复出现。')
            ids.add(ident);item['id'] = ident
        tasks.append(item)
    expected={(date(req['start_date'])+dt.timedelta(days=i)).isoformat() for i in range((date(req['deadline'])-date(req['start_date'])).days+1)}
    if set(days)!=expected:raise ValueError('请为计划中的每一天安排学习、复习或练习。')
    if not {'review','practice'} <= kinds:raise ValueError('计划须包含复习和练习安排。')
    return {'requirements':req, 'title':text(body['title'],200), 'outcome':text(body['outcome']), 'tasks':tasks}


def decode(raw):
    try:
        value = json.loads(raw)
        return value if isinstance(value, dict) and value.get('type') == MARKER else None
    except (ValueError, TypeError):return None


def revision(goal, tasks):
    return hashlib.sha256(json.dumps([goal,tasks],sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def load(c, goal_id):
    goal = agent_state.read(c, 'goals', goal_id)
    meta = decode(goal['details'])
    if not meta:raise ValueError('该目标不是学习计划。')
    tasks = agent_state.read(c, 'tasks', parent=goal_id)
    rows = []
    for task in tasks:
        item = decode(task['details'])
        if not item:continue
        progress = agent_state.read(c,'task_progress',parent=task['id'])
        rows.append({**task, 'learning':item, 'progress':progress,
                     'actual_minutes':sum(p['minutes'] or 0 for p in progress)})
    return {'goal':goal, 'requirements':meta['requirements'], 'outcome':meta['outcome'],
            'tasks':rows, 'revision':revision(goal,tasks), 'mastery':None}


def listing(c):
    return [load(c,row['id']) for row in agent_state.read(c,'goals') if decode(row['details'])]


def save(c, body):
    if not isinstance(body,dict) or set(body)-{'request_id','plan','goal_id','revision'}:raise ValueError('保存参数无效。')
    request_id = agent_state.ident(body.get('request_id'))
    draft = plan(body.get('plan'))
    fingerprint = hashlib.sha256(json.dumps(['learning_save',body],sort_keys=True,ensure_ascii=False,allow_nan=False).encode()).hexdigest()
    c.execute('BEGIN IMMEDIATE')
    receipt = c.execute('SELECT * FROM agent_state_requests WHERE id=?',(request_id,)).fetchone()
    if receipt:
        if receipt['fingerprint'] != fingerprint:raise ValueError('请求ID已用于其他内容。')
        return json.loads(receipt['response'])
    goal_id = body.get('goal_id')
    existing = {}
    if goal_id:
        current = load(c,agent_state.ident(goal_id))
        if body.get('revision') != current['revision']:raise ValueError('计划已被修改，请刷新后重新编辑。')
        existing = {t['id']:t for t in current['tasks']}
    elif any('id' in t for t in draft['tasks']):raise ValueError('新计划不能引用已有任务。')
    source = 'learning_confirm:'+request_id
    goal_fields = {'title':draft['title'],'deadline':draft['requirements']['deadline'],
                   'details':json.dumps({'type':MARKER,'requirements':draft['requirements'],'outcome':draft['outcome']},ensure_ascii=False)}
    goal = agent_state.mutate(c,'goals','update' if goal_id else 'create',goal_fields,goal_id,source=source,begin=False)
    kept = set()
    for task in draft['tasks']:
        ident = task.get('id')
        if ident and ident not in existing:raise ValueError('任务不属于当前学习计划。')
        fields = {'title':task['title'],'goal_id':goal['id'],'scheduled_at':task['date'],
                  'details':json.dumps({'type':MARKER,**{k:task[k] for k in ('content','minutes','outcome','kind')}},ensure_ascii=False)}
        agent_state.mutate(c,'tasks','update' if ident else 'create',fields,ident,source=source,begin=False)
        if ident:kept.add(ident)
    for ident in existing.keys()-kept:
        agent_state.mutate(c,'tasks','update',{'status':'cancelled'},ident,source=source,begin=False)
    result = {'ok':True,'goal_id':goal['id'],'request_id':request_id}
    c.execute('INSERT INTO agent_state_requests VALUES(?,?,?,?,?,?)',(request_id,fingerprint,json.dumps(result),'goals',goal['id'],agent_state.now()))
    return result


def parse_model(raw):
    try:
        if not isinstance(raw,str) or len(raw)>60000:raise ValueError()
        value=raw.strip()
        if value.startswith('```json') and value.endswith('```'):value=value[7:-3]
        result=json.loads(value)
        if not isinstance(result,dict):raise ValueError()
        return result
    except (ValueError,TypeError):raise ValueError('模型未返回有效的结构化数据；未生成计划，请重试或调整需求。') from None


def generate(body, call_model, today):
    if not isinstance(body,dict) or set(body)-{'stage','text','requirements'}:raise ValueError('学习请求无效。')
    stage=body.get('stage')
    if stage=='analyze':
        content=text(body.get('text'),2500)
        instruction='你是学习需求整理器，只输出JSON。只从用户输入提取，不编造课程范围、考试日期或掌握情况。未知字段填空字符串，daily_minutes未知填null。相对日期以今天为基准。输出 {"requirements":{"course":"","scope":"","start_date":"YYYY-MM-DD或空","deadline":"YYYY-MM-DD或空","daily_minutes":null,"level":""},"questions":["影响计划的待确认问题"]}。今天：'+today
        result,meta=call_model(content,instruction,2048)
        value=parse_model(result)
        req=value.get('requirements');questions=value.get('questions')
        if not isinstance(req,dict) or set(req)!=set(REQUIREMENTS) or not isinstance(questions,list) or len(questions)>8:raise ValueError('模型需求分析结构无效，请手动填写信息。')
        if any(not isinstance(v,str) or len(v)>500 for k,v in req.items() if k!='daily_minutes') or (req['daily_minutes'] is not None and (type(req['daily_minutes']) is not int or not 1<=req['daily_minutes']<=720)):raise ValueError('模型提取信息无效，请手动填写。')
        return {'requirements':req,'questions':[text(q,300) for q in questions],'model':meta}
    if stage=='plan':
        req=requirements(body.get('requirements'))
        if date(req['start_date']) < date(today):raise ValueError('新草稿开始日期不能早于今天。')
        instruction='你是学习计划规划器，只输出JSON，无工具权限。用户已核对信息，不能更改或增加课程范围、截止日期和基础。生成简洁可行的每日安排，包含复习和练习，单日总分钟不超过daily_minutes。只输出 {"title":"目标名","outcome":"预期成果，不宣称已经掌握","tasks":[{"title":"任务名","content":"具体内容","date":"YYYY-MM-DD","minutes":30,"kind":"study或review或practice","outcome":"预期可观察成果"}]}。2至93项，每项内容和成果尽量简短。不虚构教材章节或考试信息。'
        result,meta=call_model(json.dumps(req,ensure_ascii=False),instruction,8192)
        value=parse_model(result)
        if set(value)!={'title','outcome','tasks'} or not isinstance(value.get('tasks'),list) or any(isinstance(t,dict) and 'id' in t for t in value.get('tasks',[])):raise ValueError('模型计划结构无效。')
        value['requirements']=req
        return {'plan':plan(value),'model':meta}
    raise ValueError('学习请求阶段无效。')
