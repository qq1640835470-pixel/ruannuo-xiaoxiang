"""P0 compatibility and safe recovery using synthetic transport and temporary SQLite."""
import copy
import json
import sqlite3
import unittest
from unittest.mock import patch
import learning
import learning_checks as checks
import providers
import server
from learning_diagnostics import LearningError
import test_learning_checks as fixtures
QUESTIONS=fixtures.QUESTIONS

def topic_questions(topic):
    first,second,short={
        '零状态响应':(('零状态响应由什么引起？',['零初始状态下的外加输入','仅初始储能'], '零状态响应考察零初始状态下的外加输入作用。'),('零状态响应的初始状态条件是什么？',['独立储能状态为零','输入必须为零'],'零初始状态与零输入是不同条件。'),('区分零状态响应和零输入响应。','零状态响应由外加输入作用于零初始状态产生；零输入响应由初始储能在零输入下产生。')),
        '一阶RC电路':(('线性一阶RC电路的时间常数是什么？',['等效电阻乘电容','等效电阻除以电容'],'从电容端口看入的等效电阻与电容的乘积为时间常数。'),('直流稳态时理想电容等效为什么？',['开路','短路'],'直流稳态电压不变，电容电流为零。'),('列出分析一阶RC电路过渡过程需要的三个量。','电容电压初始值、最终值和时间常数。')),
        '电容充放电':(('采用关联参考方向时电容电流满足什么关系？',['i=C乘电压变化率','i等于恒定电压除以电容'],'电容电流与电容电压的变化率成正比。'),('理想电容储能表达式是什么？',['二分之一乘C乘电压平方','C乘电压'],'线性理想电容储能为二分之一C乘电压平方。'),('无冲击电流时电容电压能否突变？','不能；电容电压突变需要冲击电流。')),
    }[topic]
    rows=[]
    for prompt,options,explanation in (first,second):rows.append(dict(type='choice',prompt=prompt,options=options,answer=0,explanation=explanation,evidence='围绕'+topic+'的基本概念'))
    rows.append(dict(type='short',prompt=short[0],options=[],answer=short[1],explanation=short[1],evidence=topic))
    return {'questions':rows}

