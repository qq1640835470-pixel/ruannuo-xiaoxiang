import copy,json,subprocess,tempfile
from test_learning_system_034 import Fixture
from test_learning_repairs import topic_questions
import server

if __name__=='__main__':
    with tempfile.TemporaryDirectory() as folder:
        fixture=Fixture(folder);original=fixture.post
        def post(url,key,body,provider,*args,**kwargs):
            result=original(url,key,body,provider,*args,**kwargs)
            if fixture.calls[-1]['stage']=='check':
                selected=json.loads(body['messages'][-1]['content'])
                if selected['title']=='自选知识点':
                    rows=topic_questions(selected['content'])
                    result['choices'][0]['message']['content']='```JSON\n'+json.dumps(rows,ensure_ascii=False)+'\n```'
            return result
        fixture.post=post
        with fixture:
            fixture.request('/api/learning/confirm',{'request_id':'plan','plan':{'requirements':fixture.req,**fixture.plan}},'POST')
            r=subprocess.run(['node','test_learning_repairs_ui.cjs',fixture.base],cwd=server.ROOT)
        raise SystemExit(r.returncode)
