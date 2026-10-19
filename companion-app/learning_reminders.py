"""Application-only learning nudges. No model, scheduler thread or learning inference."""
import datetime as dt
import hashlib
import json
import uuid
import agent_state
import learning
import learning_adjustments

KEY='learning_reminder_settings'
DEFAULTS=dict(enabled=False,window_start='09:00',window_end='21:00',quiet_start='22:00',quiet_end='08:00',daily_limit=4,paused_on='')
GAP=30*60


def local_now():
    return dt.datetime.now().astimezone()


def init(c):
    c.execute('''CREATE TABLE IF NOT EXISTS learning_reminders(
        id TEXT PRIMARY KEY,day TEXT NOT NULL,delivered_at REAL NOT NULL,
        state TEXT NOT NULL,wake_at REAL,snapshot TEXT NOT NULL)''')
    c.execute('CREATE INDEX IF NOT EXISTS reminders_day ON learning_reminders(day,delivered_at)')
    c.execute('INSERT OR IGNORE INTO settings VALUES(?,?)',(KEY,json.dumps(DEFAULTS)))


def settings(c):
    row=c.execute('SELECT value FROM settings WHERE key=?',(KEY,)).fetchone()
    return {**DEFAULTS,**(json.loads(row[0]) if row else {})}


def clock(value):
    try:
        if not isinstance(value,str) or len(value)!=5:raise ValueError()
        parsed=dt.time.fromisoformat(value)
        if parsed.second or parsed.tzinfo:raise ValueError()
        return parsed.hour*60+parsed.minute
    except ValueError:raise ValueError('提醒时间须为HH:MM。') from None


def within(minute,start,end):
    a,b=clock(start),clock(end)
    return a<=minute<b if a<b else minute>=a or minute<b


def permitted(s,now):
    minute=now.hour*60+now.minute
    return s['enabled'] and s['paused_on']!=now.date().isoformat() and within(minute,s['window_start'],s['window_end']) and not within(minute,s['quiet_start'],s['quiet_end'])


def data(c,now):
    """Read task metadata and explicit minutes only; never notes, answers or chat."""
    day=now.date().isoformat();all_tasks={};eligible={}
    for goal in c.execute('SELECT id,status,details FROM goals').fetchall():
        meta=learning.decode(goal['details'])
        if not meta:continue
        view=learning_adjustments.reminder_view(c,goal['id'],day)
        due={t['id'] for t in view['today_and_overdue']}
        for task in c.execute('SELECT id,title,status,scheduled_at,updated_at,details FROM tasks WHERE goal_id=?',(goal['id'],)):
            if not learning.decode(task['details']):continue
            item=dict(id=task['id'],goal_id=goal['id'],title=task['title'],course=meta['requirements']['course'],status=task['status'],date=task['scheduled_at'][:10],version=hashlib.sha256(json.dumps([dict(task),dict(goal)],sort_keys=True).encode()).hexdigest())
            all_tasks[item['id']]=item
            if item['id'] in due and goal['status'] not in ('done','cancelled'):eligible[item['id']]=item
    planned=[t for t in all_tasks.values() if t['date']==day and t['status']!='cancelled']
    minutes=[];unfilled=0;undated=0
    for p in c.execute('SELECT p.task_id,p.recorded_at,p.minutes FROM task_progress p JOIN tasks t ON t.id=p.task_id JOIN goals g ON g.id=t.goal_id WHERE g.details LIKE ?',('%'+learning.MARKER+'%',)):
        if p['task_id'] not in all_tasks:continue
        try:recorded=dt.datetime.fromisoformat(p['recorded_at'])
        except ValueError:
            undated+=1;continue
        if recorded.tzinfo is None:recorded=recorded.replace(tzinfo=now.tzinfo)
        if recorded.astimezone(now.tzinfo).date()!=now.date():continue
        if p['minutes'] is None:unfilled+=1
        else:minutes.append(p['minutes'])
    completed=sum(t['status']=='done' for t in planned)
    summary=dict(day=day,planned=len(planned),completed=completed,remaining=len(planned)-completed,
                 actual_minutes=sum(minutes) if minutes else None,unfilled_records=unfilled,undated_records=undated,
                 deferred=sum(t['status']=='deferred' for t in all_tasks.values() if t['status']!='cancelled'),
                 overdue=sum(t['date']<day for t in eligible.values()))
    return eligible,summary


def view(c,now):
    return {'settings':settings(c),'summary':data(c,now)[1]}


def current(c,row,now,eligible):
    if row['state']!='open' or row['day']!=now.date().isoformat():return None
    stamps=json.loads(row['snapshot'])
    tasks=[eligible[i] for i,version in stamps.items() if i in eligible and eligible[i]['version']==version]
    return {'id':row['id'],'tasks':tasks} if tasks else None


