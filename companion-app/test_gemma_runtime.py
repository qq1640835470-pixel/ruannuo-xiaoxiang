import json,pathlib,tempfile,time,unittest
from unittest.mock import Mock,patch
import local_models as models,local_runtime as runtime,local_runtime_setup as setup


class GemmaTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=pathlib.Path(self.temp.name)
        self.data=patch('app_paths.DATA',self.path);self.data.start()
    def tearDown(self):self.data.stop();self.temp.cleanup()
    def result(self):return {'choices':[{'message':{'content':'红色方块'}}],'model':models.GEMMA,'usage':{'prompt_tokens':300,'completion_tokens':5}}
    def test_auto_stays_qwen_even_with_gemma_active(self):
        with patch('local_models.installed',return_value=True):
            for text in ('你好','请推导这个积分'):
                self.assertIn(models.choose(text,active=models.GEMMA,last_used=time.monotonic())['model'],(models.SMALL,models.LARGE))
            models.select(models.GEMMA)
            self.assertEqual(models.choose('请推导这个积分')['model'],models.GEMMA)
    def test_gemma_install_requires_both_verified_assets(self):
        model={'file':'gemma/test.gguf','size':4,'sha256':'a'};projector={'file':'gemma/mmproj.gguf','size':4,'sha256':'b'}
        with patch.object(setup,'BASE',self.path),patch.object(models,'assets',return_value=[model,projector]):
            for asset in (model,projector):
                path=self.path/asset['file'];path.parent.mkdir(exist_ok=True);path.write_bytes(b'GGUF')
                path.with_suffix('.gguf.download.json').write_text(json.dumps({'state':'verified','sha256':asset['sha256']}))
            self.assertTrue(models.installed(models.GEMMA))
            (self.path/projector['file']).unlink()
            self.assertFalse(models.installed(models.GEMMA))
    def test_cpu_launch_gemma_has_projector_and_qwen_does_not(self):
        executable=self.path/'llama-server.exe';executable.touch();process=Mock();process.poll.return_value=None
        config={'executable':str(executable),'backend':'cpu','verified':True}
        for model in (models.GEMMA,models.SMALL):
            with patch.object(setup,'BASE',self.path),patch('local_models.installed',return_value=True),patch('local_runtime._configuration',return_value=config),patch('local_runtime._PROCESS',None),patch('local_runtime._ACTIVE_MODEL',None),patch('local_runtime._healthy',return_value=True),patch('local_runtime.subprocess.Popen',return_value=process) as launch:
                runtime.ensure_ready(model);command=launch.call_args.args[0]
                if model==models.GEMMA:
                    self.assertIn('--mmproj',command);self.assertIn('--no-mmproj-offload',command)
                    self.assertEqual(command[command.index('-c')+1],'8192');self.assertNotIn('--reasoning',command)
                    self.assertGreaterEqual(int(command[command.index('-ub')+1]),256)
                else:
                    self.assertNotIn('--mmproj',command);self.assertNotIn('--image-max-tokens',command)
                    self.assertEqual(command[command.index('-c')+1],'16384');self.assertIn('--reasoning',command)
    def test_gpu_budget_accounts_for_projector(self):
        with patch('local_models.subprocess.run',return_value=Mock(stdout='2000\n')):
            self.assertEqual(models.gpu_layers(models.GEMMA),0)
        with patch('local_models.subprocess.run',return_value=Mock(stdout='11000\n')):
            self.assertEqual(models.gpu_layers(models.GEMMA),35)
    def test_gemma_text_never_claims_native_tools(self):
        with patch('local_runtime.ensure_ready'),patch('local_runtime._request',return_value=self.result()) as request:
            result=runtime.chat([{'role':'user','content':'你好'}],'',model=models.GEMMA,tools=[{'name':'weather'}])
        body=request.call_args.args[1]
        self.assertNotIn('tools',body);self.assertNotIn('chat_template_kwargs',body)
        self.assertNotIn('/no_think',body['messages'][0]['content']);self.assertFalse(result['usage']['tools_enabled'])
    def test_manual_models_do_not_enter_qwen_retry_chain(self):
        for model in (models.GEMMA,models.SMALL):
            with patch('local_models.installed',return_value=True),patch('local_runtime._chat_once',side_effect=ValueError('本地模型返回空回复。')) as infer,self.assertRaises(ValueError):
                runtime.chat([{'role':'user','content':'你好'}],'',model=model)
            self.assertEqual(infer.call_count,1)
    def test_image_payload_is_embedded_loopback_and_selection_unchanged(self):
        with patch('local_runtime.ensure_ready'),patch('local_runtime._request',return_value=self.result()) as request:
            result=runtime.analyze_images('描述颜色',[{'data':b'\x89PNG\r\n\x1a\nfixture','mime_type':'image/png'}])
        body=request.call_args.args[1];parts=body['messages'][-1]['content']
        self.assertTrue(parts[1]['image_url']['url'].startswith('data:image/png;base64,'))
        self.assertNotIn('tools',body);self.assertEqual(result['calls'],[]);self.assertEqual(models.selection(),'auto')
        self.assertEqual(result['usage']['purpose'],'image_analysis')
    def test_images_refuse_remote_urls_paths_and_mismatched_mime_before_start(self):
        with patch('local_runtime.ensure_ready') as ready:
            for images in (['C:/private.png'],[{'data':'https://example.com/image.png','mime_type':'image/png'}],[{'data':b'not an image','mime_type':'image/png'}],[]):
                with self.assertRaises(ValueError):runtime.analyze_images('描述',images)
            ready.assert_not_called()


if __name__=='__main__':unittest.main()
