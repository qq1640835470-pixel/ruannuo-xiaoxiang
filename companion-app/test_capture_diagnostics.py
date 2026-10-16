"""Targeted capture/source verification and metadata-only diagnostics. No paid requests."""
import json,pathlib,tempfile,unittest
from unittest.mock import patch
import server,runtime_log

class CaptureDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.old=server.DATA,server.DB
        server.DATA=pathlib.Path(self.tmp.name);server.DB=server.DATA/'app.sqlite3';server.init()
    def tearDown(self):
        server.DATA,server.DB=self.old;self.tmp.cleanup()
    def test_same_model_call_captures_verified_source_without_codex(self):
        raw='字体现在太小了，希望稍微大一些，其他布局保持。'
        response={'text':'我明白了。','model':'gemini-test','usage':{'estimate_cny':.001},'calls':[{'name':'capture_feedback','args':{'title':'调整字号','summary':'适当增大字体，保持现有布局。','source_quote':raw}}]}
        with patch('providers.chat',return_value=response) as model,patch('feedback_bridge.send') as codex:
            result=server.chat(raw);model.assert_called_once();codex.assert_not_called()
        draft=result['feedback_drafts'][0];self.assertEqual(draft['raw_text'],raw);self.assertEqual(draft['status'],'pending')
        self.assertEqual(len(server.list_feedback_drafts()),1)
        server.capture_ai_feedback({'title':'调整字号','summary':draft['summary']},raw,draft['source_id'],'gemini','gemini-test')
        self.assertEqual(len(server.list_feedback_drafts()),1)
        with server.connect() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM feedback_delivery').fetchone()[0],0)
        self.assertNotIn(raw,json.dumps(runtime_log.recent(),ensure_ascii=False))
    def test_prefix_saves_locally_without_generation_and_refuses_negation(self):
        with server.connect() as c:c.execute("UPDATE settings SET value='false' WHERE key='api_generation_enabled'")
        with patch('providers.chat') as model,patch('feedback_bridge.send') as codex:
            result=server.chat('反馈：按钮太挤了');model.assert_not_called();codex.assert_not_called()
        self.assertEqual(result['feedback_drafts'][0]['provider'],'local')
        with self.assertRaises(ValueError):server.capture_ai_feedback({'title':'x','summary':'x'},'不要保存这条反馈','source','local','none')
    def test_recent_quote_must_be_exact_and_queued_needs_receipt(self):
        original=server.add_message('user','我希望摸头时能有音效。')
        draft=server.capture_ai_feedback({'title':'摸头音效','summary':'增加摸头音效。','source_quote':'我希望摸头时能有音效。'},'记录刚才的要求','new-source','gemini','gemini-test')
        self.assertEqual(draft['source_id'],original)
        with self.assertRaises(ValueError):server.update_feedback_draft(draft['id'],{'status':'queued','delivery_id':'a'*32})
        server.update_feedback_draft(draft['id'],{'status':'dismissed'});self.assertEqual(server.list_feedback_drafts(),[])
    def test_logs_drop_payloads_and_exceptions_keep_only_frames(self):
        secret='sk-'+'a'*32
        runtime_log.event('test',provider='gemini',headers={'Authorization':secret},body='private-chat',returned_model=secret,route='/api/state?key='+secret)
        try:raise ValueError('password=never-log-this')
        except ValueError as exc:runtime_log.error('test_error',exc)
        log=(server.DATA/'logs'/'runtime.jsonl').read_text(encoding='utf-8')
        for value in (secret,'private-chat','never-log-this','Authorization'):self.assertNotIn(value,log)
        events=runtime_log.recent();self.assertEqual(events[-1]['error_type'],'ValueError');self.assertTrue(events[-1]['frames'])
    def test_logging_rotates_bounded_files(self):
        with patch.object(runtime_log,'MAX_BYTES',300):
            for _ in range(20):runtime_log.event('rotation',status='ok')
        files=list((server.DATA/'logs').glob('runtime.jsonl*'));self.assertLessEqual(len(files),4)
        self.assertTrue(runtime_log.recent())

if __name__=='__main__':unittest.main()
