"""Explicit, bounded live regression fixture. Prints metadata, never prompts or keys."""
from __future__ import annotations
import argparse,json,pathlib
import providers,server

def run():
    server.init();model=providers.MODELS['gemini'];cases=[]
    target=pathlib.Path(__file__).parent/'artifacts'/'gemini-31-schema-diagnostic.json'
    previous=json.loads(target.read_text(encoding='utf-8')) if target.is_file() else {}
    for label,tools in [('original_schema',providers.TOOLS),('adapted_schema',providers.gemini_tools(providers.TOOLS))]:
        body={'contents':[{'role':'user','parts':[{'text':'Say hello briefly.'}]}],
              'tools':[{'functionDeclarations':tools}],'generationConfig':{'maxOutputTokens':32}}
        envelope={'input_token_upper_bound':len(json.dumps(body,ensure_ascii=False).encode('utf-8'))+1024,'max_output_tokens':32}
        cases.append((label,body,envelope))
    ceiling=sum(providers.reservation('gemini',model,0,envelope) for _,_,envelope in cases)
    total=ceiling+previous.get('protective_ceiling_cny',0)
    if total>.1 or server.budget()['remaining_cny']<ceiling:raise ValueError('诊断保护预算超出0.10元或现有剩余额度。')
    records=previous.get('records',[])
    for label,body,envelope in cases:
        ident=server.reserve('gemini',model,envelope=envelope)
        meta={'purpose':'gemini_schema_diagnostic','case':label,'requested_model':model,'input_token_upper_bound':envelope['input_token_upper_bound'],'max_output_tokens':32}
        try:
            result=providers.post('https://generativelanguage.googleapis.com/v1beta/models/'+model+':generateContent',providers.hub.load_keys()['gemini'],body,'gemini')
            usage=result.get('usageMetadata',{});tin=usage.get('promptTokenCount');tout=usage.get('candidatesTokenCount',0)+usage.get('thoughtsTokenCount',0)
            meta.update(input_tokens=tin,output_tokens=tout,returned_model=result.get('modelVersion'),status='completed',has_candidates=bool(result.get('candidates')))
            if isinstance(tin,int):
                a,b=providers.model_rates('gemini',model);meta['estimate_cny']=round((tin*a+tout*b)/1000000,6)
            server.settle(ident,meta)
        except Exception as exc:
            meta.update(status='unknown',diagnostic=exc.diagnostic if isinstance(exc,providers.ProviderHTTPError) else {'error_type':type(exc).__name__,'http_status':getattr(exc,'code',None)})
            server.settle(ident,meta)
        records.append({'usage_id':ident,**meta})
    report={'protective_ceiling_cny':total,'records':records,'budget':server.budget(),
            'note':'错误原文、提示词与密钥均未保留；被拒绝请求未取得用量仍保留预留，未假定免费。'}
    target.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=True,indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--live',action='store_true');args=parser.parse_args()
    if not args.live:parser.error('仅显式--live才会调用提供方；调用沿用现有累计10元预算。')
    run()