class LearningRepairTests(unittest.TestCase):
    setUp=fixtures.CheckTests.setUp
    tearDown=fixtures.CheckTests.tearDown

    def test_short_topics_anchored_explanatory_evidence_and_isolation(self):
        for i,topic in enumerate(('零状态响应','一阶RC电路','电容充放电')):
            rows=topic_questions(topic)
            result=checks.execute(server.connect,'generate',{'request_id':'topic'+str(i),'topic':topic},lambda *a:(json.dumps(rows),{'provider':'synthetic'}))
            with server.connect() as c:
                record=checks.get(c,result['id'],False)
                self.assertEqual(record['goal_id'],'');self.assertEqual(record['task_id'],'')
                self.assertEqual(record['scope']['content'],topic)
            response=checks.execute(server.connect,'submit',{'request_id':'answer'+str(i),'answers':{'1':0,'2':1,'3':'参考要点'},'evaluate_short':False},None,result['id'])
            with server.connect() as c:self.assertEqual(checks.get(c,response['id'])['results'][0]['verdict'],'correct')

    def test_format_normalization_preserves_missing_answer_rejection(self):
        rows=copy.deepcopy(QUESTIONS)
        rows['questions'][0].update(type='single_choice',answer='A',options={'A':'参考节点','B':'材料密度','C':'颜色'})
        rows['questions'][1]['answer']='0';rows['questions'][2].update(type='short_answer',options=None)
        parsed=learning.parse_model('\ufeff```JSON\n'+json.dumps(rows)+'\n```')
        result=checks.questions(parsed,{'title':'节点法','content':'','outcome':''},3)
        self.assertEqual(result[0]['answer'],0);self.assertEqual(result[2]['options'],[])
        del rows['questions'][0]['explanation']
        with self.assertRaises(ValueError):checks.questions(rows,{'title':'节点法','content':'','outcome':''},3)
        for raw in ('not-json','{"questions":',"{'questions':[]}"):
            with self.assertRaises(LearningError) as exc:learning.parse_model(raw)
            self.assertEqual(exc.exception.category,'invalid_json')

    def test_precise_errors_and_failed_retry_never_reinvokes_model(self):
        for index,(value,category) in enumerate((('not json','invalid_json'),('{"questions":[]}','question_schema'),('{"error":"具体一点"}','scope_unclear'))):
            called=[]
            def model(*args):called.append(1);return value,{}
            body={'request_id':'fail'+str(index),'topic':'零状态响应'}
            for _ in range(2):
                with self.assertRaises(LearningError) as exc:checks.execute(server.connect,'generate',body,model)
                self.assertEqual(exc.exception.category,category)
            self.assertEqual(len(called),1)
        with self.assertRaises(LearningError):checks.execute(server.connect,'generate',{'request_id':'vague','topic':'学习'},None)
        rows=copy.deepcopy(QUESTIONS)
        for q in rows['questions']:q['evidence']='无关范围'
        with self.assertRaises(LearningError) as exc:checks.execute(server.connect,'generate',{'request_id':'range','topic':'零状态响应'},lambda *a:(json.dumps(rows),{}))
        self.assertEqual(exc.exception.category,'scope_evidence')

    def test_database_failure_is_distinct_and_does_not_retry(self):
        with server.connect() as c:c.execute("CREATE TRIGGER fail_quiz BEFORE INSERT ON learning_checks BEGIN SELECT RAISE(ABORT,'PRIVATE'); END")
        body={'request_id':'dbfail','topic':'节点法'};called=[]
        def model(*args):called.append(1);return json.dumps(QUESTIONS),{}
        for _ in range(2):
            with self.assertRaises(LearningError) as exc:checks.execute(server.connect,'generate',body,model)
            self.assertEqual(exc.exception.category,'database');self.assertNotIn('PRIVATE',str(exc.exception))
        self.assertEqual(len(called),1)

    def test_reminder_start_already_active_keeps_original_task_row(self):
        import datetime as dt
        import learning_reminders
        from test_learning import PLAN
        server.learning_save({'request_id':'plan','plan':copy.deepcopy(PLAN)})
        task=next(t for t in server.list_tasks() if t['scheduled_at']=='2026-10-20')
        before=server.task_update(task['id'],{'status':'active'})['task']
        stamp=dt.datetime.fromisoformat('2026-10-20T10:00:00+08:00')
        with server.connect() as c:learning_reminders.write(c,'settings',{'request_id':'enable','enabled':True},stamp)
        with server.connect() as c:delivery=learning_reminders.check(c,{},stamp)['reminder']
        with server.connect() as c:result=learning_reminders.write(c,'action',{'request_id':'start','action':'start','reminder_id':delivery['id'],'task_id':task['id']},stamp)
        self.assertEqual(result['status'],'active')
        with server.connect() as c:self.assertEqual(dict(c.execute('SELECT * FROM tasks WHERE id=?',(task['id'],)).fetchone()),before)

    def test_local_reasoning_only_and_truncated_outputs_are_not_questions(self):
        import local_runtime,local_models
        route={'model':local_models.LARGE,'reason':'test','selection':'manual'}
        for finish,content in (('length','partial'),('stop','')):
            result={'model':local_models.LARGE,'choices':[{'finish_reason':finish,'message':{'content':content,'reasoning':'PRIVATE_REASONING'}}],'usage':{'prompt_tokens':5,'completion_tokens':9}}
            with patch('local_runtime.choose',return_value=route),patch('local_runtime.ensure_ready'),patch('local_runtime._request',return_value=result):
                with self.assertRaises(LearningError) as exc:local_runtime._chat_once([{'role':'user','content':'topic'}],{},model=local_models.LARGE,tools=[],instruction='JSON')
                self.assertEqual(exc.exception.category,'empty_truncated');self.assertNotIn('PRIVATE_REASONING',str(exc.exception))
                if finish=='length':self.assertEqual(exc.exception.usage['output_tokens'],9)

    def test_gemini_and_openrouter_finish_reasons_and_usage(self):
        self.cloud.stop()
        try:
            with patch('providers.hub.load_keys',return_value={'gemini':'synthetic','openrouter':'synthetic'}),patch('providers.openrouter_model',return_value={}):
                gemini={'modelVersion':'gemini-returned','candidates':[{'finishReason':'MAX_TOKENS','content':{'parts':[{'text':'{incomplete'}]}}],'usageMetadata':{'promptTokenCount':10,'candidatesTokenCount':5}}
                with patch('providers.post',return_value=gemini):
                    with self.assertRaises(LearningError) as exc:providers.chat('gemini',[{'role':'user','content':'主题'}],{},model=providers.MODELS['gemini'],allow_tools=False,instruction='JSON')
                    self.assertEqual(exc.exception.category,'empty_truncated');self.assertEqual(exc.exception.usage['output_tokens'],5)
                for content,finish in ((None,'stop'),('partial','length'),('   ','stop')):
                    reply={'model':'vendor/returned','choices':[{'finish_reason':finish,'message':{'content':content,'reasoning':'not a question'}}],'usage':{'prompt_tokens':3,'completion_tokens':7}}
                    with patch('providers.post',return_value=reply):
                        with self.assertRaises(LearningError) as exc:providers.chat('openrouter',[],{},model='vendor/requested',instruction='JSON',allow_tools=False)
                        self.assertEqual(exc.exception.category,'empty_truncated');self.assertEqual(exc.exception.usage['returned_model'],'vendor/returned')
                reply={'model':'vendor/returned','choices':[{'message':{'content':[{'type':'text','text':'```json\n{}\n```'}]}}],'usage':{}}
                metadata={'supported_parameters':['max_completion_tokens'],'context_length':20000,'max_completion_tokens':5000}
                with patch('providers.openrouter_model',return_value=metadata),patch('providers.post',return_value=reply) as post:
                    result=providers.chat('openrouter',[],{},model='vendor/requested',instruction='JSON',allow_tools=False,max_output_tokens=4096)
                    body=post.call_args.args[2];self.assertEqual(body['max_completion_tokens'],4096);self.assertNotIn('response_format',body);self.assertEqual(learning.parse_model(result['text']),{})
        finally:self.cloud.start()

if __name__=='__main__':unittest.main()
