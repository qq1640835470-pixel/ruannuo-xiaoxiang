"""Style-playback fixtures only: no platform, account or model requests."""
import pathlib,tempfile,unittest
from unittest.mock import patch
import local_intents,music_service,server

class MusicStyleTests(unittest.TestCase):
    def test_command_quantities_and_negative_examples(self):
        for text,count,query in (('随便播放几首钢琴曲',5,'钢琴曲'),('帮我随机播放三首轻音乐',3,'轻音乐'),('播放十二首爵士乐',12,'爵士乐'),('我想听2首民谣',2,'民谣')):
            self.assertEqual(local_intents.music_request(text),{'query':query,'count':count,'recommend':True})
        self.assertFalse(local_intents.music_request('播放一首晴天')['recommend'])
        self.assertEqual(local_intents.music_request('听一首钢琴曲')['count'],1)
        for text in ('不要播放钢琴曲','例如播放三首钢琴曲','为什么不能播放音乐？','“播放几首钢琴曲”是例子'):
            self.assertIsNone(local_intents.music_request(text))
        with self.assertRaises(ValueError):local_intents.music_request('播放21首钢琴曲')

    def test_playlist_keyword_search_then_unique_random_queue(self):
        tracks=[{'id':i,'name':'曲目'+str(i),'artists':''} for i in range(1,9)]
        with patch('music_service.rpc',return_value={'body':{'result':{'playlists':[{'id':42,'name':'钢琴合辑'}]}}}) as rpc,patch('music_service.tracks',return_value={'tracks':[*tracks,tracks[0],{'id':None}]}) as playlist:
            result=music_service.recommend('钢琴曲',5)
        rpc.assert_called_once_with('cloudsearch',{'keywords':'钢琴曲','type':1000,'limit':5,'offset':0})
        playlist.assert_called_once_with(42);self.assertEqual(len(result['tracks']),5)
        self.assertEqual(len({t['id'] for t in result['tracks']}),5);self.assertEqual(result['playlist'],'钢琴合辑')

    def test_empty_search_has_no_song_fallback(self):
        with patch('music_service.rpc',return_value={'body':{'result':{}}}),patch('music_service.tracks') as tracks:
            self.assertEqual(music_service.recommend('钢琴曲')['tracks'],[]);tracks.assert_not_called()

    def test_explicit_style_command_uses_no_language_model_and_returns_queue(self):
        with tempfile.TemporaryDirectory() as d,patch.object(server,'DATA',pathlib.Path(d)),patch.object(server,'DB',pathlib.Path(d)/'db.sqlite3'):
            server.init();tracks=[{'id':i,'name':'钢琴'+str(i),'artists':''} for i in range(1,6)]
            with patch('music_service.recommend',return_value={'tracks':tracks,'playlist':'合辑'}) as recommend,patch('providers.chat',side_effect=AssertionError('No model')):
                result=server.chat('随便播放几首钢琴曲')
            recommend.assert_called_once_with('钢琴曲',5)
            self.assertEqual(result['music']['tracks'],tracks);self.assertEqual(result['music']['play_id'],1)
            self.assertIn('请求播放',result['reply']);self.assertEqual(result['budget']['requests'],0)

if __name__=='__main__':unittest.main()
