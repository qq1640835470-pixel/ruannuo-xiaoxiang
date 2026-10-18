"""Offline regressions for model compatibility, memory, routing and spending gates."""
import http.cookiejar,http.server,io,json,pathlib,tempfile,threading,types,unittest,urllib.error,urllib.request
from unittest.mock import patch
import connectors,model_routing,persistent_memory,providers,server,typed_tools

class CoreRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.old=(server.DATA,server.DB,providers.CATALOG_PATH)
        server.DATA=pathlib.Path(self.tmp.name);server.DB=server.DATA/'test.sqlite3';providers.CATALOG_PATH=server.DATA/'catalogue.json';server.init()
    def tearDown(self):
        server.DATA,server.DB,providers.CATALOG_PATH=self.old;self.tmp.cleanup()

    def test_gemini_schema_keeps_canonical_constraints_and_noarg_tool(self):
        before=json.dumps(providers.TOOLS);adapted=providers.gemini_tools(providers.TOOLS)
        self.assertEqual(json.dumps(providers.TOOLS),before)
        self.assertNotIn('additionalProperties',json.dumps(adapted));self.assertNotIn('maxLength',json.dumps(adapted))
        self.assertNotIn('parameters',next(t for t in adapted if t['name']=='show_balances'))
        with self.assertRaises(ValueError):typed_tools.validate({'name':'weather','args':{'location':'x'*81}},providers.TOOLS)
        with self.assertRaises(ValueError):typed_tools.validate({'name':'configure_local','args':{'operation':'health','shell':'bad'}},providers.TOOLS)

    def test_safe_error_retains_actionable_keyword_never_original_message(self):
        raw=json.dumps({'error':{'status':'INVALID_ARGUMENT','message':'Unknown name "additionalProperties" at tools[0].function_declarations[5].parameters. user=private-prompt sk-123456789012345 tools[0].privateprompt'}}).encode()
        result=providers.safe_error('gemini',400,raw)
        self.assertEqual(result['category'],'unsupported_schema_keyword');self.assertEqual(result['schema_keywords'],['additionalProperties'])
        self.assertEqual(result['field_paths'],['tools[0].function_declarations[5].parameters'])
        self.assertNotIn('private',json.dumps(result));self.assertNotIn('sk-',json.dumps(result))
        class Opener:
            def open(self,*args,**kwargs):raise urllib.error.HTTPError('https://s.test',400,'private',{},io.BytesIO(raw))
        with patch('providers.urllib.request.build_opener',return_value=Opener()):
            with self.assertRaises(providers.ProviderHTTPError) as raised:providers.post('https://s.test','test-key',{},'gemini')
        self.assertEqual(raised.exception.code,400);self.assertNotIn('private',str(raised.exception))

    def test_provider_failures_keep_selected_model_and_unknown_reservation(self):
        exc=providers.ProviderHTTPError('gemini',400,{'category':'unsupported_schema_keyword'})
        with patch('providers.chat',side_effect=exc):result=server.chat('解释一下半导体能带')
        self.assertEqual(result['requested_model'],providers.MODELS['gemini'])
        self.assertEqual(result['diagnostic']['category'],'unsupported_schema_keyword')
        self.assertNotIn('400',result['reply']);self.assertEqual(server.budget()['reserved_cny'],.5)

    def test_old_fact_retrieved_after_more_than_ten_turns_with_source(self):
        source=server.add_message('user','我喜欢弹吉他和华语情歌')
        for i in range(30):server.add_message('user','普通消息'+str(i))
        server.init();result=server.memory_state('我喜欢什么音乐和吉他')['facts']
        self.assertTrue(any(row['source_id']==source for row in result))
        context=json.loads(server.context());self.assertTrue(any(row['source_id']==source for row in context['user_memory']))
        self.assertLessEqual(len(json.dumps(context['user_memory'],ensure_ascii=False)),persistent_memory.MAX_CONTEXT_CHARS+20)
        server.update_memory({'operation':'forget','id':result[0]['id']});server.init()
        self.assertFalse(any(row['id']==result[0]['id'] for row in server.memory_state()['facts']))

    def test_memory_is_bounded_redacted_and_ignores_assistant_claims(self):
        server.add_message('assistant','我喜欢不应保存的虚构事情')
        server.add_message('user','我的密码是 top-secret')
        with server.connect() as c:
            for i in range(300):persistent_memory.remember(c,'测试事实'+str(i),'source-'+str(i),server.now())
        self.assertEqual(len(server.memory_state()['facts']),256)
        self.assertNotIn('top-secret',persistent_memory.redact('我的密码是 top-secret'))
        self.assertNotIn('test-secret',persistent_memory.redact('Bearer test-secret'))
        self.assertFalse(any('虚构' in r['text'] for r in server.memory_state()['facts']))

    def test_explicit_remember_and_allowlisted_alias_survive_restart(self):
        result=server.chat('记住：我喜欢古典吉他');server.init()
        self.assertIn('记住',result['reply']);self.assertEqual(len(server.memory_state()['facts']),1)
        alias=server.update_memory({'operation':'learn_alias','alias':'小视频','app':'bilibili'})
        with patch('connectors.execute',return_value='已请求') as launch:
            result=server.chat('打开小视频');launch.assert_called_once()
        self.assertEqual(result['actions'][0]['status'],'requested');self.assertTrue(alias['source_id'])
        with self.assertRaises(ValueError):server.update_memory({'operation':'learn_alias','alias':'evil','app':'powershell'})

    def test_optional_routing_and_unknown_pricing(self):
        settings=server.settings();self.assertEqual(model_routing.choose('你好',settings)['provider'],'gemini')
        settings['routing_enabled']=True
        self.assertEqual(model_routing.choose('你好',settings)['provider'],'deepseek')
        self.assertEqual(model_routing.choose('请推导这个电路的输出阻抗',settings)['provider'],'gemini')
        settings['chat_models']['deepseek']='deepseek-unpriced'
        self.assertEqual(model_routing.choose('你好',settings)['reason'],'unknown_cheap_price_use_manual')
        settings['chat_models']['deepseek']=providers.PET_MODELS['deepseek']
        self.assertEqual(model_routing.choose('你好',settings)['reason'],'manual_model_lower_estimate')
        settings['provider']='local';self.assertEqual(model_routing.choose('电路证明',settings)['provider'],'local')

    def test_maps_are_local_workspace_queries_without_external_launch(self):
        fake=types.SimpleNamespace(search_places=lambda query:{'status':'ok','results':[{'name':query,'lat':22.6,'lon':114.0}]})
        with patch.dict('sys.modules',{'maps_service':fake}),patch('connectors.execute',side_effect=AssertionError('No launcher')),patch('providers.chat',side_effect=AssertionError('No model')):
            result=server.chat('打开地图');self.assertEqual(result['workspace']['type'],'map')
            result=server.chat('查找深圳北站位置');self.assertEqual(result['workspace']['query'],'深圳北站')
            self.assertEqual(result['actions'],[]);self.assertEqual(result['workspace']['search']['results'][0]['name'],'深圳北站')
            self.assertEqual(server.chat('不要打开地图')['actions'],[])
        self.assertEqual(server.budget()['requests'],0)

    def test_future_adapters_cannot_call_keys_or_network(self):
        with patch('providers.hub.load_keys',side_effect=AssertionError('No keys')):
            for provider in ('openai','claude','glm'):
                with self.assertRaises(ValueError):providers.chat(provider,[],context='test')
        self.assertEqual({x['id'] for x in providers.adapter_catalogue()['providers'] if x['enabled']},{'gemini','deepseek','openrouter'})

    def test_unknown_price_autonomous_pet_stays_free(self):
        with patch('providers.chat',side_effect=AssertionError('No model')),patch('local_runtime.status',return_value={'installed':False}):
            result=server.pet_chat({'trigger':'idle'})
        self.assertEqual(result['skipped'],'free_only');self.assertEqual(server.budget()['requests'],0)
        self.assertIsNone(providers.model_rates('gemini','gemini-3.7-flash'))

    def test_manual_budget_limit_and_settings_validation(self):
        srv=http.server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler);threading.Thread(target=srv.serve_forever,daemon=True).start()
        base=f'http://127.0.0.1:{srv.server_port}';op=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        def update(body):return json.load(op.open(urllib.request.Request(base+'/api/settings',data=json.dumps(body).encode(),method='PATCH',headers={'Content-Type':'application/json'})))
        try:
            op.open(base+'/').read();uid=server.reserve('gemini');server.settle(uid,{'estimate_cny':.3})
            result=update({'budget_limit_cny':.2,'budget_soft_alert_ratio':.5,'routing_enabled':True})
            self.assertEqual(result['budget']['remaining_cny'],0);self.assertTrue(result['budget']['soft_alert'])
            self.assertEqual(result['budget']['spent_estimate_cny'],.3);self.assertFalse(result['budget']['weekly_budget_active'])
            for body in ({'budget_limit_cny':-1},{'budget_limit_cny':True},{'routing_enabled':'true'},{'routing_cheap_provider':'claude'}):
                with self.assertRaises(urllib.error.HTTPError) as raised:update(body)
                self.assertEqual(raised.exception.code,400)
            with self.assertRaises(ValueError):server.reserve('gemini')
            before=server.budget()
            result=update({'budget_limit_cny':None})
            self.assertTrue(result['budget']['unlimited']);self.assertIsNone(result['budget']['remaining_cny'])
            self.assertEqual(result['budget']['spent_estimate_cny'],before['spent_estimate_cny'])
            self.assertEqual(result['budget']['reserved_cny'],before['reserved_cny'])
            for model in ('gemini-3.1-flash-lite','gemini-price-unknown'):
                uid=server.reserve('gemini',model);server.settle(uid,{'error_type':'test_unknown_usage'})
            self.assertTrue(server.budget()['unlimited'])
        finally:srv.shutdown();srv.server_close()

if __name__=='__main__':unittest.main()
