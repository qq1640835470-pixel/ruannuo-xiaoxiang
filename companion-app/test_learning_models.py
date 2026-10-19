"""Independent learning selection with temporary SQLite and synthetic HTTP only."""
import copy
import json
import tempfile
import unittest
import urllib.error
from unittest.mock import patch

import learning
import learning_checks
import model_center
import providers
import server
from local_models import selection as read_local_selection
from test_learning_system_034 import Fixture, MODEL

LEARNING='vendor/independent-learning'
OTHER='vendor/other-chat'


class SelectionFixture(Fixture):
    def __enter__(self):
        super().__enter__()
        cache=json.loads(providers.CATALOG_PATH.read_text(encoding='utf-8'))
        row=cache['openrouter']['models'][0]
        cache['openrouter']['models'] += [{**copy.deepcopy(row),'id':m,'label':m} for m in (LEARNING,OTHER)]
        cache['gemini']={'models':[{**copy.deepcopy(row),'id':'gemini-3.8-flash','label':'Synthetic Gemini 3.8 Flash'}],'fetched_at':server.now()}
        providers.CATALOG_PATH.write_text(json.dumps(cache),encoding='utf-8')
        return self

    def post(self,url,key,body,provider,*args,**kwargs):
        actual=body['model']
        if actual not in (MODEL,LEARNING,OTHER):raise AssertionError('Unexpected model or fallback')
        result=super().post(url,key,{**body,'model':MODEL},provider,*args,**kwargs)
        self.calls[-1]['body']=copy.deepcopy(body)
        result['model']=actual
        return result

    def configure(self,mode='independent',provider='openrouter',model=LEARNING):
        return self.request('/api/settings',{'learning_model_config':{'mode':mode,'provider':provider,'model':model}},'PATCH')


class LearningModelTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.fixture=SelectionFixture(self.tmp.name).__enter__();self.r=self.fixture.request

    def tearDown(self):
        self.fixture.__exit__(None,None,None);self.tmp.cleanup()

    def snapshot(self):return self.r('/api/settings')['learning_selection']

    def generate(self,request='analysis',**body):
        return self.r('/api/learning/generate',{'request_id':request,'stage':'analyze','text':'合成节点法要求',**body},'POST')

    def assert_failed(self,action,text=None):
        with self.assertRaises(urllib.error.HTTPError) as error:action()
        payload=json.load(error.exception)
        if text:self.assertIn(text,payload['error'])
        return payload

    def test_old_user_missing_keys_follows_chat_and_restart(self):
        with server.connect() as c:c.execute("DELETE FROM settings WHERE key IN ('learning_model_config','learning_selection_revision')")
        self.assertEqual(self.snapshot()['mode'],'follow');self.assertEqual(self.snapshot()['model'],MODEL)
        self.r('/api/settings',{'chat_models':{'openrouter':OTHER}},'PATCH')
        self.assertEqual(self.snapshot()['model'],OTHER)
        server.init();self.assertEqual(self.snapshot()['model'],OTHER)
        self.assertEqual(self.generate()['model']['requested_model'],OTHER)

    def test_independent_chat_pet_local_settings_unchanged_and_persistent(self):
        before=self.r('/api/settings');self.fixture.configure();chosen=self.snapshot()
        self.r('/api/settings',{'provider':'gemini','chat_models':{'gemini':'gemini-3.8-flash'}},'PATCH')
        self.assertEqual(self.snapshot(),chosen)
        server.init();after=self.r('/api/settings');self.assertEqual(after['learning_selection'],chosen)
        self.assertEqual(after['pet_models'],before['pet_models']);self.assertEqual(after['pet_provider'],before['pet_provider'])
        self.assertEqual(self.generate()['model']['requested_model'],LEARNING)
        self.fixture.configure('follow');self.assertEqual(self.snapshot()['model'],'gemini-3.8-flash')

    def test_six_entries_exact_route_usage_and_private_input_boundary(self):
        self.fixture.configure()
        server.add_message('user','PRIVATE_CHAT_SENTINEL')
        req=self.generate()['requirements']
        draft=self.generate('plan',stage='plan',requirements=req)
        goal=self.r('/api/learning/confirm',{'request_id':'save','plan':draft['plan']},'POST')
        saved=self.r('/api/learning/plans')['plans'][0];task=saved['tasks'][0]
        self.r('/api/learning/checks',{'request_id':'topic-quiz','topic':'节点法'},'POST')
        check=self.r('/api/learning/checks',{'request_id':'quiz','task_id':task['id']},'POST')
        self.r(f"/api/learning/checks/{check['id']}/submit",{'request_id':'submit','answers':{'1':0,'2':0,'3':'列式'},'evaluate_short':True},'POST')
        selection={'goal_id':goal['goal_id'],'revision':saved['revision'],'include_plan':True,'include_remaining':True,'progress_ids':[],'check_ids':[check['id']],'note':'合成调整'}
        view=self.r('/api/learning/adjustments/preview',{'selection':selection},'POST')
        result=self.r('/api/learning/adjustments/generate',{'request_id':'adjust','selection':selection,'preview_hash':view['preview_hash'],'model':view['model'],'confirmed':True},'POST')
        self.assertEqual(view['model']['model'],LEARNING);self.assertEqual(result['model']['requested_model'],LEARNING)
        self.assertEqual([r['stage'] for r in self.fixture.calls],['analyze','plan','check','check','evaluate','adjust'])
        self.assertEqual(json.loads(self.fixture.calls[2]['body']['messages'][-1]['content']),{'title':'自选知识点','content':'节点法','outcome':''})
        self.assertEqual(json.loads(self.fixture.calls[3]['body']['messages'][-1]['content'])['title'],task['title'])
        for call in self.fixture.calls:
            self.assertEqual(call['body']['model'],LEARNING);self.assertNotIn('PRIVATE_CHAT_SENTINEL',json.dumps(call['body']))
            self.assertNotIn('tools',call['body']);self.assertFalse(call['body']['provider']['allow_fallbacks'])
        for row in self.r('/api/usage')['usage']:
            meta=json.loads(row['metadata']);self.assertEqual(meta['requested_model'],LEARNING);self.assertEqual(meta['returned_model'],LEARNING)
        self.fixture.calls.clear()
        self.r('/api/chat',{'text':'合成聊天','client_request_id':'a'*32},'POST')
        self.assertEqual(self.fixture.calls[0]['body']['model'],MODEL)

    def test_preview_change_and_change_back_blocks_before_budget(self):
        old=self.snapshot();self.fixture.configure();self.fixture.configure('follow')
        self.assertNotEqual(old['revision'],self.snapshot()['revision'])
        with patch('server.reserve',side_effect=AssertionError('Must not reserve')):
            error=self.assert_failed(lambda:self.generate(model_selection=old),'学习模型选择已变化')
        self.assertEqual(error['category'],'selection_changed');self.assertEqual(self.fixture.calls,[])

    def test_adjustment_stale_preview_and_completed_receipt_after_change(self):
        plan={**copy.deepcopy(self.fixture.plan),'requirements':self.fixture.req}
        goal=self.r('/api/learning/confirm',{'request_id':'save','plan':plan},'POST')
        saved=self.r('/api/learning/plans')['plans'][0]
        selection={'goal_id':goal['goal_id'],'revision':saved['revision'],'include_plan':True,'include_remaining':False,'progress_ids':[],'check_ids':[],'note':''}
        view=self.r('/api/learning/adjustments/preview',{'selection':selection},'POST')
        body={'request_id':'adjust','selection':selection,'preview_hash':view['preview_hash'],'model':view['model'],'confirmed':True}
        self.fixture.configure()
        self.assert_failed(lambda:self.r('/api/learning/adjustments/generate',body,'POST'))
        self.assertEqual(self.fixture.calls,[])
        view=self.r('/api/learning/adjustments/preview',{'selection':selection},'POST')
        body.update(request_id='valid-adjust',model=view['model'],preview_hash=view['preview_hash'])
        result=self.r('/api/learning/adjustments/generate',body,'POST');self.fixture.configure('follow')
        self.assertEqual(result,self.r('/api/learning/adjustments/generate',body,'POST'));self.assertEqual(len(self.fixture.calls),1)

    def test_cloud_disabled_and_budget_stop_no_fallback(self):
        self.fixture.configure()
        self.r('/api/settings',{'api_generation_enabled':False},'PATCH')
        self.assert_failed(lambda:self.generate(),'云模型生成已关闭')
        self.r('/api/settings',{'api_generation_enabled':True,'budget_limit_cny':0,'local_fallback_enabled':True},'PATCH')
        self.assert_failed(lambda:self.generate('budget'),'预算剩余不足');self.assertEqual(self.fixture.calls,[])

    def test_missing_key_missing_model_and_unsupported_capacity_no_fallback(self):
        self.fixture.configure()
        with patch('providers.hub.load_keys',return_value={}):self.assert_failed(lambda:self.generate('no-key'))
        self.assertEqual(self.fixture.calls,[])
        with patch('providers.post',side_effect=providers.ProviderHTTPError('openrouter',404,{})) as transport:
            for _ in range(2):self.assert_failed(lambda:self.generate('missing'))
            self.assertEqual(transport.call_count,1);self.assertEqual(transport.call_args.args[2]['model'],LEARNING)
        with patch('providers.openrouter_model',return_value={'supported_parameters':['max_tokens'],'context_length':500,'max_completion_tokens':100}):
            self.assert_failed(lambda:self.generate('capacity'))
        self.assertEqual(self.fixture.calls,[])

    def test_receipt_recovery_analysis_and_plan_do_not_recall_after_restart_or_model_change(self):
        for stage in ('analyze','plan'):
            body={'request_id':'receipt-'+stage,'stage':stage,'text':'合成需求','model_selection':self.snapshot()}
            if stage=='plan':body={'request_id':'receipt-plan','stage':stage,'requirements':self.fixture.req,'model_selection':self.snapshot()}
            result=self.r('/api/learning/generate',body,'POST');server.init();self.fixture.configure()
            self.assertEqual(result,self.r('/api/learning/generate',body,'POST'))
        self.assertEqual(len(self.fixture.calls),2)

    def test_pending_and_conflicting_generation_request_never_calls(self):
        body={'request_id':'pending','stage':'analyze','text':'合成需求','model_selection':self.snapshot()}
        fingerprint=__import__('learning_adjustments').digest(body)
        with server.connect() as c:c.execute('INSERT INTO agent_state_requests VALUES(?,?,?,?,?,?)',('pending',fingerprint,'{"state":"pending"}','learning_generation','',server.now()))
        self.assert_failed(lambda:self.r('/api/learning/generate',body,'POST'))
        self.assert_failed(lambda:self.r('/api/learning/generate',{**body,'text':'不同内容'},'POST'))
        self.assertEqual(self.fixture.calls,[])

    def test_local_independent_and_follow_auto_preview_pin_exact_model(self):
        self.fixture.configure(provider='local',model=server.local_models.GEMMA)
        before=server.local_models.selection()
        with patch('local_runtime.status',return_value={'installed':True}),patch('local_models.installed',return_value=True),patch('providers.chat',return_value={'text':'{}','model':server.local_models.GEMMA}) as model:
            server.learning_model('合成输入','JSON',2048,expected_selection=self.snapshot())
            self.assertEqual(model.call_args.kwargs['model'],server.local_models.GEMMA)
        self.assertEqual(server.local_models.selection(),before)
        self.fixture.configure('follow');self.r('/api/settings',{'provider':'local'},'PATCH')
        with patch('local_models.selection',return_value='auto'),patch('local_runtime.choose',return_value={'model':server.local_models.SMALL}):
            view=self.r('/api/learning/model-preview',{'operation':'analyze','body':{'text':'合成输入'}},'POST')
            self.assertEqual(view['model']['model'],server.local_models.SMALL)
            with patch('local_runtime.status',return_value={'installed':True}),patch('local_models.installed',return_value=True),patch('providers.chat',return_value={'text':'{}','model':server.local_models.SMALL}) as model:
                server.learning_model('合成输入','JSON',2048,expected_selection=view['model'])
                self.assertEqual(model.call_args.kwargs['model'],server.local_models.SMALL)

    def test_preview_only_no_generation_and_no_key_loading(self):
        with patch('providers.hub.load_keys',side_effect=AssertionError('No key read in preview')):
            self.r('/api/learning/model-preview',{'operation':'analyze','body':{'text':'合成输入'}},'POST')
            self.r('/api/learning/model-preview',{'operation':'plan','body':{'requirements':self.fixture.req}},'POST')
            self.r('/api/learning/model-preview',{'operation':'check','body':{'topic':'零状态响应'}},'POST')
        self.assertEqual(self.fixture.calls,[]);self.assertEqual(self.r('/api/usage')['usage'],[])

    def test_mismatched_returned_model_cannot_gain_verification(self):
        from test_learning_checks import QUESTIONS
        result=learning_checks.execute(server.connect,'generate',{'request_id':'mismatch','topic':'节点法'},lambda *a:(json.dumps(QUESTIONS),{'provider':'openrouter','requested_model':LEARNING,'returned_model':OTHER}))
        with self.assertRaisesRegex(ValueError,'请求与返回型号不一致'):
            with server.connect() as c:model_center.write(c,{'request_id':'verify','action':'verify','check_id':result['id'],'real_confirmation':True},server.VERSION)
        value=self.r('/api/models/center');self.assertNotIn('本机已验证',next(r for r in value['models'] if r['id']==LEARNING)['verification'])

    def test_stale_short_evaluation_preserves_generated_check_without_paid_call(self):
        check=self.r('/api/learning/checks',{'request_id':'quiz','topic':'节点法'},'POST')
        selected=self.snapshot();self.fixture.configure()
        self.assert_failed(lambda:self.r(f"/api/learning/checks/{check['id']}/submit",{'request_id':'stale-eval','answers':{'1':0,'2':0,'3':'列式'},'evaluate_short':True,'model_selection':selected},'POST'))
        saved=self.r(f"/api/learning/checks/{check['id']}");self.assertEqual(saved['status'],'generated');self.assertEqual(saved['answers'],{})
        self.assertEqual(len(self.fixture.calls),1)

    def test_invalid_config_is_atomic_and_missing_snapshot_fails_closed(self):
        before=self.r('/api/settings')
        self.assert_failed(lambda:self.r('/api/settings',{'provider':'gemini','learning_model_config':{'mode':'independent','provider':'openrouter','model':'not an exact id'}},'PATCH'))
        self.assertEqual(self.r('/api/settings')['provider'],before['provider'])
        self.assertEqual(self.r('/api/settings')['learning_model_config'],before['learning_model_config'])
        with self.assertRaises(ValueError):server.learning_generate({'request_id':'no-preview','stage':'analyze','text':'合成输入'})
        self.assertEqual(self.fixture.calls,[])

    def test_plan_receipt_recovery_after_actual_write_response_lost(self):
        self.fixture.configure()
        body={'request_id':'plan-receipt','stage':'plan','requirements':self.fixture.req,'model_selection':self.snapshot()}
        result=self.r('/api/learning/generate',body,'POST')
        server.init();self.fixture.configure('follow')
        self.assertEqual(self.r('/api/learning/generate',body,'POST'),result)
        self.assertEqual(len(self.fixture.calls),1);self.assertEqual(self.r('/api/learning/plans')['plans'],[])

    def test_model_changes_and_restart_preserve_learning_history(self):
        goal=self.r('/api/learning/confirm',{'request_id':'save','plan':{**copy.deepcopy(self.fixture.plan),'requirements':self.fixture.req}},'POST')
        saved=self.r('/api/learning/plans')['plans'][0];task=saved['tasks'][0]
        self.r('/api/tasks/'+task['id']+'/progress',{'request_id':'progress','minutes':17,'note':'合成原始记录'},'POST')
        check=self.r('/api/learning/checks',{'request_id':'quiz','task_id':task['id']},'POST')
        self.r(f"/api/learning/checks/{check['id']}/submit",{'request_id':'answers','answers':{'1':0,'2':0,'3':'合成答案'},'evaluate_short':False},'POST')
        saved=self.r('/api/learning/plans')['plans'][0]
        selection={'goal_id':goal['goal_id'],'revision':saved['revision'],'include_plan':True,'include_remaining':True,'progress_ids':[],'check_ids':[check['id']],'note':''}
        view=self.r('/api/learning/adjustments/preview',{'selection':selection},'POST')
        self.r('/api/learning/adjustments/generate',{'request_id':'adjust','selection':selection,'preview_hash':view['preview_hash'],'model':view['model'],'confirmed':True},'POST')
        tables=('goals','tasks','task_progress','learning_checks','learning_adjustments')
        with server.connect() as c:before={name:[tuple(row) for row in c.execute('SELECT * FROM '+name+' ORDER BY rowid')] for name in tables}
        calls=len(self.fixture.calls)
        self.fixture.configure();self.r('/api/settings',{'chat_models':{'openrouter':OTHER}},'PATCH')
        self.fixture.configure('follow');self.fixture.configure();server.init()
        with server.connect() as c:after={name:[tuple(row) for row in c.execute('SELECT * FROM '+name+' ORDER BY rowid')] for name in tables}
        self.assertEqual(after,before);self.assertEqual(len(self.fixture.calls),calls)

    def test_follow_local_selection_round_trip_invalidates_preview_but_independent_does_not(self):
        models=server.local_models
        with patch.object(models.app_paths,'DATA',self.fixture.data),patch('local_models.selection',side_effect=read_local_selection),patch('local_models.installed',return_value=True),patch('local_runtime.choose',return_value={'model':models.SMALL}):
            self.r('/api/settings',{'provider':'local'},'PATCH')
            old=self.r('/api/learning/model-preview',{'operation':'analyze','body':{'text':'合成需求'}},'POST')['model']
            for model in (models.LARGE,'auto'):
                self.r('/api/local/model/control',{'operation':'select','model':model},'POST')
            self.assertGreater(self.snapshot()['revision'],old['revision'])
            with patch('server.reserve',side_effect=AssertionError('Stale local preview must not reserve')):
                self.assert_failed(lambda:self.generate(model_selection=old),'学习模型选择已变化')
            self.fixture.configure(provider='local',model=models.SMALL);independent=self.snapshot()
            self.r('/api/local/model/control',{'operation':'select','model':models.LARGE},'POST')
            self.assertEqual(self.snapshot(),independent)
        self.assertEqual(self.fixture.calls,[])

    def test_local_learning_preserves_actual_or_missing_returned_model(self):
        models=server.local_models
        self.fixture.configure(provider='local',model=models.SMALL)
        with patch('local_runtime.status',return_value={'installed':True}),patch('local_models.installed',return_value=True),patch('local_runtime.ensure_ready'):
            for actual in ('fixture/actual-local',None):
                reply={'choices':[{'message':{'content':'{}'}}],'usage':{'prompt_tokens':3,'completion_tokens':2}}
                if actual is not None:reply['model']=actual
                with patch('local_runtime._request',return_value=reply) as transport:
                    _,metadata=server.learning_model('合成输入','只输出JSON',2048,expected_selection=self.snapshot())
                self.assertEqual(metadata['requested_model'],models.SMALL)
                self.assertEqual(metadata['returned_model'],actual)
                self.assertEqual(transport.call_count,1)
                with server.connect() as c:row=c.execute('SELECT metadata FROM usage ORDER BY rowid DESC LIMIT 1').fetchone()
                self.assertEqual(json.loads(row['metadata'])['returned_model'],actual)


if __name__=='__main__':unittest.main()
