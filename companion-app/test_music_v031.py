import pathlib,tempfile,unittest
from unittest.mock import patch
import music_service

class MusicV031Tests(unittest.TestCase):
    def test_search_preserves_metadata_and_uses_platform(self):
        response={'body':{'result':{'songs':[{'id':42,'name':'歌曲','ar':[{'name':'歌手'}],'dt':123}]}}}
        with patch('music_service.rpc',return_value=response) as rpc:
            result=music_service.search('  歌曲  ')
        rpc.assert_called_once_with('cloudsearch',{'keywords':'歌曲','type':1,'limit':30,'offset':0})
        self.assertEqual(result['tracks'],[{'id':42,'name':'歌曲','artists':'歌手','duration_ms':123}])
        self.assertNotIn('url',result['tracks'][0])

    def test_search_validation_no_network(self):
        with patch('music_service.rpc') as rpc:
            for query in ('','   ','a'*101,None):
                with self.assertRaises(ValueError):music_service.search(query)
            rpc.assert_not_called()

    def test_cookie_survives_status_checks_and_transient_error(self):
        with tempfile.TemporaryDirectory() as directory,patch('music_service.DATA',pathlib.Path(directory)):
            music_service.save_cookie('MUSIC_U=fixture-only;')
            original=(pathlib.Path(directory)/'netease-cookie.dpapi').read_bytes()
            self.assertNotIn(b'fixture-only',original)
            with patch('music_service.rpc',return_value={'body':{'data':{'profile':{'userId':42,'nickname':'fixture'}}}}):
                self.assertTrue(music_service.status()['logged_in'])
                self.assertTrue(music_service.status()['logged_in'])
            with patch('music_service.rpc',side_effect=ValueError('temporary offline')):
                with self.assertRaises(ValueError):music_service.status()
            self.assertEqual((pathlib.Path(directory)/'netease-cookie.dpapi').read_bytes(),original)
            self.assertEqual(music_service.load_cookie(),'MUSIC_U=fixture-only;')

if __name__=='__main__':unittest.main()
