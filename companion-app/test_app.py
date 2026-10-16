"""Targeted checks for persistent budget, local boundaries and typed tool actions. No paid requests."""
import http.cookiejar, http.server, json, pathlib, tempfile, threading, unittest, urllib.error, urllib.request
from unittest.mock import patch
import connectors, server

class AppTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.old=(server.DATA,server.DB)
        server.DATA=pathlib.Path(self.tmp.name);server.DB=server.DATA/'test.sqlite3';server.init()
    def tearDown(self):
        server.DATA,server.DB=self.old;self.tmp.cleanup()
    def test_budget_persists_and_blocks(self):
        ids=[server.reserve('gemini') for _ in range(20)]
        with self.assertRaises(ValueError):server.reserve('gemini')
        server.init();self.assertEqual(server.budget()['remaining_cny'],0)
        server.settle(ids[0],{'estimate_cny':.012})
        self.assertAlmostEqual(server.budget()['remaining_cny'],.488)
        server.settle(ids[1]);self.assertEqual(server.budget()['reserved_cny'],9.5)
    def test_task_and_model_tool_validation(self):
        r=server.tool_result({'name':'create_task','args':{'title':'测试任务'}})
        self.assertIn('测试任务',r[0]);self.assertEqual(len(server.list_tasks()),1)
        with self.assertRaises(ValueError):server.tool_result({'name':'shell','args':{'command':'whoami'}})
        with self.assertRaises(ValueError):connectors.prepare({'kind':'open_service','app':'https://attacker.test'})
        with self.assertRaises(ValueError):server.add_task({'title':'测试','scheduled_at':'坏日期'})
    def test_map_query_encoding(self):
        a=connectors.prepare({'kind':'map_search','app':'baidu','query':'深圳大学 &学校'})
        self.assertIn('%26',a['payload']['url']);self.assertNotIn('&学校',a['payload']['url'])
    def test_local_commands_no_model_or_message_send(self):
        with patch('providers.chat',side_effect=AssertionError('No generation expected')),patch('connectors.execute',return_value='已请求打开微信') as launch:
            r=server.chat('打开微信');self.assertEqual(r['provider'],'local');self.assertEqual(r['actions'][0]['status'],'requested');self.assertTrue(r['actions'][0]['auto_executed'])
            launch.assert_called_once()
            r=server.chat('在QQ群聊发送你好');self.assertEqual(r['actions'],[]);self.assertIn('没有被读取或发送',r['reply'])
        self.assertEqual(server.budget()['requests'],0)
    def test_auto_open_no_replay_or_negated_requests(self):
        with patch('connectors.execute',return_value='已请求打开') as launch:
            r=server.chat('请帮我打开QQ')
            with self.assertRaises(ValueError):server.execute_action(r['actions'][0]['id'])
            self.assertEqual(launch.call_count,1)
            self.assertEqual(server.local_chat('不要打开QQ')['actions'],[])
            self.assertFalse(server.explicit_open_request('我在考虑打开QQ这个功能'))
            self.assertFalse(server.explicit_open_request('帮我解释“打开QQ”这个例子'))
            draft=server.save_action(connectors.prepare({'kind':'prepare_message','app':'qq','text':'测试草稿'}))
            server.auto_open({'actions':[draft]},'打开QQ')
            self.assertEqual(draft['status'],'prepared');self.assertEqual(launch.call_count,1)
    def test_model_action_uses_same_auto_execution(self):
        with patch('connectors.execute',return_value='已请求打开') as launch:
            reply,actions=server.tool_result({'name':'prepare_action','args':{'kind':'open_app','app':'notepad'}})
            result=server.auto_open({'reply':reply,'actions':actions},'帮我把记事本打开')
            self.assertEqual(result['actions'][0]['status'],'requested');launch.assert_called_once()
        with patch('connectors.execute',side_effect=OSError('test')):
            result=server.chat('打开记事本');self.assertEqual(result['actions'][0]['status'],'failed')
    def test_http_origin_cookie_and_persistence(self):
        srv=http.server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        thread=threading.Thread(target=srv.serve_forever,daemon=True);thread.start()
        base=f'http://127.0.0.1:{srv.server_port}'
        jar=http.cookiejar.CookieJar();op=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        try:
            op.open(base+'/').read()
            with self.assertRaises(urllib.error.HTTPError) as cm:
                op.open(urllib.request.Request(base+'/api/tasks',data=b'{"title":"x"}',headers={'Content-Type':'application/json','Origin':'https://attacker.test'}))
            self.assertEqual(cm.exception.code,403)
            req=urllib.request.Request(base+'/api/tasks',data=json.dumps({'title':'持久化测试'}).encode(),headers={'Content-Type':'application/json'})
            task=json.load(op.open(req));self.assertTrue(task['id'])
            with patch('connectors.execute',return_value='系统请求回执') as launch:
                server.chat('打开QQ')
                server.chat('记下：验收测试')
                server.init()
                state=json.load(op.open(base+'/api/state'))
                json.load(op.open(base+'/api/state'))
                launch.assert_called_once()
            self.assertTrue(any(t['title']=='持久化测试' for t in state['tasks']))
            self.assertIn('已保存到本机',state['messages'][-1]['execution'][0]['result'])
            operation=next(m for m in state['messages'] if m['role']=='assistant' and m['actions'])
            self.assertNotIn('系统请求回执',operation['display_content'])
            self.assertEqual(operation['actions'][0]['result'],'系统请求回执')
            with self.assertRaises(urllib.error.HTTPError):urllib.request.urlopen(base+'/api/state')
            with self.assertRaises(urllib.error.HTTPError):op.open(urllib.request.Request(base+'/api/state',headers={'Host':'attacker.test'}))
        finally:srv.shutdown();srv.server_close()

    def test_failure_prose_and_technical_record_stay_separate(self):
        with patch('connectors.execute',side_effect=OSError('private diagnostic')):
            result=server.chat('打开QQ')
        self.assertEqual(result['actions'][0]['status'],'failed')
        self.assertIn('没能',result['reply']);self.assertNotIn('private diagnostic',str(result))
        with patch('providers.chat',side_effect=urllib.error.HTTPError('https://example.test',429,'quota',{},None)):
            result=server.chat('和我聊聊吉他吧')
        self.assertNotIn('HTTP',result['reply'])
        self.assertIn('HTTP 429',result['execution'][0]['result'])
        self.assertEqual(server.budget()['reserved_cny'],.5)
        with server.connect() as c:message=dict(c.execute("SELECT * FROM messages WHERE role='assistant' ORDER BY rowid DESC LIMIT 1").fetchone())
        self.assertEqual(json.loads(message['execution']),result['execution'])

    def test_pet_dialogue_has_no_actions_and_persistent_limits(self):
        response={'text':'这里的风景倒不错。陪我聊一首喜欢的歌吧？','model':'returned-test-model',
                  'calls':[{'name':'create_task','args':{'title':'must not run'}}],
                  'usage':{'estimate_cny':.02,'requested_model':'requested-test-model','returned_model':'returned-test-model'}}
        with patch('providers.chat',return_value=response) as model:
            result=server.pet_chat({'trigger':'manual','pose':'hang'})
            self.assertEqual(result['model'],'returned-test-model');self.assertIn('风景',result['text'])
            self.assertTrue(model.call_args.kwargs['companion']);self.assertEqual(server.list_tasks(),[])
            self.assertEqual(server.budget()['requests'],1)
            server.init();self.assertEqual(server.pet_chat({'trigger':'idle','pose':'sit'})['skipped'],'cooldown')
            self.assertEqual(model.call_count,1)
        with server.connect() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM messages').fetchone()[0],0)

    def test_pet_failure_no_retry_and_disabled_no_spend(self):
        with patch('providers.chat',side_effect=OSError('private failure')) as model:
            result=server.pet_chat({'trigger':'manual','pose':'sit'})
            self.assertTrue(result['error']);self.assertNotIn('private failure',str(result))
            self.assertEqual(server.pet_chat({'trigger':'manual'})['skipped'],'cooldown')
            self.assertEqual(model.call_count,1);self.assertEqual(server.budget()['reserved_cny'],server.providers.reservation('gemini',server.providers.PET_MODELS['gemini'],10))
        with server.connect() as c:c.execute("UPDATE settings SET value='false' WHERE key='pet_ai_enabled'")
        with patch('providers.chat',side_effect=AssertionError('disabled')):
            self.assertEqual(server.pet_chat({})['skipped'],'disabled')
        with self.assertRaises(ValueError):server.pet_chat({'pose':'invalid'})

    def test_pet_provider_payload_contains_no_tools(self):
        import providers
        fixtures={'gemini':{'candidates':[{'content':{'parts':[{'text':'你好'}]}}],'usageMetadata':{'promptTokenCount':10,'candidatesTokenCount':5},'modelVersion':'gemini-3.8-flash'},
                  'deepseek':{'choices':[{'message':{'content':'你好'}}],'usage':{'prompt_tokens':10,'completion_tokens':5},'model':'deepseek-v4-pro'}}
        for provider in fixtures:
            with patch.object(providers.hub,'load_keys',return_value={provider:'test-only'}),patch.object(providers,'post',return_value=fixtures[provider]) as post:
                result=providers.chat(provider,[{'role':'user','content':'陪我聊一句'}],'ordinary context',companion=True)
                body=post.call_args.args[2];self.assertNotIn('tools',body)
                self.assertEqual(result['usage']['requested_model'],providers.PET_MODELS[provider])
                if providers.model_rates(provider,providers.PET_MODELS[provider]):self.assertIn('estimate_cny',result['usage'])
                else:self.assertNotIn('estimate_cny',result['usage'])

    def test_feedback_bridge_queue_idempotency_and_restart(self):
        import uuid
        fid=uuid.uuid4().hex
        with patch('server.threading.Thread') as thread,patch('feedback_bridge.send',return_value={'status':'queued','detail':'accepted by queue'}) as send:
            thread.return_value.start.side_effect=lambda:thread.call_args.kwargs['target']()
            result=server.submit_feedback({'id':fid,'content':'界面颜色反馈'})
            self.assertEqual(result['status'],'queued')
            self.assertEqual(server.submit_feedback({'id':fid,'content':'duplicate'})['status'],'queued');send.assert_called_once()
            with server.connect() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM feedback').fetchone()[0],1)
        with server.connect() as c:c.execute("UPDATE feedback_delivery SET status='sending' WHERE id=?",(fid,))
        server.init();self.assertEqual(server.feedback_status(fid)['status'],'unknown')
        with self.assertRaises(ValueError):server.submit_feedback({'id':'bad','content':'x'})

    def test_feedback_cli_is_exact_thread_no_shell_and_timeout_is_unknown(self):
        import feedback_bridge,subprocess,types
        with patch('feedback_bridge.executable',return_value='codex.exe'),patch('feedback_bridge.subprocess.run',return_value=types.SimpleNamespace(returncode=0)) as run:
            result=feedback_bridge.send('a; $(not a command)','abc')
            self.assertEqual(result['status'],'queued');args=run.call_args.args[0]
            self.assertEqual(args[1:4],['queue','--thread',feedback_bridge.THREAD_ID]);self.assertIn('$(not a command)',args[-1]);self.assertNotIn('shell',run.call_args.kwargs)
        with patch('feedback_bridge.executable',return_value='codex.exe'),patch('feedback_bridge.subprocess.run',side_effect=subprocess.TimeoutExpired('codex',20)):
            self.assertEqual(feedback_bridge.send('test','abc')['status'],'unknown')
        with patch('feedback_bridge.executable',return_value=None):self.assertEqual(feedback_bridge.send('test','abc')['status'],'failed')

    def test_current_time_in_both_main_context_and_pet_context(self):
        with patch('server.now',return_value='2026-10-16T23:59:59+08:00'):
            self.assertEqual(server.time_context()['phase'],'夜晚');self.assertIn('23:59:59',server.context())
        with patch('server.now',return_value='2026-10-17T00:00:00+08:00'):self.assertEqual(server.time_context()['phase'],'深夜')

if __name__=='__main__':unittest.main()
