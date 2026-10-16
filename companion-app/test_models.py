"""Model catalogue, independent selections and unknown-cost reservations; no paid calls."""
import json, pathlib, tempfile, unittest, urllib.error
from unittest.mock import patch
import providers, server

class CatalogueTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.old=(server.DATA,server.DB,providers.CATALOG_PATH)
        server.DATA=pathlib.Path(self.tmp.name);server.DB=server.DATA/'test.sqlite3'
        providers.CATALOG_PATH=server.DATA/'catalogue.json';server.init()
    def tearDown(self):
        server.DATA,server.DB,providers.CATALOG_PATH=self.old;self.tmp.cleanup()
    def test_text_filter_and_no_implicit_network(self):
        data={'models':[{'name':'models/'+name,'supportedGenerationMethods':methods} for name,methods in [
            ('gemini-new',['generateContent']),('gemini-image',['generateContent']),
            ('gemini-new-tts',['generateContent']),('gemini-transcribe',['generateContent']),
            ('gemini-nano-banana',['generateContent']),('embedding',['embedContent']),('../escape',['generateContent'])]]}
        self.assertEqual([r['id'] for r in providers.normalize_models('gemini',data)],['gemini-new'])
        with patch('providers.hub.load_keys',side_effect=AssertionError('No network expected')):
            self.assertEqual(providers.model_catalogue('gemini')['status'],'not_fetched')
            self.assertEqual(providers.validate_model('gemini',providers.MODELS['gemini']),providers.MODELS['gemini'])
            with self.assertRaises(ValueError):providers.validate_model('gemini','unlisted')
    def test_explicit_readonly_refresh_and_failure_retains_cache(self):
        class Response:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,size):return b'{"data":[{"id":"deepseek-new"}]}'
        class Opener:
            def open(inner,request,timeout):
                self.assertEqual(request.method,'GET');self.assertEqual(request.full_url,'https://api.deepseek.com/models')
                self.assertIsNone(request.data);return Response()
        with patch('providers.hub.load_keys',return_value={'deepseek':'test-secret'}),patch('providers.urllib.request.build_opener',return_value=Opener()):
            result=providers.model_catalogue('deepseek',True)
        self.assertEqual(result['models'][0]['id'],'deepseek-new')
        with patch('providers.hub.load_keys',side_effect=RuntimeError('test-secret')):
            failed=providers.model_catalogue('deepseek',True)
        self.assertEqual(failed['status'],'refresh_failed');self.assertEqual(failed['models'],result['models'])
        self.assertNotIn('test-secret',json.dumps(failed));self.assertNotIn('test-secret',providers.CATALOG_PATH.read_text())
    def test_independent_maps_and_budget_guard(self):
        with server.connect() as c:
            c.execute("UPDATE settings SET value=? WHERE key='chat_models'",(json.dumps({'gemini':providers.MODELS['gemini'],'deepseek':'deepseek-flash'}),))
        server.init();s=server.settings()
        self.assertEqual(s['model'],providers.MODELS['gemini']);self.assertEqual(s['pet_model'],providers.PET_MODELS['gemini'])
        uid=server.reserve('gemini','gemini-unknown-price')
        self.assertEqual(server.budget()['remaining_cny'],0)
        server.settle(uid,{'input_tokens':1,'output_tokens':1,'price_basis':'unknown_price_reservation_retained'})
        self.assertEqual(server.budget()['reserved_cny'],10)
        with self.assertRaises(ValueError):server.reserve('gemini')
    def test_model_parameter_and_tools_are_not_assumed(self):
        providers.CATALOG_PATH.write_text(json.dumps({'gemini':{'models':[{'id':'gemma-new'}]}}))
        response={'candidates':[{'content':{'parts':[{'text':'Hello'}]}}],'modelVersion':'returned-gemma','usageMetadata':{'promptTokenCount':10,'candidatesTokenCount':2}}
        with patch('providers.hub.load_keys',return_value={'gemini':'test'}),patch('providers.post',return_value=response) as post:
            result=providers.chat('gemini',[{'role':'user','content':'Hello'}],'test',model='gemma-new')
        self.assertIn('/gemma-new:generateContent',post.call_args.args[0]);body=post.call_args.args[2]
        self.assertNotIn('tools',body);self.assertNotIn('thinkingConfig',body['generationConfig'])
        self.assertNotIn('estimate_cny',result['usage']);self.assertEqual(result['usage']['requested_model'],'gemma-new')
        self.assertEqual(result['usage']['returned_model'],'returned-gemma')

if __name__=='__main__':unittest.main()
