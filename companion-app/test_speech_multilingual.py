"""Offline translation-to-speech tests; synthetic text, no actual model or Fish calls."""
import http.cookiejar,http.server,json,pathlib,tempfile,threading,unittest,urllib.request
from unittest.mock import patch
import local_runtime,providers,server,speech_service as speech

class SpeechLanguageTests(unittest.TestCase):
    def test_translation_precedes_synthesis_and_language_caches_are_separate(self):
        with tempfile.TemporaryDirectory() as d,patch.object(local_runtime,'translate') as translate,patch.object(providers,'speech',return_value=b'audio') as synth:
            for language,text in (('zh','你好'),('ja','こんにちは'),('yue','你好呀'),('en','Hello')):
                translate.return_value={'text':text,'model':'fixture-local','usage':{'estimate_cny':0}}
                def render(spoken,reference_id,language):
                    self.assertEqual(spoken,text);self.assertEqual(reference_id,speech.VOICE)
                    self.assertEqual(translate.call_args.args,('你好',language));return b'audio'
                synth.side_effect=render
                first=speech.generate('你好',d,language=language);second=speech.generate('你好',d,language=language)
                self.assertEqual(first['translated_text'],text);self.assertEqual(second['translated_text'],text)
                self.assertFalse(first['cached']);self.assertTrue(second['cached'])
            self.assertEqual(synth.call_count,4);self.assertEqual(translate.call_count,4)

    def test_translation_failure_never_sends_original_or_pauses_fish(self):
        with tempfile.TemporaryDirectory() as d,patch.object(local_runtime,'translate',side_effect=ValueError('本机翻译不可用')),patch.object(providers,'speech') as synth:
            with self.assertRaises(ValueError):speech.generate('你好',d,language='ja')
            synth.assert_not_called();self.assertIsNone(speech.status(d)['last_error'])
            self.assertFalse((pathlib.Path(d)/'speech-state.json').exists())

    def test_expired_paused_and_cooldown_block_translation(self):
        with tempfile.TemporaryDirectory() as d,patch.object(local_runtime,'translate') as translate,patch.object(providers,'speech') as synth:
            with patch.object(speech,'FREE_UNTIL',speech.dt.date(2000,1,1)):
                with self.assertRaises(ValueError):speech.generate('你好',d,language='en')
            record=pathlib.Path(d)/'speech-state.json';record.write_text('{"paused":true}')
            with self.assertRaises(ValueError):speech.generate('你好',d,language='en')
            record.write_text(json.dumps({'last_idle':speech.time.time()}))
            self.assertEqual(speech.generate('你好',d,'idle','en'),{'skipped':'cooldown'})
            translate.assert_not_called();synth.assert_not_called()

    def test_invalid_language_and_invalid_translation_do_not_synthesize(self):
        with tempfile.TemporaryDirectory() as d,patch.object(local_runtime,'translate') as translate,patch.object(providers,'speech') as synth:
            for language in ('fr',None,{},''):
                with self.assertRaises(ValueError):speech.generate('你好',d,language=language)
            translate.assert_not_called()
            for text in ('','*','a'*601):
                translate.return_value={'text':text,'model':'fixture','usage':{}}
                with self.assertRaises(ValueError):speech.generate('你好',d,language='en')
            synth.assert_not_called()

    def test_language_identity_and_normalization_survive_cache(self):
        with tempfile.TemporaryDirectory() as d,patch.object(local_runtime,'translate',return_value={'text':'**xy**你好','model':'fixture','usage':{}}) as translate,patch.object(providers,'speech',return_value=b'audio') as synth:
            original=speech.generate('xy你好',d)
            translated=speech.generate('xy你好',d,language='zh')
            self.assertNotEqual(original['url'],translated['url'])
            self.assertEqual(translated['translated_text'],'叉歪你好')
            synth.assert_called_with('叉歪你好',reference_id=speech.VOICE,language='zh')

class TranslationRuntimeTests(unittest.TestCase):
    def test_dedicated_prompt_has_no_persona_memory_or_tools(self):
        for language in local_runtime.TRANSLATION_LANGUAGES:
            with self.subTest(language=language),patch.object(local_runtime,'choose',return_value={'model':local_runtime.MODEL}),patch.object(local_runtime,'ensure_ready'),patch.object(local_runtime,'_request',return_value={'choices':[{'message':{'content':'译文'},'finish_reason':'stop'}]}) as request,patch.object(local_runtime.local_adaptation,'context',side_effect=AssertionError('No personal context')),patch.object(providers.hub,'load_keys',side_effect=AssertionError('No cloud')):
                result=local_runtime.translate('原文',language);body=request.call_args.args[1]
                self.assertEqual(len(body['messages']),2);self.assertEqual(body['messages'][1]['content'],'原文')
                self.assertIn(local_runtime.TRANSLATION_LANGUAGES[language],body['messages'][0]['content'])
                self.assertNotIn('tools',body);self.assertNotIn('女仆',body['messages'][0]['content'])
                self.assertEqual(result['usage']['estimate_cny'],0)

    def test_incomplete_translation_or_tool_calls_are_rejected(self):
        for choice in ({'message':{'content':'half'},'finish_reason':'length'},{'message':{'content':'','tool_calls':[{}]}},{'message':{'content':''}}):
            with patch.object(local_runtime,'choose',return_value={'model':local_runtime.MODEL}),patch.object(local_runtime,'ensure_ready'),patch.object(local_runtime,'_request',return_value={'choices':[choice]}):
                with self.assertRaises(ValueError):local_runtime.translate('原文','en')

    def test_fish_payload_has_target_text_and_exact_free_model(self):
        for language in ('zh','ja','yue','en'):
            with patch.object(providers.hub,'load_keys',return_value={'fish_audio':'fixture'}),patch.object(providers,'post',return_value=b'audio') as post:
                providers.speech('译文',speech.VOICE,language=language)
                body=post.call_args.args[2]
                self.assertEqual(body['language'],language);self.assertTrue(body['text'].endswith('译文'))
                self.assertEqual(body['reference_id'],speech.VOICE)
                self.assertEqual(post.call_args.kwargs['extra'],{'model':'s2.1-pro-free'})

class SpeechEndpointTests(unittest.TestCase):
    def test_language_flows_through_http_to_translation_and_fish(self):
        with tempfile.TemporaryDirectory() as d,patch.object(server,'DATA',pathlib.Path(d)),patch.object(server,'DB',pathlib.Path(d)/'test.sqlite3'):
            server.init();httpd=http.server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
            worker=threading.Thread(target=httpd.serve_forever,daemon=True);worker.start()
            try:
                base='http://127.0.0.1:'+str(httpd.server_port)
                opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
                with opener.open(base+'/') as response:response.read()
                with patch.object(local_runtime,'translate',return_value={'text':'Hello','model':'fixture','usage':{'estimate_cny':0}}) as translate,patch.object(providers,'speech',return_value=b'audio') as synth:
                    request=urllib.request.Request(base+'/api/speech',data=json.dumps({'text':'你好','language':'en'}).encode(),headers={'Content-Type':'application/json'})
                    with opener.open(request) as response:result=json.load(response)
                    translate.assert_called_once_with('你好','en');synth.assert_called_once_with('Hello',reference_id=speech.VOICE,language='en')
                    self.assertEqual(result['translated_text'],'Hello');self.assertEqual(result['language'],'en')
            finally:httpd.shutdown();httpd.server_close();worker.join()

if __name__=='__main__':unittest.main()
