"""Three bounded, explicitly authorized calls. No external actions or private file upload."""
import json, pathlib, urllib.error
import providers, server

server.init()
checks=[('gemini','用两句中文解释什么是负反馈，不要创建任务。'),
        ('gemini','请帮我准备一个百度地图检索深圳大学的操作入口。'),
        ('deepseek','只用一句中文介绍你能提供学习帮助，不要声称能控制未连接的软件。')]
results=[]
for provider,text in checks:
    uid=server.reserve(provider)
    try:
        r=providers.chat(provider,[{'role':'user','content':text}],'当前是初版功能测试，无个人通信和文件。')
        server.settle(uid,r['usage'])
        results.append({'provider':provider,'ok':True,'reply':r['text'],'calls':r['calls'],'usage':r['usage']})
    except Exception as e:
        server.settle(uid)
        results.append({'provider':provider,'ok':False,'http_status':e.code if isinstance(e,urllib.error.HTTPError) else None,
                        'error_type':type(e).__name__})
payload={'checks':results,'budget':server.budget()}
(pathlib.Path(__file__).parent/'qa-live-results.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(payload,ensure_ascii=False,indent=2))
