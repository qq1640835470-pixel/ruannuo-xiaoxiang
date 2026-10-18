"""Target binding and receipts with simulated queue execution; never send real messages."""
import http.cookiejar,http.server,json,pathlib,tempfile,threading,types,unittest,urllib.request
from unittest.mock import patch
import feedback_bridge as bridge,server

A='11111111-1111-4111-8111-111111111111'
B='22222222-2222-4222-8222-222222222222'

class FeedbackTargetTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.old=(server.DATA,server.DB)
        server.DATA=pathlib.Path(self.tmp.name);server.DB=server.DATA/'db.sqlite3';server.init()
    def tearDown(self):server.DATA,server.DB=self.old;self.tmp.cleanup()
    def configure(self,ident=A):return bridge.configure({'thread_id':ident,'label':ident[0],'enabled':True},server.DATA)

    def test_no_legacy_fallback_and_configuration_validation(self):
        self.assertFalse(bridge.status(server.DATA)['configured'])
        with patch('feedback_bridge.subprocess.run') as run:
            self.assertEqual(bridge.send('text','id')['status'],'failed');run.assert_not_called()
        for body in ({'thread_id':'bad','enabled':True},{'thread_id':A,'label':'x\ny'},{'enabled':True}):
            with self.assertRaises(ValueError):bridge.configure(body,server.DATA)
        self.configure();self.assertEqual(bridge.status(server.DATA)['thread_id'],A)

    def test_target_snapshot_survives_configuration_change_during_delivery(self):
        self.configure()
        with patch('server.threading.Thread') as thread,patch.object(bridge,'send',return_value={'status':'queued','detail':'accepted'}) as send:
            first=server.submit_feedback({'id':'a'*32,'content':'合成反馈','target_thread_id':A})
            self.assertEqual(first['status'],'sending');self.configure(B)
            thread.call_args.kwargs['target']()
            self.assertEqual(send.call_args.args[2]['thread_id'],A)
        receipt=server.feedback_status('a'*32);self.assertEqual(receipt['target_thread_id'],A)
        self.assertEqual(receipt['status'],'queued')
        self.assertEqual(server.submit_feedback({'id':'a'*32,'content':'same id','target_thread_id':B})['target_thread_id'],A)

    def test_stale_or_disabled_target_preserves_feedback_without_sending(self):
        self.configure(B)
        with patch('server.threading.Thread') as thread,patch.object(bridge,'send') as send:
            result=server.submit_feedback({'id':'b'*32,'content':'保留合成反馈','target_thread_id':A})
            self.assertEqual(result['status'],'failed');thread.assert_not_called();send.assert_not_called()
        with server.connect() as c:self.assertEqual(c.execute('SELECT content FROM feedback').fetchone()[0],'保留合成反馈')

    def test_queue_arguments_use_configured_uuid_and_never_shell(self):
        target=self.configure(B)
        with patch.object(bridge,'executable',return_value='codex.exe'),patch.object(bridge.subprocess,'run',return_value=types.SimpleNamespace(returncode=0)) as run:
            result=bridge.send('a; $(literal)','id',target)
        self.assertEqual(run.call_args.args[0][1:4],['queue','--thread',B]);self.assertNotIn('shell',run.call_args.kwargs)
        self.assertIn(B,result['detail']);self.assertIn('排队成功不表示已经阅读',result['detail'])

    def test_http_settings_and_test_submission_have_target_receipt(self):
        httpd=http.server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler);worker=threading.Thread(target=httpd.serve_forever,daemon=True);worker.start()
        try:
            base='http://127.0.0.1:'+str(httpd.server_port)
            opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
            with opener.open(base+'/') as response:response.read()
            request=urllib.request.Request(base+'/api/feedback-target',method='PATCH',data=json.dumps({'thread_id':B,'label':'fixture','enabled':True}).encode(),headers={'Content-Type':'application/json'})
            with opener.open(request) as response:self.assertEqual(json.load(response)['thread_id'],B)
            with patch.object(bridge,'send',return_value={'status':'queued','detail':'fixture queue'}) as send:
                for _ in range(2):
                    request=urllib.request.Request(base+'/api/feedback/test',data=json.dumps({'id':'c'*32,'target_thread_id':B,'content':'not the test message'}).encode(),headers={'Content-Type':'application/json'})
                    with opener.open(request) as response:result=json.load(response)
                for _ in range(100):
                    if server.feedback_status('c'*32)['status']!='sending':break
                    import time;time.sleep(.01)
                self.assertEqual(send.call_count,1);self.assertIn('通道测试',send.call_args.args[0])
            with opener.open(base+'/api/feedback/'+'c'*32) as response:receipt=json.load(response)
            self.assertEqual(receipt['target_thread_id'],B);self.assertEqual(receipt['kind'],'test')
            self.assertEqual(receipt['status'],'queued')
        finally:httpd.shutdown();httpd.server_close();worker.join()

if __name__=='__main__':unittest.main()
