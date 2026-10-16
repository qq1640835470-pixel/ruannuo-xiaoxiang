"""Coarse location privacy and mode transitions, without GPS or external network."""
import json
import pathlib
import tempfile
import unittest
import urllib.parse
from unittest.mock import patch
import location_service as service

FORECAST={'timezone':'Europe/London','current':{'time':'2026-10-16T10:00','temperature_2m':15,'weather_code':3},'daily':{'time':['2026-10-16','2026-10-17'],'weather_code':[3,0],'temperature_2m_max':[17,18],'temperature_2m_min':[10,11],'precipitation_probability_max':[20,0]}}
CITY={'results':[{'latitude':51.507451,'longitude':-.127758,'name':'London','country':'United Kingdom'}]}

class LocationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=pathlib.Path(self.temp.name);service._CACHE.clear()
    def tearDown(self):self.temp.cleanup()
    def test_default_and_disabled_do_not_request_network(self):
        with patch('location_service.web_tools.get',side_effect=AssertionError('Unexpected network')):
            self.assertFalse(service.status(self.path)['enabled']);self.assertEqual(service.weather(self.path)['status'],'needs_location')
            service.update({'mode':'geolocation','latitude':51.507451,'longitude':-.127758,'auto_refresh':True},self.path)
            encrypted=(self.path/'location.dpapi').read_bytes();self.assertNotIn(b'latitude',encrypted);self.assertNotIn(b'51.507451',encrypted)
            stored=service._load(self.path);self.assertEqual(stored['latitude'],51.51);self.assertEqual(stored['longitude'],-.13)
            public=json.dumps(service.status(self.path));self.assertNotIn('latitude',public);self.assertNotIn('longitude',public)
            service.update({'mode':'disabled'},self.path);self.assertEqual(service._load(self.path),{'mode':'disabled'})
    def test_manual_mode_rejects_late_automatic_position(self):
        with patch('location_service.web_tools.get',return_value=json.dumps(CITY).encode()):
            manual=service.update({'mode':'manual','city':'London'},self.path)
        late=service.update({'mode':'geolocation','latitude':1,'longitude':2,'automatic':True,'auto_refresh':True},self.path)
        self.assertTrue(late['ignored']);self.assertEqual(late['label'],manual['label']);self.assertEqual(service._load(self.path)['latitude'],51.51)
    def test_weather_rounded_auto_timezone_and_no_coordinate_output(self):
        service.update({'mode':'geolocation','latitude':51.507451,'longitude':-.127758,'auto_refresh':True},self.path)
        with patch('location_service.web_tools.get',return_value=json.dumps(FORECAST).encode()) as request:
            result=service.weather(self.path);again=service.weather(self.path)
        self.assertEqual(request.call_count,1);self.assertTrue(again['cached']);self.assertEqual(result['timezone'],'Europe/London')
        query=urllib.parse.parse_qs(urllib.parse.urlsplit(request.call_args.args[0]).query)
        self.assertEqual(query['latitude'],['51.51']);self.assertEqual(query['longitude'],['-0.13']);self.assertEqual(query['timezone'],['auto'])
        serialized=json.dumps(result);self.assertNotIn('latitude',serialized);self.assertNotIn('longitude',serialized);self.assertNotIn('51.51',serialized)
        self.assertEqual(service.status(self.path)['timezone'],'Europe/London')
    def test_invalid_position_and_failed_geocoding_preserve_record(self):
        for latitude in [True,float('nan'),91,'22']:
            with self.assertRaises(ValueError):service.update({'mode':'geolocation','latitude':latitude,'longitude':1},self.path)
        self.assertFalse((self.path/'location.dpapi').exists())
        service.update({'mode':'geolocation','latitude':22,'longitude':113},self.path)
        with patch('location_service.web_tools.get',side_effect=TimeoutError('secret coordinates')):
            with self.assertRaisesRegex(ValueError,'城市检索'):service.update({'mode':'manual','city':'London'},self.path)
            result=service.weather(self.path)
        self.assertEqual(service.status(self.path)['mode'],'geolocation');self.assertNotIn('secret',json.dumps(result));self.assertEqual(result['status'],'unavailable')
    def test_closed_mode_ignores_auto_and_stale_age(self):
        self.assertTrue(service.update({'mode':'geolocation','latitude':1,'longitude':2,'automatic':True},self.path)['ignored'])
        with patch('location_service.time.time',return_value=1000):service.update({'mode':'geolocation','latitude':1,'longitude':2,'auto_refresh':True},self.path)
        with patch('location_service.time.time',return_value=2801):self.assertTrue(service.status(self.path)['stale'])

if __name__=='__main__':unittest.main()
