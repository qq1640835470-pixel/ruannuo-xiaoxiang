"""Validate the small JSON-schema subset used by the local tool allowlist."""
from __future__ import annotations

def validate(call,schemas):
    if not isinstance(call,dict) or set(call)-{'name','args'}:raise ValueError('工具调用格式无效。')
    schema=next((s for s in schemas if s['name']==call.get('name')),None)
    if schema is None:raise ValueError('模型提出了尚未支持的工具，不执行。')
    args=call.get('args',{});parameters=schema.get('parameters',{})
    if not isinstance(args,dict) or set(args)-set(parameters.get('properties',{})):raise ValueError('工具参数不在支持清单中。')
    if set(parameters.get('required',[]))-set(args):raise ValueError('工具缺少必要参数。')
    kinds={'string':str,'boolean':bool,'object':dict,'array':list,'number':(int,float),'integer':int}
    for key,value in args.items():
        field=parameters['properties'][key];kind=field.get('type')
        if kind in kinds and (not isinstance(value,kinds[kind]) or kind in ('number','integer') and isinstance(value,bool)):raise ValueError('工具参数类型无效。')
        if 'enum' in field and value not in field['enum']:raise ValueError('工具参数值不支持。')
        if isinstance(value,str) and len(value)>field.get('maxLength',4000):raise ValueError('工具参数过长。')
    return args
