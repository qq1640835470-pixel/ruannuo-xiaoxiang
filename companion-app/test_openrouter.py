"""Offline HTTP, isolated DPAPI and learning integration; no real API calls."""
import io
import json
import pathlib
import tempfile
import unittest
import urllib.error
from unittest.mock import patch
import configure_openrouter
import model_routing
import providers
import runtime_log
import server
import learning
from test_learning import REQ, PLAN

MODEL='vendor/test-model:free'
KEY='sk-or-test-only-never-valid-123456'
ROW={'id':MODEL,'name':'Friendly name','architecture':{'input_modalities':['text','image'],'output_modalities':['text']},
     'context_length':100000,'top_provider':{'max_completion_tokens':10000},
     'supported_parameters':['max_tokens','response_format','tools'],
     'pricing':{'prompt':'0.000001','completion':'0.000002'}}
REPLY={'model':MODEL,'choices':[{'message':{'content':'{"ok":true}'},'finish_reason':'stop'}],
       'usage':{'prompt_tokens':20,'completion_tokens':10,'cost':0.00004}}


class Response:
    def __init__(self,data):self.data=json.dumps(data).encode()
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def read(self,size):return self.data[:size]


class OpenRouterTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name)
        self.patches=[patch.object(server,'DATA',self.root),patch.object(server,'DB',self.root/'test.db'),
            patch.object(providers,'CATALOG_PATH',self.root/'catalogue.json'),patch.object(providers.hub,'VAULT',self.root/'providers.dpapi'),
            patch('urllib.request.OpenerDirector.open',side_effect=AssertionError('Live HTTP forbidden'))]
        for p in self.patches:p.start()
        server.init()
        self.catalogue()

    def tearDown(self):
        if server.MONITOR:server.MONITOR.close();server.MONITOR=None
        runtime_log._path=None
        for p in reversed(self.patches):p.stop()
        self.tmp.cleanup()

    def catalogue(self,row=None):
        providers.CATALOG_PATH.write_text(json.dumps({'openrouter':{'models':providers.normalize_models('openrouter',{'data':[row or ROW]})}}))

    def chat(self,reply=None,**kw):
        with patch('providers.hub.load_keys',return_value={'openrouter':KEY}),patch('providers.urllib.request.build_opener') as build:
            build.return_value.open.return_value=Response(reply or REPLY)
            result=providers.chat('openrouter',[{'role':'user','content':'test'}],'',model=MODEL,**kw)
            req=build.return_value.open.call_args.args[0]
            self.assertEqual(req.full_url,'https://openrouter.ai/api/v1/chat/completions')
            self.assertEqual(req.get_header('Authorization'),'Bearer '+KEY)
            self.assertEqual(build.return_value.open.call_args.kwargs['timeout'],45)
            return result,json.loads(req.data)

    def test_adapter_selection_and_old_defaults(self):
        self.assertTrue(providers.ADAPTERS['openrouter'].enabled)
        s=server.settings();s['provider']='openrouter';s['chat_models']['openrouter']=MODEL
        self.assertEqual(model_routing.choose('hello',s)['model'],MODEL)
        self.assertEqual(server.DEFAULT_SETTINGS['provider'],'gemini')
        self.assertFalse(server.DEFAULT_SETTINGS['routing_enabled'])

    def test_model_ids_and_text_filter(self):
        rows=providers.normalize_models('openrouter',{'data':[ROW,{**ROW,'id':'bad name'},{**ROW,'id':'vendor/image','architecture':{'input_modalities':['text'],'output_modalities':['image']}}]})
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['label'],'Friendly name')
        self.assertEqual(providers.validate_model('openrouter',MODEL),MODEL)
        for value in ('Friendly name','../escape','vendor/a?key=x',KEY,'vendor/sk-or-secret'):
            with self.assertRaises(ValueError):providers.validate_model('openrouter',value)

    def test_public_catalogue_refresh_and_offline_manual(self):
        with patch('providers.hub.load_keys',side_effect=AssertionError('Must not load keys')),patch('providers.urllib.request.build_opener') as build:
            build.return_value.open.return_value=Response({'data':[ROW]})
            data=providers.model_catalogue('openrouter',True)
            req=build.return_value.open.call_args.args[0]
            self.assertIsNone(req.get_header('Authorization'));self.assertEqual(req.method,'GET')
            self.assertEqual(data['models'][0]['id'],MODEL)
            build.return_value.open.side_effect=TimeoutError(KEY)
            failed=providers.model_catalogue('openrouter',True)
            self.assertEqual(failed['status'],'refresh_failed');self.assertEqual(failed['models'],data['models'])
            self.assertNotIn(KEY,json.dumps(failed))
        self.assertEqual(providers.validate_model('openrouter','vendor/manual-model'),'vendor/manual-model')

    def test_dpapi_preserves_existing_and_contains_no_plaintext(self):
        hub=providers.hub
        hub.VAULT.write_bytes(hub.protect(json.dumps({'deepseek':'test-other'}).encode()))
        configure_openrouter.save_key(KEY)
        self.assertNotIn(KEY.encode(),hub.VAULT.read_bytes())
        self.assertEqual(hub.load_keys(),{'deepseek':'test-other','openrouter':KEY})
        self.assertFalse(hub.VAULT.with_suffix('.tmp').exists())

    def test_failed_encryption_keeps_original(self):
        providers.hub.VAULT.write_bytes(b'original')
        with patch('providers.hub.load_keys',return_value={}),patch('providers.hub.protect',side_effect=RuntimeError(KEY)):
            with self.assertRaises(RuntimeError):configure_openrouter.save_key(KEY)
        self.assertEqual(providers.hub.VAULT.read_bytes(),b'original')

    def test_missing_key_has_instructions(self):
        with patch('providers.hub.load_keys',return_value={}):
            with self.assertRaisesRegex(ValueError,'DPAPI'):providers.chat('openrouter',[],'',model=MODEL)

    def test_success_body_usage_cost_and_no_secret_log(self):
        result,body=self.chat()
        self.assertEqual(body['model'],MODEL);self.assertNotIn('thinking',body);self.assertNotIn('tools',body)
        self.assertEqual(body['max_tokens'],1536);self.assertFalse(body['provider']['allow_fallbacks'])
        self.assertEqual(result['usage']['input_tokens'],20);self.assertEqual(result['usage']['estimate_cny'],0.0004)
        self.assertEqual(result['usage']['provider_reported_cost_usd'],0.00004)
        self.assertFalse(result['usage']['billing_amount_confirmed']);self.assertNotIn(KEY,(self.root/'logs/runtime.jsonl').read_text())

    def test_json_capability_and_limits(self):
        _,body=self.chat(instruction='Return JSON',max_output_tokens=8192,allow_tools=False)
        self.assertEqual(body['response_format'],{'type':'json_object'})
        row={**ROW,'supported_parameters':['max_completion_tokens']};self.catalogue(row)
        _,body=self.chat(instruction='Return JSON',max_output_tokens=2048)
        self.assertNotIn('response_format',body);self.assertEqual(body['max_completion_tokens'],2048)
        for row in ({**ROW,'context_length':100},{**ROW,'top_provider':{'max_completion_tokens':100}},{**ROW,'supported_parameters':[]}):
            self.catalogue(row)
            with self.assertRaises(ValueError):self.chat()

    def test_http_errors_are_safe_and_explicit(self):
        for code,expected in ((401,'认证'),(402,'额度不足'),(403,'权限'),(404,'模型不存在'),(408,'超时'),(429,'受限'),(503,'不可用')):
            with self.subTest(code=code),patch('providers.urllib.request.build_opener') as build:
                build.return_value.open.side_effect=urllib.error.HTTPError('https://example',code,KEY,{},io.BytesIO(json.dumps({'error':{'message':KEY}}).encode()))
                with self.assertRaises(providers.ProviderHTTPError) as caught:providers.post('https://example',KEY,{},'openrouter')
                self.assertIn(expected,providers.provider_error_message(caught.exception))
                self.assertNotIn(KEY,str(caught.exception));self.assertNotIn(KEY,json.dumps(caught.exception.diagnostic))
                self.assertEqual(build.return_value.open.call_count,1)

    def test_timeout_network_and_embedded_error(self):
        for exc in (TimeoutError(KEY),urllib.error.URLError(KEY)):
            with patch('providers.urllib.request.build_opener') as build:
                build.return_value.open.side_effect=exc
                with self.assertRaises(type(exc)):providers.post('https://example',KEY,{},'openrouter')
                self.assertNotIn(KEY,providers.provider_error_message(exc));self.assertEqual(build.return_value.open.call_count,1)
        with self.assertRaises(providers.ProviderHTTPError) as caught:self.chat({'error':{'code':402,'message':KEY}})
        self.assertEqual(caught.exception.code,402)

    def test_empty_truncated_and_missing_usage(self):
        for reply in ({'choices':[]},{'choices':[{'finish_reason':'length','message':{'content':'partial'}}]}):
            with self.assertRaises(ValueError):self.chat(reply)
        result,_=self.chat({**REPLY,'usage':{}})
        self.assertNotIn('estimate_cny',result['usage']);self.assertNotIn('provider_reported_cost_usd',result['usage'])

    def test_unknown_price_budget_is_retained(self):
        uid=server.reserve('openrouter','vendor/manual-model')
        server.settle(uid,{'input_tokens':20,'output_tokens':10})
        self.assertEqual(server.budget()['reserved_cny'],10)
        self.assertFalse(server.budget()['billing_balance_known'])
        with self.assertRaises(ValueError):server.reserve('openrouter',MODEL)

    def test_learning_selected_model_and_error(self):
        with server.connect() as c:
            c.execute("UPDATE settings SET value=? WHERE key='provider'",(json.dumps('openrouter'),))
            c.execute("UPDATE settings SET value=? WHERE key='chat_models'",(json.dumps({'openrouter':MODEL}),))
        with patch('providers.chat',return_value={'text':'{"ok":true}','model':MODEL,'usage':{'estimate_cny':0.001}}) as chat:
            text,metadata=server.learning_model('explicit input','JSON only',8192)
            self.assertEqual(metadata['requested_model'],MODEL);self.assertEqual(chat.call_args.args[2],{})
            self.assertFalse(chat.call_args.kwargs['allow_tools']);self.assertEqual(chat.call_args.kwargs['model'],MODEL)
        with patch('providers.chat',side_effect=providers.ProviderHTTPError('openrouter',402,{})):
            with self.assertRaisesRegex(ValueError,'额度不足'):server.learning_model('test','JSON',2048)

    def test_learning_json_through_http_adapter_without_saving(self):
        with server.connect() as c:
            c.execute("UPDATE settings SET value=? WHERE key='provider'",(json.dumps('openrouter'),))
            c.execute("UPDATE settings SET value=? WHERE key='chat_models'",(json.dumps({'openrouter':MODEL}),))
        plan={k:v for k,v in PLAN.items() if k!='requirements'}
        with patch('providers.hub.load_keys',return_value={'openrouter':KEY}),patch('providers.urllib.request.build_opener') as build:
            build.return_value.open.return_value=Response({**REPLY,'choices':[{'message':{'content':json.dumps(plan)}}]})
            result=learning.generate({'stage':'plan','requirements':REQ},server.learning_model,'2026-10-19')
            self.assertEqual(len(result['plan']['tasks']),2)
            body=json.loads(build.return_value.open.call_args.args[0].data)
            self.assertEqual(body['max_tokens'],8192);self.assertEqual(body['response_format'],{'type':'json_object'})
            self.assertEqual(len(body['messages']),2);self.assertNotIn('tools',body)
            build.return_value.open.return_value=Response({**REPLY,'choices':[{'message':{'content':'not JSON'}}]})
            with self.assertRaises(ValueError):learning.generate({'stage':'plan','requirements':REQ},server.learning_model,'2026-10-19')
        with server.connect() as c:self.assertEqual(c.execute('SELECT count(*) FROM tasks').fetchone()[0],0)

    def test_redirect_is_blocked_and_variable_prices_unknown(self):
        import urllib.request
        with self.assertRaises(urllib.error.HTTPError):
            providers.hub.NoRedirect().redirect_request(urllib.request.Request('https://openrouter.ai/api/v1/models'),None,302,'',{},'https://example.test')
        self.catalogue({**ROW,'pricing':{**ROW['pricing'],'overrides':[{'prompt':'1'}]}})
        self.assertIsNone(providers.model_rates('openrouter',MODEL))


if __name__=='__main__':unittest.main()
