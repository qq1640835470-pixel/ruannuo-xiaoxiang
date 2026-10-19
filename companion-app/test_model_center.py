import copy,json,unittest
from unittest.mock import patch
import model_center as center
import providers,server
import test_learning as fixtures
from test_openrouter import ROW
from test_learning_checks import QUESTIONS
import learning_checks

class ModelCenterTests(unittest.TestCase):
    def setUp(self):
        fixtures.LearningTests.setUp(self)
        self.cache=patch.object(providers,'CATALOG_PATH',server.DATA/'catalogue.json');self.cache.start()
        rows=[]
        for ident,pricing,params,modalities in [('vendor/free',{'prompt':'0','completion':'0'},['max_tokens','response_format'],['text']),('vendor/unknown:free',{},['max_tokens'],['text']),('other/reason',{'prompt':'0.0000005','completion':'0.000002'},['max_completion_tokens','reasoning'],['text','image']),('vendor/small',{'prompt':'0.01','completion':'0.02'},['max_tokens'],['text'])]:
            row=copy.deepcopy(ROW);row.update(id=ident,pricing=pricing,supported_parameters=params);row['architecture']['input_modalities']=modalities
            if ident.endswith('small'):row['top_provider']['max_completion_tokens']=1000
            rows.append(row)
        self.models=providers.normalize_models('openrouter',{'data':rows})
        providers.CATALOG_PATH.write_text(json.dumps({'openrouter':{'models':self.models,'fetched_at':server.now(),'status':'listed'}}),encoding='utf-8')
    def tearDown(self):self.cache.stop();fixtures.LearningTests.tearDown(self)
    def catalogue(self):
        with server.connect() as c:return center.catalogue(c,server.VERSION)
    def test_tags_prices_unknown_capabilities_and_visual_boundary(self):
        rows={r['id']:r for r in self.catalogue()['models']}
        self.assertIn('free',rows['vendor/free']['tags']);self.assertNotIn('free',rows['vendor/unknown:free']['tags']);self.assertIsNone(rows['vendor/unknown:free']['input_usd_million'])
        self.assertIn('reasoning',rows['other/reason']['tags']);self.assertIn('vision',rows['other/reason']['tags']);self.assertFalse(rows['other/reason']['image_input_adapted'])
        self.assertIn('low_cost',rows['other/reason']['tags']);self.assertEqual(rows['other/reason']['output_usd_million'],2)
        self.assertEqual(rows['vendor/small']['learning_check']['state'],'incompatible')
        self.assertTrue(all('本机已验证' not in r['verification'] for r in rows.values()))
    def test_favorite_recent_restart_and_requests(self):
        body={'request_id':'fav','action':'favorite','model_id':'vendor/free','favorite':True}
        for _ in range(2):
            with server.connect() as c:center.write(c,body,server.VERSION)
        with server.connect() as c:center.recent(c,'vendor/free')
        server.init();value=self.catalogue()
        self.assertEqual(value['preferences']['favorites'],['vendor/free']);self.assertEqual(value['preferences']['recent'],['vendor/free'])
        with self.assertRaises(ValueError):
            with server.connect() as c:center.write(c,{**body,'favorite':False},server.VERSION)
    def test_simulation_does_not_promote_real_and_old_versions_stale(self):
        metadata={'provider':'openrouter','requested_model':'vendor/free','returned_model':'vendor/free','verification_origin':'simulated'}
        result=learning_checks.execute(server.connect,'generate',{'request_id':'quiz','topic':'节点法'},lambda *a:(json.dumps(QUESTIONS),metadata))
        value=self.catalogue();self.assertIn('模拟',next(r for r in value['models'] if r['id']=='vendor/free')['verification'])
        with self.assertRaises(ValueError):
            with server.connect() as c:center.write(c,{'request_id':'no-promote','action':'verify','check_id':result['id'],'real_confirmation':True},server.VERSION)
        with server.connect() as c:center.record(c,metadata,'success','0.3.3',origin='real')
        self.assertIn('过期',next(r for r in self.catalogue()['models'] if r['id']=='vendor/free')['verification'])
    def test_user_confirmation_requires_saved_success_and_explicit_consent(self):
        metadata={'provider':'openrouter','requested_model':'vendor/free','returned_model':'vendor/free'}
        result=learning_checks.execute(server.connect,'generate',{'request_id':'quiz','topic':'节点法'},lambda *a:(json.dumps(QUESTIONS),metadata))
        self.assertNotIn('本机已验证',next(r for r in self.catalogue()['models'] if r['id']=='vendor/free')['verification'])
        body={'request_id':'verify','action':'verify','check_id':result['id'],'real_confirmation':False}
        with self.assertRaises(ValueError):
            with server.connect() as c:center.write(c,body,server.VERSION)
        with server.connect() as c:center.write(c,{**body,'real_confirmation':True},server.VERSION)
        self.assertIn('用户确认',next(r for r in self.catalogue()['models'] if r['id']=='vendor/free')['verification'])
        altered=self.models;altered[0]['context_length']=99999
        providers.CATALOG_PATH.write_text(json.dumps({'openrouter':{'models':altered,'fetched_at':server.now()}}),encoding='utf-8')
        # A changed capability signature invalidates only that model's evidence.
        with server.connect() as c:stored=center.preferences(c);stored['records'][0]['rules']='old';center.store(c,stored)
        self.assertIn('过期',next(r for r in self.catalogue()['models'] if r['id']=='vendor/free')['verification'])
    def test_confirmation_preserves_original_test_signature_and_timestamp(self):
        metadata={'provider':'openrouter','requested_model':'vendor/free','returned_model':'vendor/free'}
        result=learning_checks.execute(server.connect,'generate',{'request_id':'quiz','topic':'节点法'},lambda *a:(json.dumps(QUESTIONS),metadata))
        with server.connect() as c:
            original=center.preferences(c)['records'][0]
            changed=center.preferences(c);changed['records'][0]['rules']='old-rule';center.store(c,changed)
        with server.connect() as c:
            center.write(c,{'request_id':'verify-old','action':'verify','check_id':result['id'],'real_confirmation':True},server.VERSION)
            confirmed=center.preferences(c)['records'][0]
        self.assertEqual(confirmed['time'],original['time']);self.assertEqual(confirmed['signature'],original['signature']);self.assertEqual(confirmed['rules'],'old-rule')
        self.assertIn('过期',next(r for r in self.catalogue()['models'] if r['id']=='vendor/free')['verification'])

    def test_unknown_metadata_and_failed_result_records(self):
        self.assertEqual(center.ability({},4096,8192)['state'],'unknown')
        self.assertIsNone(center.price({'pricing':{'prompt':'Infinity'}},'prompt'))
        with server.connect() as c:center.record(c,{'provider':'openrouter','requested_model':'vendor/free'},'failure',server.VERSION,category='parameters')
        row=self.catalogue()['preferences']['records'][0];self.assertEqual(row['category'],'parameters');self.assertEqual(row['origin'],'unverified')
        self.assertTrue(all('本机已验证' not in r['verification'] for r in self.catalogue()['models']))

if __name__=='__main__':unittest.main()
