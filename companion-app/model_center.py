"""Local model preferences and evidence labels; reuses the provider catalogue and SQLite."""
import datetime as dt
import hashlib
import json
import math
import providers
import agent_state
from learning_diagnostics import MESSAGES

KEY='model_center_preferences'
RULES='learning-schema-v2'


def preferences(c):
    row=c.execute('SELECT value FROM settings WHERE key=?',(KEY,)).fetchone()
    return json.loads(row[0]) if row else {'favorites':[],'recent':[],'records':[]}


def store(c,value):
    c.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',(KEY,json.dumps(value,ensure_ascii=False)))


def signature(model,row=None):
    row=providers.openrouter_model(model) if row is None else row
    return hashlib.sha256(json.dumps({k:row.get(k) for k in ('context_length','max_completion_tokens','supported_parameters','input_modalities','output_modalities')},sort_keys=True).encode()).hexdigest()


def recent(c,model):
    if not providers.valid_openrouter_id(model):return
    value=preferences(c);value['recent']=[model]+[i for i in value['recent'] if i!=model][:19];store(c,value)


def record(c,model,outcome,version,*,check_id='',category='',origin='unverified',task='learning_check'):
    ident=model.get('requested_model')
    if model.get('provider')!='openrouter' or not providers.valid_openrouter_id(ident):return
    value=preferences(c)
    value['recent']=[ident]+[i for i in value['recent'] if i!=ident][:19]
    item={'model_id':ident,'returned_model':model.get('returned_model','unverified'),'task':task,'outcome':outcome,
          'category':category if category in MESSAGES else '', 'origin':origin if origin in ('unverified','simulated','real') else 'unverified',
          'time':agent_state.now(),'app_version':version,'rules':RULES,'signature':signature(ident),'check_id':check_id}
    value['records']=[item]+value['records'][:199];store(c,value)


def price(row,key):
    try:value=float(row.get('pricing',{})[key])*1000000
    except (KeyError,TypeError,ValueError,OverflowError):return None
    return value if math.isfinite(value) and value>=0 else None


def ability(row,output,context):
    inputs=row.get('input_modalities',[]);outputs=row.get('output_modalities',[])
    if inputs and 'text' not in inputs or outputs and 'text' not in outputs:return {'state':'incompatible','reason':'当前适配器仅发送文字'}
    params=row.get('supported_parameters',[])
    if row and params and not {'max_tokens','max_completion_tokens'}.intersection(params):return {'state':'incompatible','reason':'未声明当前适配器可用的输出长度参数'}
    maximum=row.get('max_completion_tokens');length=row.get('context_length')
    if isinstance(maximum,int) and maximum<output:return {'state':'incompatible','reason':f'输出上限低于{output} Token'}
    if isinstance(length,int) and length<context:return {'state':'incompatible','reason':f'上下文低于{context} Token的基础候选门槛'}
    if not inputs or not outputs or not params or not isinstance(maximum,int) or not isinstance(length,int):return {'state':'unknown','reason':'能力信息不完整，待验证'}
    return {'state':'candidate','reason':'元数据满足基础要求，可以尝试；尚不证明正确性或账号权限'}