def check(c,body,now):
    if not isinstance(body,dict) or set(body)-{'current_id'}:raise ValueError('提醒检查参数无效。')
    c.execute('BEGIN IMMEDIATE')
    s=settings(c);eligible,summary=data(c,now)
    response={'settings':s,'summary':summary,'reminder':None}
    if not permitted(s,now):return response
    if body.get('current_id'):
        ident=agent_state.ident(body['current_id'])
        row=c.execute('SELECT * FROM learning_reminders WHERE id=?',(ident,)).fetchone()
        if row:
            response['reminder']=current(c,row,now,eligible)
            if response['reminder']:return response
    epoch=now.timestamp();day=now.date().isoformat()
    # Persisted wall-clock guard also suppresses deliveries after the clock moves back.
    last=c.execute('SELECT MAX(delivered_at) FROM learning_reminders').fetchone()[0]
    if last is not None and epoch<last:return response
    delivered=c.execute('SELECT count(*) FROM learning_reminders WHERE day=?',(day,)).fetchone()[0]
    if delivered>=s['daily_limit']:return response
    used=set()
    for r in c.execute('SELECT snapshot FROM learning_reminders WHERE day=?',(day,)):used.update(json.loads(r[0]))
    selected={i:t for i,t in eligible.items() if i not in used} if last is None or epoch-last>=GAP else {}
    # Coalesce all due snoozes with new tasks into one delivery; never replay a queue.
    due=c.execute("SELECT * FROM learning_reminders WHERE state='snoozed' AND wake_at<=?",(epoch,)).fetchall()
    for r in due:
        for ident,version in json.loads(r['snapshot']).items():
            if ident in eligible and eligible[ident]['version']==version:selected[ident]=eligible[ident]
        c.execute("UPDATE learning_reminders SET state='consumed' WHERE id=?",(r['id'],))
    if not selected:return response
    tasks=sorted(selected.values(),key=lambda t:(t['status']!='active',t['date'],t['id']))
    ident=uuid.uuid4().hex
    c.execute('INSERT INTO learning_reminders VALUES(?,?,?,?,?,?)',(ident,day,epoch,'open',None,json.dumps({t['id']:t['version'] for t in tasks})))
    response['reminder']={'id':ident,'tasks':tasks}
    return response


def write(c,operation,body,now):
    if not isinstance(body,dict):raise ValueError('提醒请求须为对象。')
    request_id=agent_state.ident(body.get('request_id'))
    fingerprint=hashlib.sha256(json.dumps([operation,body],sort_keys=True,allow_nan=False).encode()).hexdigest()
    c.execute('BEGIN IMMEDIATE')
    previous=c.execute('SELECT fingerprint,response FROM agent_state_requests WHERE id=?',(request_id,)).fetchone()
    if previous:
        if previous['fingerprint']!=fingerprint:raise ValueError('请求ID已用于其他内容。')
        return json.loads(previous['response'])
    s=settings(c);entity_id='settings'
    if operation=='settings':
        patch={k:v for k,v in body.items() if k!='request_id'}
        if not patch or set(patch)-{'enabled','window_start','window_end','quiet_start','quiet_end','daily_limit'}:raise ValueError('提醒设置字段无效。')
        for k,v in patch.items():
            if k=='enabled' and type(v) is not bool:raise ValueError('提醒开关无效。')
            if k=='daily_limit' and (type(v) is not int or not 1<=v<=8):raise ValueError('每日提醒上限须为1至8次。')
            if k.endswith(('_start','_end')):clock(v)
        s.update(patch)
        if s['window_start']==s['window_end'] or s['quiet_start']==s['quiet_end']:raise ValueError('开始与结束时间不能相同。')
        result={'ok':True,'settings':s}
    elif operation=='action':
        action=body.get('action')
        if set(body)-{'request_id','action','reminder_id','task_id','minutes'}:raise ValueError('提醒操作参数无效。')
        if action in ('pause','resume'):
            if set(body)-{'request_id','action'}:raise ValueError('暂停参数无效。')
            s['paused_on']=now.date().isoformat() if action=='pause' else ''
            if action=='pause':c.execute("UPDATE learning_reminders SET state='paused' WHERE state='open'")
        else:
            entity_id=agent_state.ident(body.get('reminder_id'))
            row=c.execute('SELECT * FROM learning_reminders WHERE id=?',(entity_id,)).fetchone()
            if not row or row['state']!='open' or row['day']!=now.date().isoformat():raise ValueError('提醒已处理或过期，请刷新。')
            if action=='start':
                if set(body)-{'request_id','action','reminder_id','task_id'}:raise ValueError('开始参数无效。')
                ident=agent_state.ident(body.get('task_id'));eligible,_=data(c,now)
                active=current(c,row,now,eligible)
                if not active or ident not in {t['id'] for t in active['tasks']}:raise ValueError('任务已修改、完成、取消或删除，请刷新计划。')
                if eligible[ident]['status']!='active':
                    agent_state.mutate(c,'tasks','update',{'status':'active'},ident,source='learning_reminder:'+request_id,begin=False)
            elif action=='snooze':
                if set(body)-{'request_id','action','reminder_id','minutes'} or type(body.get('minutes')) is not int or body['minutes'] not in (15,60):raise ValueError('稍后提醒只支持15或60分钟。')
            elif action!='dismiss' or set(body)-{'request_id','action','reminder_id'}:raise ValueError('提醒操作无效。')
            state={'start':'started','snooze':'snoozed','dismiss':'dismissed'}[action]
            wake=now.timestamp()+body['minutes']*60 if action=='snooze' else None
            c.execute('UPDATE learning_reminders SET state=?,wake_at=? WHERE id=?',(state,wake,entity_id))
        result={'ok':True,'action':action,'reminder_id':body.get('reminder_id')}
        if action=='start':result.update(task_id=body['task_id'],status='active')
    else:raise ValueError('提醒操作无效。')
    c.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',(KEY,json.dumps(s)))
    c.execute('INSERT INTO agent_state_requests VALUES(?,?,?,?,?,?)',(request_id,fingerprint,json.dumps(result),'learning_reminders',entity_id,agent_state.now()))
    return result
