import json,pathlib,tempfile,unittest
from unittest.mock import patch
import companion_knowledge,music_service,providers,server

class MusicKnowledgeTests(unittest.TestCase):
    def test_music_only_accepts_platform_audio_and_marks_trial(self):
        result={'body':{'data':[{'url':'http://m10.music.126.net/song.mp3','freeTrialInfo':{'start':0}}]}}
        with patch('music_service.rpc',return_value=result):
            song=music_service.song_url('186016');self.assertTrue(song['trial']);self.assertTrue(song['url'].startswith('https://'))
        result['body']['data'][0]['url']='https://example.com/untrusted.mp3'
        with patch('music_service.rpc',return_value=result),self.assertRaises(ValueError):music_service.song_url('186016')
        with self.assertRaises(ValueError):music_service.clean_id('186016&cookie=x')
    def test_no_login_does_not_call_account_api(self):
        with patch('music_service.load_cookie',return_value=''),patch('music_service.rpc') as rpc:
            self.assertFalse(music_service.status()['logged_in']);rpc.assert_not_called()
    def test_worldbook_activates_only_relevant_entries(self):
        names={r['id'] for r in companion_knowledge.select('我想弹吉他')}
        self.assertIn('music-interests',names);self.assertNotIn('engineering-interests',names)
        library=companion_knowledge.library({'phase':'午间'})
        self.assertGreaterEqual(len(library['lines']),24);self.assertFalse(library['weather_attached'])
    def test_weather_is_direct_without_text_model(self):
        weather={'status':'ok','kind':'weather','location':'深圳市南山区','current':{'temperature_2m':28,'summary':'阴'},'days':[{'summary':'阴','temperature_2m_min':25,'temperature_2m_max':30,'precipitation_probability_max':20}],'source_url':'https://api.open-meteo.com','queried_at':'test'}
        with patch('web_tools.weather',return_value=weather) as tool,patch('providers.chat') as model:
            result=server.local_chat('今天深圳市南山区的天气');tool.assert_called_once_with('深圳市南山区');model.assert_not_called()
        self.assertIn('28°C',result['reply']);self.assertEqual(result['execution'][0]['status'],'completed')
    def test_newly_known_model_has_budget_and_tools(self):
        self.assertEqual(providers.model_rates('gemini','gemini-3.5-flash-lite'),(3,25))
        self.assertIn('gemini-3.5-flash-lite',providers.TOOL_MODELS['gemini'])

if __name__=='__main__':unittest.main()
