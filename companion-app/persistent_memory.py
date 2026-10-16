"""Bounded local facts with user-message provenance; no generated summaries."""
from __future__ import annotations
import hashlib,json,re

MAX_FACTS=256
MAX_CONTEXT_CHARS=2800
SECRET=re.compile(r'(?:sk-[A-Za-z0-9_-]{10,}|AIza[A-Za-z0-9_-]{15,}|AQ\.[A-Za-z0-9_-]{15,}|Bearer\s+\S+|(?:api[_ -]?key|token|password|cookie|密码|密钥|口令)\s*(?:[:：=]|是|为)\s*\S+)',re.I)

def redact(text):return SECRET.sub('[凭据已遮蔽]',str(text))

def init(c):
    c.executescript('''CREATE TABLE IF NOT EXISTS memory_facts(
        id TEXT PRIMARY KEY,source_id TEXT,text TEXT,created_at TEXT,origin TEXT);
        CREATE INDEX IF NOT EXISTS memory_source ON memory_facts(source_id);
        CREATE TABLE IF NOT EXISTS learned_aliases(alias TEXT PRIMARY KEY,app TEXT,source_id TEXT,created_at TEXT);''')

def remember(c,text,source_id,created_at,origin='user'):
    text=redact(text).strip()[:500]
    if not text or text=='[凭据已遮蔽]':return None
    ident=hashlib.sha256((source_id+'\0'+text).encode()).hexdigest()[:32]
    c.execute('INSERT OR IGNORE INTO memory_facts VALUES(?,?,?,?,?)',(ident,source_id,text,created_at,origin))
    c.execute('DELETE FROM memory_facts WHERE id NOT IN (SELECT id FROM memory_facts ORDER BY rowid DESC LIMIT ?)',(MAX_FACTS,))
    return ident

def observe(c,text,source_id,created_at):
    if re.search(r'(?:不要|别|不用).{0,4}(?:记住|记录|保存)',text):return []
    found=[]
    for sentence in re.split(r'[。！？\n]',text):
        sentence=sentence.strip()
        if 4<=len(sentence)<=500 and (re.search(r'(?:叫我|称呼我)\s*[A-Za-z0-9\u4e00-\u9fff]{1,20}$',sentence) or re.match(r'^(?:(?:请|帮我)?记住[：:,，\s]*)?(?:我(?:的|是|在|住|叫|喜欢|不喜欢|习惯|希望|偏好|学|用|希望)|以后(?:叫我|称呼我))',sentence)):
            sentence=re.sub(r'^(?:请|帮我)?记住[：:,，\s]*','',sentence)
            ident=remember(c,sentence,source_id,created_at)
            if ident:found.append(ident)
    return found

def terms(text):
    text=re.sub(r'(?:记得|记住|什么|一下|这个|那个|我的|我是|你是|主人|可以|帮我)','',text.lower())
    return set(re.findall(r'[a-z0-9_]{2,}|[\u4e00-\u9fff]{2}',text))|{text[i:i+2] for i in range(len(text)-1) if all('\u4e00'<=ch<='\u9fff' for ch in text[i:i+2])}

def retrieve(c,query):
    wanted=terms(query)
    rows=[dict(row) for row in c.execute('SELECT * FROM memory_facts ORDER BY rowid DESC LIMIT ?',(MAX_FACTS,))]
    ranked=sorted(enumerate(rows),key=lambda pair:(len(terms(pair[1]['text'])&wanted),-pair[0]),reverse=True)
    result=[];size=2
    for index,row in ranked:
        score=len(terms(row['text'])&wanted)
        if not score and index>=3:continue
        item={k:row[k] for k in ('id','source_id','text','origin')}
        count=len(json.dumps(item,ensure_ascii=False))+(2 if result else 0)
        if size+count>MAX_CONTEXT_CHARS:continue
        result.append(item);size+=count
        if len(result)>=8:break
    return result

def learn_alias(c,alias,app,source_id,created_at,allowed):
    if not isinstance(alias,str) or not re.fullmatch(r'[\w\u4e00-\u9fff -]{1,30}',alias) or app not in allowed:raise ValueError('别名只能关联已支持的程序或服务。')
    c.execute('INSERT OR REPLACE INTO learned_aliases VALUES(?,?,?,?)',(alias.strip(),app,source_id,created_at))
    c.execute('DELETE FROM learned_aliases WHERE alias NOT IN (SELECT alias FROM learned_aliases ORDER BY rowid DESC LIMIT 64)')
    return {'alias':alias.strip(),'app':app,'source_id':source_id}
