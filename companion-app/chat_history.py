"""Bounded SQLite chat browsing and idempotent request receipts."""
import hashlib,json,re

def page(connection,query='',before=None,around=None,limit=30):
    limit=max(1,min(50,int(limit)));query=str(query).strip()[:200]
    args=[];where=[]
    if query:where.append('instr(lower(content),lower(?))>0');args.append(query)
    if before is not None:where.append('rowid<?');args.append(int(before))
    if around:
        found=connection.execute('SELECT rowid FROM messages WHERE id=?',(str(around)[:40],)).fetchone()
        if not found:return {'messages':[],'has_more':False,'next_before':None}
        where.append('rowid BETWEEN ? AND ?');args.extend([max(0,found[0]-12),found[0]+12])
    sql='SELECT rowid AS cursor,* FROM messages'+(' WHERE '+' AND '.join(where) if where else '')+' ORDER BY rowid DESC LIMIT ?'
    rows=[dict(row) for row in connection.execute(sql,(*args,limit+1))];more=len(rows)>limit;rows=rows[:limit];rows.reverse()
    for row in rows:
        row['actions']=json.loads(row.get('actions') or '[]');row['execution']=json.loads(row.get('execution') or '[]')
        row['attachments']=json.loads(row.get('attachments') or '[]')
        for action in row['actions']:
            latest=connection.execute('SELECT status,result FROM actions WHERE id=?',(action.get('id'),)).fetchone()
            if latest:action.update(dict(latest))
    return {'messages':rows,'has_more':more,'next_before':rows[0]['cursor'] if rows else None}

def request_id(value):
    if not isinstance(value,str) or not re.fullmatch('[a-f0-9]{32}',value):raise ValueError('消息请求编号无效。')
    return value

def init(connection):
    connection.execute('CREATE TABLE IF NOT EXISTS chat_requests(id TEXT PRIMARY KEY,text_hash TEXT,status TEXT,response TEXT,created_at TEXT)')

def digest(text):return hashlib.sha256(text.encode('utf-8')).hexdigest()
