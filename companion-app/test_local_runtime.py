import hashlib,http.server,json,pathlib,tempfile,threading,unittest
from unittest.mock import patch
import local_runtime,local_runtime_setup as setup

class DownloadTests(unittest.TestCase):
    def setUp(self):
        self.content=b'GGUF fixture official-file-content';self.requests=[]
        owner=self
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                value=self.headers.get('Range');owner.requests.append(value);offset=int(value[6:-1]) if value else 0
                self.send_response(206 if value else 200)
                if value:self.send_header('Content-Range',f'bytes {offset}-{len(owner.content)-1}/{len(owner.content)}')
                self.end_headers();self.wfile.write(owner.content[offset:])
            def log_message(self,*args):pass
        self.server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler);self.worker=threading.Thread(target=self.server.serve_forever,daemon=True);self.worker.start()
        self.temp=tempfile.TemporaryDirectory();self.file=pathlib.Path(self.temp.name)/'model.gguf';self.url=f'http://127.0.0.1:{self.server.server_port}/file';self.digest=hashlib.sha256(self.content).hexdigest()
    def tearDown(self):self.server.shutdown();self.server.server_close();self.temp.cleanup()
    def test_resume_exact_range_and_hash(self):
        self.file.with_suffix('.gguf.part').write_bytes(self.content[:5])
        setup.download(self.url,self.file,len(self.content),self.digest)
        self.assertEqual(self.requests,['bytes=5-']);self.assertEqual(self.file.read_bytes(),self.content)
        setup.download(self.url,self.file,len(self.content),self.digest);self.assertEqual(len(self.requests),1)
    def test_mismatched_hash_never_installs(self):
        with self.assertRaises(ValueError):setup.download(self.url,self.file,len(self.content),'0'*64)
        self.assertFalse(self.file.exists());self.assertTrue(self.file.with_suffix('.gguf.part').exists())
    def test_rejects_zip_path_escape(self):
        import zipfile
        archive=pathlib.Path(self.temp.name)/'runtime.zip'
        with zipfile.ZipFile(archive,'w') as z:z.writestr('../escape','bad')
        with self.assertRaises(ValueError):setup.extract_verified(archive,pathlib.Path(self.temp.name)/'runtime')

class ReleaseTests(unittest.TestCase):
    def test_runtime_uses_binary_separate_cuda_dependencies_and_cpu(self):
        names=['cudart-llama-bin-win-cuda-12.4-x64.zip','llama-b123-bin-win-cuda-12.4-x64.zip','llama-b123-bin-win-cpu-x64.zip']
        releases=[{'tag_name':'v0.7.0','assets':[]},{'tag_name':'b123','assets':[{'name':n} for n in names]}]
        with patch('local_runtime_setup.metadata',return_value=releases),patch('local_runtime_setup.detected_cuda',return_value=(13,4)):tag,assets=setup.runtime_release()
        self.assertEqual(tag,'b123');self.assertEqual(assets[0]['name'],names[1]);self.assertEqual(len(assets),3)
    def test_prefers_supported_modern_cuda_and_cpu_if_no_driver(self):
        names=['llama-b123-bin-win-cuda-12.4-x64.zip','llama-b123-bin-win-cuda-13.4-x64.zip','cudart-llama-bin-win-cuda-13.4-x64.zip','llama-b123-bin-win-cpu-x64.zip']
        releases=[{'tag_name':'b123','assets':[{'name':n} for n in names]}]
        with patch('local_runtime_setup.metadata',return_value=releases),patch('local_runtime_setup.detected_cuda',return_value=(13,4)):
            self.assertIn('13.4',setup.runtime_release()[1][0]['name'])
        with patch('local_runtime_setup.metadata',return_value=releases),patch('local_runtime_setup.detected_cuda',return_value=None):
            self.assertEqual([a['name'] for a in setup.runtime_release()[1]],[names[3]])
    def test_cpu_release_is_supported_without_cuda(self):
        releases=[{'tag_name':'b123','assets':[{'name':'llama-b123-bin-win-cpu-x64.zip'}]}]
        with patch('local_runtime_setup.metadata',return_value=releases),patch('local_runtime_setup.detected_cuda',return_value=(13,4)):tag,assets=setup.runtime_release()
        self.assertEqual(len(assets),1);self.assertIn('cpu',assets[0]['name'])

class AdapterTests(unittest.TestCase):
    def test_no_install_reports_honestly(self):
        with tempfile.TemporaryDirectory() as d,patch.object(setup,'BASE',pathlib.Path(d)):
            self.assertFalse(local_runtime.status()['installed']);self.assertFalse(local_runtime.status()['ready'])
            with self.assertRaises(ValueError):local_runtime.ensure_ready()
    def result(self,message):return {'choices':[{'message':message}],'usage':{'prompt_tokens':10,'completion_tokens':5},'model':local_runtime.MODEL}
    def test_non_thinking_local_chat_no_cloud_and_redaction(self):
        with patch('local_runtime.ensure_ready'),patch('local_runtime._request',return_value=self.result({'content':'你好'})) as request:
            result=local_runtime.chat([{'role':'user','content':'你好 sk-1234567890example'}],'当前时段：下午',companion=True)
        body=request.call_args.args[1]
        self.assertFalse(body['chat_template_kwargs']['enable_thinking']);self.assertNotIn('tools',body)
        self.assertNotIn('sk-1234567890example',json.dumps(body));self.assertIn('当前时段',body['messages'][0]['content'])
        self.assertEqual(result['usage']['estimate_cny'],0);self.assertEqual(result['calls'],[])
    def test_structured_tools_only_parse_never_execute(self):
        tool={'name':'weather','description':'weather','parameters':{'type':'object','properties':{'location':{'type':'string'}}}}
        message={'content':None,'tool_calls':[{'function':{'name':'weather','arguments':'{"location":"深圳"}'}}]}
        with patch('local_runtime.ensure_ready'),patch('local_runtime._request',return_value=self.result(message)):
            result=local_runtime.chat([{'role':'user','content':'深圳天气'}],'',tools=[tool])
        self.assertEqual(result['calls'],[{'name':'weather','args':{'location':'深圳'}}]);self.assertEqual(result['text'],'')
        message['tool_calls'][0]['function']['name']='shell'
        with patch('local_runtime.ensure_ready'),patch('local_runtime._request',return_value=self.result(message)),self.assertRaises(ValueError):
            local_runtime.chat([{'role':'user','content':'你好'}],'',tools=[tool])
    def test_text_tool_markup_cannot_claim_execution(self):
        with patch('local_runtime.ensure_ready'),patch('local_runtime._request',return_value=self.result({'content':'<tool_call>{}</tool_call>'})),self.assertRaises(ValueError):
            local_runtime.chat([{'role':'user','content':'调用工具'}],'')
    def test_no_cloud_retry_after_local_failure(self):
        with patch('local_runtime.ensure_ready'),patch('local_runtime._request',side_effect=OSError),self.assertRaisesRegex(ValueError,'未自动调用云端'):
            local_runtime.chat([{'role':'user','content':'你好'}],'')
if __name__=='__main__':unittest.main()
