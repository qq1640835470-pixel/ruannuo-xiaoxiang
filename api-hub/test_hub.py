import unittest, urllib.error, urllib.request
from unittest.mock import patch
import hub

class ProviderChecks(unittest.TestCase):
    def test_zero_is_valid(self):
        r=hub.normalize('deepseek',{'balance_infos':[{'currency':'CNY','total_balance':'0'}]})
        self.assertEqual(r['balances'][0]['total'],'0')
    def test_missing_is_unknown(self):
        with self.assertRaises(ValueError):hub.normalize('fish_audio',{})
        with self.assertRaises(ValueError):hub.normalize('deepseek',{'balance_infos':[{'currency':'CNY'}]})
    def test_invalid_numbers(self):
        for s in ['NaN','Infinity','bad',None,True]:self.assertIsNone(hub.number(s))
    def test_ids_are_not_persisted(self):
        r=hub.normalize('fish_audio',{'credit':'1.20','user_id':'private-id','_id':'private-id'})
        self.assertNotIn('private-id',str(r))
    def test_http_error_does_not_echo_key(self):
        with patch('hub.request_json',side_effect=urllib.error.HTTPError('https://example',401,'secret-key-value',{},None)):
            r=hub.check_one('fish_audio','secret-key-value')
            self.assertNotIn('secret-key-value',str(r));self.assertIsNone(r.get('api_credit'))
    def test_block_redirect(self):
        with self.assertRaises(urllib.error.HTTPError):
            hub.NoRedirect().redirect_request(urllib.request.Request('https://api.fish.audio/wallet/self/api-credit'),None,302,'',{},'https://example.com')
    def test_dpapi_round_trip(self):
        plain=b'test-data-only'
        encrypted=hub.protect(plain)
        self.assertNotIn(plain,encrypted)
        self.assertEqual(hub.protect(encrypted,decrypt=True),plain)
    def test_google_auth_not_balance(self):
        r=hub.normalize('gemini',{'models':[{'name':'sample'}]})
        self.assertIsNone(r['balance'])

if __name__=='__main__':unittest.main()
