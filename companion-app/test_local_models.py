import json,pathlib,tempfile,time,unittest
from unittest.mock import patch,Mock
import local_models as models,local_runtime as runtime

class LocalRoutingTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=pathlib.Path(self.tmp.name)
        self.data=patch('app_paths.DATA',self.path);self.data.start()
        self.available=patch('local_models.installed',return_value=True);self.available.start()
    def tearDown(self):self.available.stop();self.data.stop();self.tmp.cleanup()
    def test_simple_and_complex_without_router_model_call(self):
        self.assertEqual(models.choose('你好呀')['model'],models.SMALL)
        self.assertEqual(models.choose('请逐步推导矩阵的特征值并检查代码')['model'],models.LARGE)
        self.assertEqual(models.choose('今天想听什么歌',companion=True)['model'],models.SMALL)
    def test_manual_selection_persists_and_beats_complexity(self):
        models.select(models.SMALL)
        self.assertEqual(models.choose('推导积分')['model'],models.SMALL)
        models.select(models.LARGE)
        self.assertEqual(models.choose('你好')['model'],models.LARGE)
        self.assertEqual(json.loads((self.path/'local-model-selection.json').read_text())['model'],models.LARGE)
    def test_recent_8b_stays_warm_then_returns_to_4b(self):
        self.assertEqual(models.choose('好的',active=models.LARGE,last_used=time.monotonic())['model'],models.LARGE)
        self.assertEqual(models.choose('好的',active=models.LARGE,last_used=time.monotonic()-181)['model'],models.SMALL)
    def test_contextual_followup_uses_8b(self):
        history=[{'role':'user','content':'推导这道电路题'},{'role':'assistant','content':'先列方程'},{'role':'user','content':'继续'}]
        self.assertEqual(models.choose('继续',history=history)['model'],models.LARGE)
    def test_missing_preferred_uses_installed_and_manual_refuses(self):
        with patch('local_models.installed',side_effect=lambda ident:ident==models.SMALL):
            route=models.choose('推导积分');self.assertEqual(route['model'],models.SMALL);self.assertEqual(route['reason'],'preferred_model_unavailable')
            with self.assertRaises(ValueError):models.select(models.LARGE)
    def test_model_selection_rejects_unknown(self):
        with self.assertRaises(ValueError):models.select('../../other.gguf')
    def test_gpu_plan_leaves_headroom(self):
        with patch('local_models.subprocess.run',return_value=Mock(stdout='4594\n')):
            layers=models.gpu_layers(models.LARGE);self.assertGreater(layers,0);self.assertLess(layers,33)
        with patch('local_models.subprocess.run',return_value=Mock(stdout='700\n')):self.assertEqual(models.gpu_layers(models.LARGE),0)
    def test_invalid_4b_format_upgrades_once_before_any_tool_execution(self):
        answer={'model':models.LARGE,'usage':{},'calls':[],'text':'ok'}
        with patch('local_runtime._chat_once',side_effect=[ValueError('本地模型未生成可解析的结构化工具调用，未执行。'),answer]) as infer:
            result=runtime.chat([{'role':'user','content':'你好'}],'')
            self.assertEqual(infer.call_count,2);self.assertEqual(result['usage']['local_routing']['attempts'],[models.SMALL,models.LARGE])
        models.select(models.SMALL)
        with patch('local_runtime._chat_once',side_effect=ValueError('本地模型返回空回复。')) as infer,self.assertRaises(ValueError):
            runtime.chat([{'role':'user','content':'你好'}],'')
        self.assertEqual(infer.call_count,1)
    def test_health_cannot_accept_other_loaded_model(self):
        with patch('local_runtime._request',side_effect=[{'status':'ok'},{'data':[{'id':models.SMALL}]}]):
            self.assertFalse(runtime._healthy(model=models.LARGE))
    def test_actual_launch_selects_model_path_and_alias(self):
        executable=self.path/'llama-server.exe';executable.touch();process=Mock();process.poll.return_value=None
        config={'executable':str(executable),'backend':'cpu','verified':True}
        with patch('local_runtime.setup.BASE',self.path),patch('local_runtime._configuration',return_value=config),patch('local_runtime._PROCESS',None),patch('local_runtime._ACTIVE_MODEL',None),patch('local_runtime._healthy',return_value=True),patch('local_runtime.subprocess.Popen',return_value=process) as launch:
            runtime.ensure_ready(models.LARGE)
            command=launch.call_args.args[0]
            self.assertEqual(command[command.index('--alias')+1],models.LARGE)
            self.assertEqual(command[command.index('-m')+1],str(self.path/models.CATALOG[models.LARGE]['file']))
            self.assertIn('--api-key',command);self.assertEqual(command[command.index('--host')+1],'127.0.0.1')

if __name__=='__main__':unittest.main()
