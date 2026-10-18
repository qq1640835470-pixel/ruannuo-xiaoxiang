"""Offline keyword-candidate checks using synthetic map data only."""
import json,unittest,urllib.parse
from unittest.mock import patch
import maps_routes as routes,maps_service

KEY='fixture_secret_123'
CONFIG={'provider':'amap','enabled':True,'keys':{'amap':KEY}}
POIS={'status':'1','pois':[
    {'name':'测试大学(东校区)','location':'114.1,22.6','cityname':'测试市','adname':'东区','address':'学院路1号'},
    {'name':'测试大学(西校区)','location':'114.2,22.7','cityname':'测试市','adname':'西区','address':'学院路2号'}]}

class MapsCandidatesTests(unittest.TestCase):
    def test_fuzzy_query_returns_official_candidates_without_exact_name_match(self):
        with patch.object(routes,'_load',return_value=CONFIG),patch.object(routes,'_request',return_value=POIS) as request,patch('maps_service.urllib.request.urlopen') as photon:
            result=maps_service.search_places('测试大学')
        self.assertEqual(len(result['results']),2);self.assertEqual(result['provider'],'amap')
        self.assertEqual(result['coordinate_system'],'GCJ-02');photon.assert_not_called()
        self.assertEqual(request.call_args.args[0],'amap_poi')
        self.assertEqual(request.call_args.args[1]['keywords'],'测试大学')
        self.assertNotIn('location',request.call_args.args[1])
        self.assertIn('东区',result['results'][0]['address'])
        uri=urllib.parse.urlsplit(result['results'][0]['url'])
        self.assertEqual(uri.netloc,'uri.amap.com');self.assertNotIn(KEY,json.dumps(result))
        self.assertEqual(urllib.parse.parse_qs(uri.query)['position'],['114.1,22.6'])

    def test_failure_does_not_fall_back_or_expose_key(self):
        for response in ({'status':'0','info':KEY},RuntimeError(KEY)):
            with self.subTest(response=type(response).__name__),patch.object(routes,'_load',return_value=CONFIG),patch.object(routes,'_request',side_effect=response if isinstance(response,Exception) else None,return_value=response),patch('maps_service.urllib.request.urlopen') as photon:
                result=maps_service.search_places('测试车站')
                self.assertEqual(result['status'],'unavailable');photon.assert_not_called()
                self.assertNotIn(KEY,json.dumps(result))

    def test_invalid_duplicate_and_key_echo_candidates(self):
        rows=[*POIS['pois'],POIS['pois'][0],{'name':'无效坐标','location':'999,999'},
              {'name':KEY,'location':'115,23','address':KEY}]
        with patch.object(routes,'_load',return_value=CONFIG),patch.object(routes,'_request',return_value={'status':'1','pois':rows}):
            result=maps_service.search_places('测试大学')
        self.assertEqual(len(result['results']),3);self.assertNotIn(KEY,json.dumps(result))

    def test_disabled_amap_uses_legacy_path(self):
        with patch.object(routes,'_load',return_value={**CONFIG,'enabled':False}),patch.object(routes,'_request') as amap,patch('maps_service.urllib.request.urlopen') as photon,patch('maps_service.time.sleep'):
            photon.return_value.__enter__.return_value.read.return_value=b'{"features":[]}'
            result=maps_service.search_places('offline-legacy-fixture')
        amap.assert_not_called();photon.assert_called_once();self.assertEqual(result['source'],'Photon / OpenStreetMap')

    def test_route_ambiguity_preserves_addresses_and_copied_candidate_can_match(self):
        with patch.object(routes,'_request',return_value=POIS):
            with self.assertRaises(LookupError) as raised:routes._amap_landmark('测试大学',KEY)
            self.assertIn('东区学院路1号',str(raised.exception));self.assertIn('西区学院路2号',str(raised.exception))
            selected=routes._amap_landmark('测试大学(东校区)测试市东区学院路1号',KEY)
            self.assertEqual(selected['coordinate'],'114.1,22.6')

if __name__=='__main__':unittest.main()
