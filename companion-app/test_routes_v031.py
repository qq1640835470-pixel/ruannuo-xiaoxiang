"""Offline fixtures only: no credential lookup and no live map requests."""
import json
import tempfile
import unittest
from unittest.mock import patch
import maps_routes as routes

AMAP_GEO = {'status': '1', 'geocodes': [{'location': '116.400000,39.900000', 'formatted_address': '北京市测试地标', 'citycode': '010', 'level': '兴趣点'}]}
BAIDU_GEO = {'status': 0, 'result': {'location': {'lat': 39.9, 'lng': 116.4}, 'precise': 1, 'level': '商务大厦'}}
AMAP_WALK = {'status': '1', 'route': {'paths': [{'distance': '120', 'duration': '90', 'steps': [{'instruction': '沿测试路向东步行120米', 'distance': '120', 'duration': '90'}]}]}}
AMAP_BUS = {'status': '1', 'route': {'transits': [{'distance': '2000', 'duration': '800', 'segments': [{'walking': {'steps': [{'instruction': '步行至甲站', 'distance': '100'}]}, 'bus': {'buslines': [{'name': '测试1路（乙方向）', 'departure_stop': {'name': '甲站'}, 'arrival_stop': {'name': '乙站'}, 'via_num': '3', 'duration': '500'}]}}]}]}}
BAIDU_WALK = {'status': 0, 'result': {'routes': [{'duration': 90, 'distance': 120, 'steps': [{'instruction': '<b>向东</b>步行120米', 'distance': 120, 'duration': 90}]}]}}
BAIDU_BUS = {'status': 0, 'result': {'routes': [{'duration': 800, 'distance': 2000, 'steps': [[{'instructions': '在甲站乘测试2路到乙站', 'vehicle': {'name': '测试2路', 'start_name': '甲站', 'end_name': '乙站'}}]]}]}}


class RoutesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.directory = self.tmp.name
        self.protection = patch.object(routes, '_protect', side_effect=lambda raw, decrypt=False: raw[7:] if decrypt else b'DPAPI::' + raw)
        self.protection.start()
        self.addCleanup(self.protection.stop)
        self.addCleanup(self.tmp.cleanup)

    def save(self, provider='amap'):
        return routes.configure({'provider': provider, 'api_key': 'fixture_secret_123', 'enabled': True}, self.directory)

    def test_unconfigured_does_not_request(self):
        with patch.object(routes, '_request', side_effect=AssertionError('network')) as request:
            result = routes.plan('北京市甲', '北京市乙', data_dir=self.directory)
            self.assertEqual(result['status'], 'needs_configuration')
            request.assert_not_called()

    def test_settings_never_return_key_and_clear(self):
        self.assertNotIn('fixture_secret_123', json.dumps(self.save()))
        self.assertNotIn('fixture_secret_123', json.dumps(routes.status(self.directory)))
        routes.configure({'provider': 'amap', 'enabled': False}, self.directory)
        self.assertTrue(routes.status(self.directory)['configured'])
        result = routes.configure({'provider': 'amap', 'clear': True}, self.directory)
        self.assertFalse(result['configured'])

    def test_four_official_adapter_fixtures(self):
        fixtures = [('amap', 'walking', AMAP_GEO, AMAP_WALK), ('amap', 'transit', AMAP_GEO, AMAP_BUS),
                    ('baidu', 'walking', BAIDU_GEO, BAIDU_WALK), ('baidu', 'transit', BAIDU_GEO, BAIDU_BUS)]
        for provider, mode, geo, fixture in fixtures:
            with self.subTest(provider=provider, mode=mode):
                self.save(provider)
                with patch.object(routes, '_request', side_effect=[geo, geo, fixture]) as request:
                    result = routes.plan('北京市甲地标', '北京市乙地标', mode, provider, self.directory)
                    self.assertEqual(result['status'], 'ok')
                    self.assertEqual(result['provider'], provider)
                    self.assertEqual(result['routes'][0]['distance_meters'], 120 if mode == 'walking' else 2000)
                    self.assertTrue(result['routes'][0]['steps'][0]['instruction'])
                    self.assertIsNone(result['routes'][0]['fare'])
                    endpoint, params = request.call_args.args
                    self.assertEqual(endpoint, provider + '_' + mode)
                    self.assertNotIn('latitude', params)
                    if provider == 'amap' and mode == 'transit':
                        self.assertEqual(params['city'], '010')
                    if provider == 'baidu':
                        self.assertEqual(params['origin'], '39.900000,116.400000')

    def test_ambiguous_address_no_routing(self):
        self.save()
        with patch.object(routes, '_request', return_value={'status': '1', 'geocodes': AMAP_GEO['geocodes'] * 2}) as request:
            result = routes.plan('甲', '乙', data_dir=self.directory)
            self.assertEqual(result['status'], 'needs_clarification')
            self.assertEqual(request.call_count, 2)

    def test_poi_exact_match_beats_similar_campus(self):
        self.save()
        poi={'status':'1','pois':[{'name':'深圳大学(粤海校区)','location':'113.936577,22.532641','cityname':'深圳市'},{'name':'深圳大学(沧海校区)','location':'113.939384,22.528107','cityname':'深圳市'}]}
        with patch.object(routes,'_request',return_value=poi) as request:
            result=routes._amap_geocode('深圳大学粤海校区','fixture_secret_123')
            self.assertEqual(result['coordinate'],'113.936577,22.532641')
            self.assertEqual(result['city'],'深圳市')
            self.assertEqual(request.call_args.args[0],'amap_poi')

    def test_baidu_imprecise_address_stops(self):
        self.save('baidu')
        geo = {'status': 0, 'result': {**BAIDU_GEO['result'], 'precise': 0}}
        with patch.object(routes, '_request', return_value=geo) as request:
            self.assertEqual(routes.plan('甲', '乙', data_dir=self.directory)['status'], 'needs_clarification')
            self.assertEqual(request.call_count, 1)

    def test_empty_amap_railway_metadata_is_not_a_train(self):
        fixture=json.loads(json.dumps(AMAP_BUS))
        fixture['route']['transits'][0]['segments'][0]['railway']={'via_stops':[],'alters':[],'spaces':[]}
        result=routes._amap_routes(fixture,'transit')
        self.assertEqual(len(result),1)
        self.assertIn('测试1路',result[0]['steps'][-1]['instruction'])

    def test_provider_errors_are_generic_and_no_auto_fallback(self):
        self.save('baidu')
        self.save('amap')
        with patch.object(routes, '_request', side_effect=RuntimeError('https://example/?key=fixture_secret_123')) as request:
            result = routes.plan('甲', '乙', data_dir=self.directory)
            self.assertEqual(result['status'], 'unavailable')
            self.assertNotIn('fixture_secret_123', json.dumps(result))
            self.assertEqual(request.call_count, 1)

    def test_no_routes_and_html_removal(self):
        self.assertEqual(routes._baidu_routes(BAIDU_WALK, 'walking')[0]['steps'][0]['instruction'], '向东步行120米')
        self.save()
        with patch.object(routes, '_request', side_effect=[AMAP_GEO, AMAP_GEO, {'status': '1', 'route': {'paths': []}}]):
            self.assertEqual(routes.plan('甲', '乙', data_dir=self.directory)['status'], 'no_route')

    def test_google_disabled_without_network(self):
        with patch.object(routes, '_request') as request:
            self.assertEqual(routes.plan('甲', '乙', provider='google', data_dir=self.directory)['status'], 'disabled')
            request.assert_not_called()

    def test_key_echo_is_redacted(self):
        self.save()
        fixture = json.loads(json.dumps(AMAP_WALK).replace('沿测试路向东步行120米', 'fixture_secret_123'))
        with patch.object(routes, '_request', side_effect=[AMAP_GEO, AMAP_GEO, fixture]):
            result = routes.plan('甲', '乙', data_dir=self.directory)
            self.assertNotIn('fixture_secret_123', json.dumps(result))

    def test_redirect_is_refused(self):
        self.assertIsNone(routes._NoRedirect().redirect_request(None, None, 302, '', {}, 'https://other.example'))

    def test_incomplete_transit_is_not_presented_as_complete(self):
        fixture = json.loads(json.dumps(AMAP_BUS))
        fixture['route']['transits'][0]['segments'][0]['railway'] = {'name': 'test train'}
        self.assertEqual(routes._amap_routes(fixture, 'transit'), [])
        fixture = json.loads(json.dumps(AMAP_BUS))
        del fixture['route']['transits'][0]['segments'][0]['bus']['buslines'][0]['arrival_stop']
        self.assertEqual(routes._amap_routes(fixture, 'transit'), [])


if __name__ == '__main__':
    unittest.main()
