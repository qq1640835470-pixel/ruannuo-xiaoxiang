"""Offline checks for music commentary selection and usage accounting."""
import json,pathlib,tempfile,unittest
from unittest.mock import patch
import providers,server

class MusicCommentaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.old=(server.DATA,server.DB)
        server.DATA=pathlib.Path(self.tmp.name);server.DB=server.DATA/'test.sqlite3';server.init()

    def tearDown(self):
        server.DATA,server.DB=self.old;self.tmp.cleanup()

    def configure(self,**values):
        with server.connect() as c:
            for key,value in values.items():c.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',(key,json.dumps(value)))

    def test_uses_chat_selection_even_when_pet_and_optional_route_differ(self):
        for provider,model in (('gemini','gemini-3.7-flash'),('deepseek','deepseek-v4-pro')):
            with self.subTest(provider=provider):
                self.configure(provider=provider,chat_models={**providers.MODELS,provider:model},routing_enabled=True,pet_provider='local')
                response={'text':'这首歌让你想到什么？','model':'returned-version','usage':{'estimate_cny':.01,'requested_model':model,'purpose':'pet_chat'}}
                with patch('server.providers.chat',return_value=response) as chat,patch('server.local_runtime.status') as local:
                    result=server.music_commentary({'title':'测试歌曲','artist':'测试歌手'})
                self.assertEqual(chat.call_args.args[0],provider);self.assertEqual(chat.call_args.kwargs['model'],model)
                self.assertTrue(chat.call_args.kwargs['companion']);local.assert_not_called()
                self.assertEqual(result['model'],'returned-version');self.assertEqual(result['requested_model'],model)
                self.assertEqual(result['provider'],provider);self.assertEqual(result['source'],'cloud_model')
                with server.connect() as c:row=c.execute('SELECT * FROM usage ORDER BY rowid DESC LIMIT 1').fetchone()
                self.assertEqual(row['status'],'completed');self.assertEqual(json.loads(row['metadata'])['purpose'],'music_commentary')

    def test_cloud_disabled_and_budget_exhausted_do_not_call_model(self):
        with patch('server.providers.chat') as chat:
            self.configure(api_generation_enabled=False)
            with self.assertRaises(ValueError):server.music_commentary({'title':'测试歌曲'})
            self.configure(api_generation_enabled=True,budget_limit_cny=0)
            with self.assertRaises(ValueError):server.music_commentary({'title':'测试歌曲'})
            chat.assert_not_called()

    def test_failure_keeps_unknown_usage_and_does_not_switch_provider(self):
        with patch('server.providers.chat',side_effect=TimeoutError()) as chat:
            with self.assertRaises(ValueError):server.music_commentary({'title':'测试歌曲'})
            self.assertEqual(chat.call_count,1)
        with server.connect() as c:row=c.execute('SELECT * FROM usage').fetchone()
        self.assertEqual(row['status'],'unknown');self.assertGreater(row['reserved_cny'],0)
        self.assertEqual(json.loads(row['metadata'])['purpose'],'music_commentary')
        self.assertFalse(server.CHAT_LOCK.locked())

    def test_local_manual_selection_and_unavailable_template(self):
        self.configure(provider='local',api_generation_enabled=False)
        with patch('server.local_runtime.status',return_value={'installed':True}),patch('server.local_runtime.choose',return_value={'model':'manual-local'}),patch('server.local_models.selection',return_value='manual-local'),patch('server.providers.chat',return_value={'text':'你喜欢哪一段？','model':'manual-local','usage':{'estimate_cny':0}}) as chat:
            result=server.music_commentary({'title':'测试歌曲'})
            self.assertEqual(chat.call_args.args[0],'local');self.assertEqual(chat.call_args.kwargs['model'],'manual-local')
            self.assertEqual(result['source'],'local_model')
        with patch('server.local_runtime.status',return_value={'installed':False}),patch('server.providers.chat') as chat:
            result=server.music_commentary({'title':'测试歌曲'})
            self.assertEqual(result['source'],'local_template');self.assertIsNone(result['model']);chat.assert_not_called()

if __name__=='__main__':unittest.main()
