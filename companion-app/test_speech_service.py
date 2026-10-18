import datetime as dt,json,pathlib,tempfile,unittest
from unittest.mock import patch
import speech_service as speech

class SpeechTests(unittest.TestCase):
    def test_cache_and_exact_free_voice(self):
        with tempfile.TemporaryDirectory() as d,patch.object(speech.providers,'speech',return_value=b'audio') as call:
            one=speech.generate('你好',d);two=speech.generate('你好',d)
            self.assertFalse(one['cached']);self.assertTrue(two['cached']);self.assertEqual(call.call_count,1)
            call.assert_called_once_with('你好',reference_id=speech.VOICE)
            self.assertEqual(speech.audio_path(one['url'].rsplit('/',1)[-1],d).read_bytes(),b'audio')
            with self.assertRaises(ValueError):speech.audio_path('../secret',d)
    def test_asterisks_are_not_spoken_or_cached_separately(self):
        with tempfile.TemporaryDirectory() as d,patch.object(speech.providers,'speech',return_value=b'audio') as call:
            first=speech.generate('**你好**',d)
            second=speech.generate('你好',d)
            self.assertTrue(second['cached'])
            self.assertEqual(first['url'],second['url'])
            call.assert_called_once_with('你好',reference_id=speech.VOICE)
            with self.assertRaises(ValueError):speech.generate('***',d)
    def test_xy_pronunciation_and_word_boundaries(self):
        with tempfile.TemporaryDirectory() as d,patch.object(speech.providers,'speech',return_value=b'audio') as call:
            speech.generate('你好**xy**，XY！xy坐标；xylophone proxy xy123 xy_name',d)
            call.assert_called_once_with('你好叉歪，叉歪！叉歪坐标；xylophone proxy xy123 xy_name',reference_id=speech.VOICE)
            self.assertTrue(speech.generate('你好叉歪，叉歪！叉歪坐标；xylophone proxy xy123 xy_name',d)['cached'])
    def test_failure_pauses_no_fallback(self):
        with tempfile.TemporaryDirectory() as d,patch.object(speech.providers,'speech',side_effect=RuntimeError()) as call:
            with self.assertRaises(ValueError):speech.generate('测试',d)
            with self.assertRaises(ValueError):speech.generate('另一句',d,'idle')
            self.assertEqual(call.call_count,1)
            self.assertIn('未回退',speech.status(d)['last_error'])
    def test_expired_never_calls(self):
        with tempfile.TemporaryDirectory() as d,patch.object(speech,'FREE_UNTIL',dt.date(2000,1,1)),patch.object(speech.providers,'speech') as call:
            with self.assertRaises(ValueError):speech.generate('你好',d)
            call.assert_not_called()
    def test_idle_cooldown(self):
        with tempfile.TemporaryDirectory() as d,patch.object(speech.providers,'speech',return_value=b'audio'):
            speech.generate('第一句',d,'idle')
            self.assertEqual(speech.generate('第二句',d,'idle'),{'skipped':'cooldown'})

if __name__=='__main__':unittest.main()
