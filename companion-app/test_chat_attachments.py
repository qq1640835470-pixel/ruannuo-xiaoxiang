"""Local synthetic attachment fixtures; no user files, model calls or external network."""
import contextlib
import base64,http.cookiejar,http.server,io,json,pathlib,sqlite3,tempfile,threading,unittest,urllib.error,urllib.request,zipfile
from unittest.mock import patch
from PIL import Image
import chat_attachments as files,chat_history,local_models,providers,server

def upload(name,raw,directory):return files.store({'name':name,'base64':base64.b64encode(raw).decode()},directory)

def png():
    stream=io.BytesIO();Image.new('RGB',(2,2),'red').save(stream,format='PNG');return stream.getvalue()

class StorageTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.directory=self.tmp.name

    def test_text_and_docx_are_extracted_and_originals_stay_local(self):
        raw='测试内容'.encode('gb18030');one=upload('说明.txt',raw,self.directory)
        item=files.load([one['id']],self.directory)[0]
        self.assertEqual(item['text'],'测试内容');self.assertEqual(files.content(item,self.directory),raw)
        self.assertNotIn('text',one);self.assertEqual(one,upload('说明.txt',raw,self.directory))
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w') as archive:archive.writestr('word/document.xml','<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Word正文</w:t></w:r></w:p></w:body></w:document>')
        doc=upload('报告.docx',stream.getvalue(),self.directory)
        self.assertEqual(files.load([doc['id']],self.directory)[0]['text'],'Word正文')

    def test_images_validate_real_format(self):
        image=upload('图片.png',png(),self.directory)
        self.assertEqual(image['kind'],'image')
        for name,data in (('spoof.jpg',png()),('broken.png',b'not an image')):
            with self.assertRaises(ValueError):upload(name,data,self.directory)

    def test_paths_types_encoding_and_lengths_are_rejected(self):
        for name,data in (('../secret.txt',b'hello'),('a\\b.txt',b'hello'),('a\n.txt',b'hello'),('run.exe',b'hello'),('scan.pdf',b'%PDF'),('data.txt',b'a\0b'),('large.txt',b'a'*5001),('empty.txt',b'')):
            with self.subTest(name=name),self.assertRaises(ValueError):upload(name,data,self.directory)
        with self.assertRaises(ValueError):files.store({'name':'a.txt','base64':'not base64'},self.directory)
        with patch.object(files,'MAX_FILE',3),self.assertRaises(ValueError):upload('a.txt',b'1234',self.directory)
        with self.assertRaises(ValueError):files.load(['../secret'],self.directory)

    def test_encrypted_or_broken_word_is_rejected(self):
        with self.assertRaises(ValueError):upload('a.docx',b'not a zip',self.directory)
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w') as archive:archive.writestr('word/document.xml','<!DOCTYPE test><document/>')
        with self.assertRaises(ValueError):upload('a.docx',stream.getvalue(),self.directory)

    def test_count_duplicates_and_missing_references(self):
        image=upload('a.png',png(),self.directory)
        for ids in ([image['id']]*2,['0'*64],['0'*64,'1'*64,'2'*64,'3'*64]):
            with self.assertRaises(ValueError):files.load(ids,self.directory)
        ids=[upload(str(i)+'.png',png(),self.directory)['id'] for i in range(3)]
        with self.assertRaises(ValueError):files.load(ids,self.directory)

class AttachmentChatTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.old=(server.DATA,server.DB)
        server.DATA=pathlib.Path(self.tmp.name);server.DB=server.DATA/'test.sqlite3';server.init()
        self.file=upload('资料.txt','仅为合成资料：测试数值42。'.encode(),server.DATA)
        self.answer={'text':'资料中的数值是42。','model':'returned-model','usage':{'estimate_cny':.01},'calls':[]}

    def tearDown(self):server.DATA,server.DB=self.old;self.tmp.cleanup()

    def test_selected_model_gets_text_without_executing_tools_and_history_has_refs(self):
        with patch.object(providers,'chat',return_value=self.answer) as model,patch.object(server,'local_chat',side_effect=AssertionError('No local command route')),patch.object(server,'tool_result',side_effect=AssertionError('No tools')):
            result=server.chat_once('帮我总结','a'*32,[self.file['id']])
        self.assertEqual(model.call_args.args[0],'gemini');self.assertFalse(model.call_args.kwargs['allow_tools'])
        self.assertEqual(model.call_args.kwargs['model'],providers.MODELS['gemini'])
        self.assertIn('42',str(model.call_args.args[1]));self.assertEqual(result['model'],'returned-model')
        with server.connect() as c:
            user=next(m for m in chat_history.page(c)['messages'] if m['role']=='user')
            usage=c.execute('SELECT metadata FROM usage').fetchone()[0]
        self.assertEqual(user['attachments'],[self.file]);self.assertNotIn('42',user['content'])
        self.assertEqual(json.loads(usage)['purpose'],'attachment_chat')

    def test_image_is_local_then_summary_goes_to_selected_model(self):
        image=upload('图.png',png(),server.DATA)
        with patch('server.local_runtime.analyze_images',return_value={'text':'合成红色图片','model':local_models.GEMMA}) as vision,patch.object(providers,'chat',return_value=self.answer) as model:
            server.chat_once('', 'b'*32,[image['id']])
        self.assertEqual(vision.call_args.args[1][0]['data'],png())
        self.assertIn('合成红色图片',str(model.call_args.args[1]));self.assertNotIn('base64',str(model.call_args.args[1]))
        self.assertEqual(model.call_args.args[0],'gemini')

    def test_receipt_covers_attachment_identity_without_replaying(self):
        other=upload('另一份.txt',b'other',server.DATA)
        with patch.object(providers,'chat',return_value=self.answer) as model:
            one=server.chat_once('总结','c'*32,[self.file['id']]);two=server.chat_once('总结','c'*32,[self.file['id']])
            self.assertEqual(one,two);self.assertEqual(model.call_count,1)
            with self.assertRaises(ValueError):server.chat_once('总结','c'*32,[other['id']])
        self.assertEqual(server.chat_receipt('c'*32)['status'],'completed')

    def test_failed_model_keeps_usage_and_unknown_receipt_without_fallback(self):
        with patch.object(providers,'chat',side_effect=TimeoutError()) as model:
            with self.assertRaises(ValueError):server.chat_once('总结','d'*32,[self.file['id']])
            self.assertTrue(server.chat_once('总结','d'*32,[self.file['id']])['pending']);self.assertEqual(model.call_count,1)
        self.assertFalse(server.CHAT_LOCK.locked())
        with server.connect() as c:usage=c.execute('SELECT status,reserved_cny FROM usage').fetchone()
        self.assertEqual(usage['status'],'unknown');self.assertGreater(usage['reserved_cny'],0)

    def test_cloud_disabled_and_context_limit_do_not_call_model(self):
        with server.connect() as c:c.execute("UPDATE settings SET value='false' WHERE key='api_generation_enabled'")
        with patch.object(providers,'chat') as model:
            with self.assertRaises(ValueError):server.chat_once('总结','e'*32,[self.file['id']])
            model.assert_not_called()
        long=upload('长.txt',('甲'*4000).encode(),server.DATA)
        with server.connect() as c:c.execute("UPDATE settings SET value='\"local\"' WHERE key='provider'")
        with patch('server.local_runtime.choose',return_value={'model':local_models.GEMMA}),patch.object(providers,'chat') as model:
            with self.assertRaises(ValueError):server.chat_once('总结','f'*32,[long['id']])
            model.assert_not_called()

    def test_attachment_mode_disables_tools_in_actual_provider_payload(self):
        response={'candidates':[{'content':{'parts':[{'text':'回答'}]}}]}
        with patch.object(providers.hub,'load_keys',return_value={'gemini':'fixture'}),patch.object(providers,'post',return_value=response) as post:
            providers.chat('gemini',[{'role':'user','content':'资料'}],'附件',allow_tools=False)
            self.assertNotIn('tools',post.call_args.args[2])
        with patch('local_runtime.chat') as local:
            providers.chat('local',[{'role':'user','content':'资料'}],'附件',allow_tools=False)
            self.assertEqual(local.call_args.kwargs['tools'],[])

    def test_old_database_migration_preserves_existing_message(self):
        path=server.DATA/'old.sqlite3'
        with contextlib.closing(sqlite3.connect(path)) as c, c:
            c.execute('CREATE TABLE messages(id TEXT PRIMARY KEY,role TEXT,content TEXT,created_at TEXT)')
            c.execute("INSERT INTO messages VALUES('old','assistant','existing','2026-10-18')")
        with patch.object(server,'DB',path):
            server.init()
            with server.connect() as c:message=chat_history.page(c)['messages'][0]
        self.assertEqual(message['content'],'existing');self.assertEqual(message['attachments'],[])

class AttachmentHttpTests(unittest.TestCase):
    def test_upload_download_and_preview_require_local_session(self):
        with tempfile.TemporaryDirectory() as d,patch.object(server,'DATA',pathlib.Path(d)),patch.object(server,'DB',pathlib.Path(d)/'db.sqlite3'):
            server.init();httpd=http.server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler);thread=threading.Thread(target=httpd.serve_forever,daemon=True);thread.start()
            try:
                base='http://127.0.0.1:'+str(httpd.server_port)
                opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
                with opener.open(base+'/') as r:r.read()
                request=urllib.request.Request(base+'/api/chat/attachments',data=json.dumps({'name':'合成.png','base64':base64.b64encode(png()).decode()}).encode(),headers={'Content-Type':'application/json'})
                with opener.open(request) as r:item=json.load(r)
                url=base+'/api/chat/attachments/'+item['id']
                with opener.open(url) as r:self.assertIn('attachment',r.headers['Content-Disposition']);self.assertEqual(r.read(),png())
                with opener.open(url+'?preview=1') as r:self.assertEqual(r.headers['Content-Type'],'image/png')
                with self.assertRaises(urllib.error.HTTPError) as denied:urllib.request.urlopen(url)
                self.assertEqual(denied.exception.code,403)
                with self.assertRaises(urllib.error.HTTPError):opener.open(urllib.request.Request(url,headers={'Origin':'https://untrusted.example'}))
                with patch.object(providers,'chat',return_value={'text':'完成','model':'fixture','usage':{'estimate_cny':0}}),patch('server.local_runtime.analyze_images',return_value={'text':'合成图片','model':'fixture'}):
                    request=urllib.request.Request(base+'/api/chat',data=json.dumps({'text':'描述','client_request_id':'9'*32,'attachment_ids':[item['id']]}).encode(),headers={'Content-Type':'application/json'})
                    with opener.open(request) as r:self.assertEqual(json.load(r)['reply'],'完成')
                with opener.open(base+'/api/state') as r:state=json.load(r)
                self.assertEqual(state['messages'][0]['attachments'],[item])
            finally:httpd.shutdown();httpd.server_close();thread.join()

if __name__=='__main__':unittest.main()