def catalogue(c,version):
    # No refresh, networking or credentials. The existing explicit refresh remains the only fetch.
    result=providers.model_catalogue('openrouter');prefs=preferences(c);rows=[]
    for row in result['models']:
        ident=row['id'];inp,out=price(row,'prompt'),price(row,'completion')
        quiz=ability(row,4096,8192);plan=ability(row,8192,16384)
        records=[r for r in prefs['records'] if r['model_id']==ident]
        real=[r for r in records if r['origin']=='real' and r['outcome']=='success' and r['task']=='learning_check' and r.get('returned_model')==ident]
        verified=next((r for r in real if r['app_version']==version and r['rules']==RULES and r['signature']==signature(ident,row)),None)
        state='本机已验证（用户确认真实出题）' if verified else '旧验证可能过期' if real else '模拟测试成功，尚未真实验证' if any(r['origin']=='simulated' and r['outcome']=='success' for r in records) else '候选，尚未验证' if quiz['state']=='candidate' else '待验证'
        tags=[]
        if 'text' in row.get('input_modalities',[]) and 'text' in row.get('output_modalities',[]):tags.append('chat')
        if quiz['state']=='candidate':tags.append('learning')
        if 'reasoning' in row.get('supported_parameters',[]):tags.append('reasoning')
        if 'image' in row.get('input_modalities',[]):tags.append('vision')
        if inp==0 and out==0:tags.append('free')
        if inp is not None and out is not None and inp<=1 and out<=4:tags.append('low_cost')
        if ident in prefs['favorites']:tags.append('favorites')
        if ident in prefs['recent']:tags.append('recent')
        rows.append({**row,'vendor':ident.split('/')[0],'input_usd_million':inp,'output_usd_million':out,
                     'tags':tags,'learning_check':quiz,'learning_plan':plan,'verification':state,
                     'app_adapted':['文字对话','结构化学习文本（仍须校验）'],'image_input_adapted':False})
    return {'models':rows,'preferences':prefs,'rules':RULES,'app_version':version,'catalogue_status':result['status']}


def write(c,body,version):
    if not isinstance(body,dict) or set(body)-{'action','model_id','favorite','check_id','real_confirmation','request_id'}:raise ValueError('模型中心参数无效。')
    request_id=agent_state.ident(body.get('request_id'));fingerprint=hashlib.sha256(json.dumps(body,sort_keys=True).encode()).hexdigest()
    c.execute('BEGIN IMMEDIATE')
    old=c.execute('SELECT fingerprint,response FROM agent_state_requests WHERE id=?',(request_id,)).fetchone()
    if old:
        if old['fingerprint']!=fingerprint:raise ValueError('请求ID内容冲突。')
        return json.loads(old['response'])
    value=preferences(c)
    if body.get('action')=='favorite':
        ident=body.get('model_id')
        if not providers.valid_openrouter_id(ident) or type(body.get('favorite')) is not bool:raise ValueError('收藏型号无效。')
        value['favorites']=[i for i in value['favorites'] if i!=ident]
        if body['favorite']:value['favorites'].append(ident)
        if len(value['favorites'])>200:raise ValueError('最多收藏200个型号。')
        store(c,value)
    elif body.get('action')=='verify':
        if body.get('real_confirmation') is not True:raise ValueError('须明确确认这次为真实模型出题成功，而非模拟测试。')
        check_id=agent_state.ident(body.get('check_id'))
        row=c.execute('SELECT generation_model FROM learning_checks WHERE id=?',(check_id,)).fetchone()
        if row is None:raise ValueError('仅能确认已保存的有效测验。')
        if any(r.get('check_id')==check_id and r['origin']=='simulated' for r in value['records']):raise ValueError('模拟测试记录不能标为真实验证。')
        model=json.loads(row[0])
        if model.get('provider')!='openrouter' or not providers.valid_openrouter_id(model.get('requested_model')):raise ValueError('此测验没有可核对的OpenRouter请求型号。')
        if model.get('returned_model')!=model['requested_model']:raise ValueError('请求与返回型号不一致或返回型号未知，不能标记此型号已验证。请人工核对别名或上游回执。')
        prior=next((r for r in value['records'] if r.get('check_id')==check_id and r['task']=='learning_check' and r['outcome']=='success'),None)
        if not prior:raise ValueError('旧测验没有可核对的测试版本记录，请勿当作当前规则的真实验证。')
        if prior['model_id']!=model['requested_model'] or prior['returned_model']!=model['returned_model']:raise ValueError('测验与验证记录型号不一致，不能归属验证。')
        confirmed={**prior,'origin':'real','confirmed_at':agent_state.now()}
        value['records']=[confirmed]+value['records'][:199]
        store(c,value)
    else:raise ValueError('模型中心操作无效。')
    response={'ok':True}
    c.execute('INSERT INTO agent_state_requests VALUES(?,?,?,?,?,?)',(request_id,fingerprint,json.dumps(response),'model_center','preferences',agent_state.now()))
    return response
