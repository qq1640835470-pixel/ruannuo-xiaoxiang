"""Typed local capability boundary and persistence tests; no paid requests."""
import pathlib,tempfile,unittest
from unittest.mock import patch
import local_features,server

class LocalTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.old=server.DATA,server.DB
        server.DATA=pathlib.Path(self.temp.name);server.DB=server.DATA/'assistant.sqlite3';server.init()
    def tearDown(self):server.DATA,server.DB=self.old;self.temp.cleanup()
    def test_preferences_atomic_and_reject_unknown(self):
        server.update_local_preferences({'font_scale':1.2,'motion':'gentle'})
        self.assertEqual(server.settings()['local_preferences']['font_scale'],1.2)
        for body in ({'font_scale':9},{'font_scale':True},{'shell':'delete'},{'motion':'execute'}):
            with self.assertRaises(ValueError):server.update_local_preferences(body)
        self.assertEqual(server.local_preferences()['motion'],'gentle')
    def test_model_tool_saves_without_codex_or_generated_code(self):
        result={'text':'','calls':[{'name':'configure_local','args':{'operation':'preferences','density':'compact'}}],'model':'gemini-test','usage':{'estimate_cny':.001}}
        with patch('providers.chat',return_value=result) as model,patch('feedback_bridge.send') as codex:
            reply=server.chat('把软件的布局调紧凑一点');model.assert_called_once();codex.assert_not_called()
        self.assertEqual(server.local_preferences()['density'],'compact');self.assertIn('调整',reply['reply'])
    def test_direct_preference_and_health_are_local(self):
        with patch('providers.chat') as model:
            server.chat('把字号调为1.1');server.chat('运行软件自检');model.assert_not_called()
        self.assertEqual(server.local_preferences()['font_scale'],1.1)
    def test_browser_url_boundary(self):
        self.assertEqual(local_features.browser_url('www.bilibili.com'),'https://www.bilibili.com/')
        for url in ('file:///C:/','javascript:alert(1)','http://localhost/','http://127.0.0.1/','https://user:password@example.com','http://192.168.1.1/'):
            with self.assertRaises(ValueError):local_features.browser_url(url)

if __name__=='__main__':unittest.main()
