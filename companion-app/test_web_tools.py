"""Read-only public tool boundaries, cache and failure behaviour. No network in unit tests."""
import json, unittest, urllib.error
from unittest.mock import patch
import web_tools

FORECAST={'current':{'time':'2026-10-16T09:00','temperature_2m':27.6,'weather_code':3},
 'daily':{'time':['2026-10-16','2026-10-17'],'weather_code':[3,51],
 'temperature_2m_max':[32.7,32.3],'temperature_2m_min':[24.4,25.1],'precipitation_probability_max':[0,20]}}
RSS=b'<rss><channel><item><title>Example &amp; official</title><link>https://example.org/page</link><description>&lt;b&gt;Public snippet&lt;/b&gt;</description></item></channel></rss>'

class WebToolsTests(unittest.TestCase):
 def setUp(self):web_tools._CACHE.clear()
 def test_shenzhen_no_geocoding_and_cache(self):
  with patch('web_tools.get',return_value=json.dumps(FORECAST).encode()) as request:
   first=web_tools.weather('深圳市南山区');second=web_tools.weather('深圳市南山区')
  self.assertEqual(first['status'],'ok');self.assertFalse(first['location_assumed']);self.assertTrue(second['cached'])
  self.assertEqual(request.call_count,1);self.assertIn('latitude=22.5333',request.call_args.args[0]);self.assertEqual(len(first['days']),2)
  first['current']['temperature_2m']=99;self.assertEqual(second['current']['temperature_2m'],27.6)
 def test_assumed_city_is_labelled_and_failures_no_fabrication(self):
  with patch('web_tools.get',return_value=json.dumps(FORECAST).encode()):self.assertTrue(web_tools.weather()['location_assumed'])
  with patch('web_tools.get',side_effect=TimeoutError('sensitive error message')):
   result=web_tools.weather('深圳市南山区')
  self.assertEqual(result['status'],'unavailable');self.assertNotIn('current',result);self.assertNotIn('sensitive',json.dumps(result))
 def test_search_only_retries_after_failure(self):
  with patch('web_tools.get',return_value=RSS) as request:
   result=web_tools.search_web('example official');again=web_tools.search_web('example official')
  self.assertEqual(request.call_count,1);self.assertTrue(again['cached']);self.assertEqual(result['results'][0]['snippet'],'Public snippet')
  web_tools._CACHE.clear()
  with patch('web_tools.get',side_effect=[TimeoutError(),TimeoutError(),b'<a class="result__a" href="https://example.org">Example official</a><a class="result__snippet">Public snippet</a>']) as request:
   result=web_tools.search_web('example official')
  self.assertEqual(result['status'],'ok');self.assertEqual(len(result['attempts']),2)
  self.assertIn('html.duckduckgo.com',request.call_args.args[0])
 def test_fixed_destinations_and_parameter_limits(self):
  with patch('web_tools.urllib.request.build_opener',side_effect=AssertionError('Unexpected network')):
   for url in ['http://www.bing.com/search','https://evil.example/','https://www.bing.com:444/search','https://user@www.bing.com/search']:
    with self.assertRaises(ValueError):web_tools.get(url)
  for name,args in [('search_web',{'query':'x','url':'https://evil.example'}),('weather',{'shell':'cmd'}),('execute',{})]:
   with self.assertRaises(ValueError):web_tools.execute(name,args)
  with self.assertRaises(ValueError):web_tools.search_web('x'*181)
 def test_rss_rejects_entities_and_non_http(self):
  with self.assertRaises(ValueError):web_tools.parse_rss(b'<!DOCTYPE rss><rss/>')
  with self.assertRaises(ValueError):web_tools.parse_rss(b'<rss><channel><item><title>x</title><link>javascript:alert(1)</link></item></channel></rss>')
 def test_search_failure_honest_and_bounded(self):
  with patch('web_tools.get',side_effect=TimeoutError()) as request:result=web_tools.search_web('test')
  self.assertEqual(request.call_count,3);self.assertEqual(result['status'],'unavailable');self.assertNotIn('results',result)
 def test_baidu_canonical_cards_ignore_scripts_navigation_and_duplicates(self):
  raw='''<script>fake="<div id='0' class='c-container' mu='https://evil.example'><h3>fake</h3></div>"</script>
  <h3><a href="https://nav.example">navigation</a></h3>
  <div class="result c-container" id="1" mu="https://www.szlib.org.cn/page/server-center-pavilion.html">
   <h3><a href="http://www.baidu.com/link?url=tracking">深圳<em>图书馆</em>服务时间</a></h3>
   <div>中心馆服务指南<br/>开放安排见官网。<script>secret javascript</script></div></div>
  <div class="c-container" id="2" mu="javascript:alert(1)"><h3>bad</h3></div>
  <div class="c-container" id="3" mu="https://www.szlib.org.cn/page/server-center-pavilion.html"><h3>重复</h3></div>'''.encode()
  rows=web_tools.parse_baidu(raw)
  self.assertEqual(len(rows),1);self.assertIn('szlib.org.cn',rows[0]['url'])
  self.assertNotIn('tracking',rows[0]['url']);self.assertNotIn('javascript',rows[0]['snippet'])
  self.assertIn('开放安排',rows[0]['snippet']);self.assertEqual(rows[0]['excerpt_kind'],'search_result_excerpt')
 def test_unrelated_rss_falls_back_to_related_baidu_without_model(self):
  raw='<div id="1" class="c-container" mu="https://www.szlib.org.cn/page/server-center-pavilion.html"><h3>深圳图书馆 开放时间</h3><div>服务指南：深圳图书馆开放时间。</div></div>'.encode()
  with patch('web_tools.get',side_effect=[RSS,raw]) as request:result=web_tools.search_web('深圳图书馆 开放时间')
  self.assertEqual(result['status'],'ok');self.assertEqual(result['scope'],'public_web_search')
  self.assertEqual(result['source'],'百度公开网页结果');self.assertEqual(result['attempts'][0]['error_type'],'QueryMismatch')
  self.assertEqual(request.call_count,2);self.assertIn('wd=',request.call_args.args[0]);self.assertIn('rn=5',request.call_args.args[0])
 def test_challenges_and_per_row_relevance_do_not_pass_as_results(self):
  with self.assertRaises(web_tools.SearchChallenge):web_tools.parse_baidu('<title>百度安全验证</title>'.encode())
  with self.assertRaises(web_tools.QueryMismatch):web_tools.relevant('深圳大学 微电子学院',[{'title':'深圳旅游','snippet':'城市介绍','url':'https://example.org'}])
  rows=web_tools.relevant('深圳图书馆',[{'title':'深圳图书馆','snippet':'相关服务','url':'https://good.example'}, {'title':'无关彩票','snippet':'领取奖品','url':'https://bad.example'}])
  self.assertEqual(len(rows),1)
 def test_scholarly_api_scope_and_provenance_are_explicit(self):
  raw=json.dumps({'message':{'items':[{'title':['超低功耗集成电路技术'],'URL':'https://doi.org/10.1360/112012-513','DOI':'10.1360/112012-513','publisher':'Science China Press','published':{'date-parts':[[2012,12,1]]}}]}}).encode()
  with patch('web_tools.get',return_value=raw) as request:result=web_tools.search_web('低功耗集成电路论文')
  self.assertEqual(request.call_count,1);self.assertIn('api.crossref.org/works?',request.call_args.args[0])
  self.assertEqual(result['scope'],'scholarly_metadata_only');self.assertIn('非全网',result['note'])
  self.assertIn('未读取论文正文',result['results'][0]['snippet']);self.assertIn('2012-12-1',result['results'][0]['snippet'])
 def test_generic_query_never_silently_becomes_scholarly_search(self):
  with patch('web_tools.get',side_effect=TimeoutError()) as request:result=web_tools.search_web('深圳图书馆开放时间')
  self.assertEqual(result['status'],'unavailable');self.assertEqual(request.call_count,3)
  self.assertFalse(any('crossref' in call.args[0] for call in request.call_args_list))
 def test_captcha_redirect_is_reported_without_visiting_challenge(self):
  redirect=urllib.error.HTTPError('https://www.baidu.com/s',302,'redirect',{'Location':'https://wappass.baidu.com/static/captcha/tuxing_v2.html'},None)
  with patch('web_tools.get',side_effect=[TimeoutError(),redirect,web_tools.SearchChallenge()]) as request:result=web_tools.search_web('深圳图书馆开放时间')
  self.assertEqual(request.call_count,3);self.assertEqual(result['status'],'unavailable')
  self.assertIn('验证码',result['detail']);self.assertEqual(result['attempts'][1]['error_type'],'SearchChallenge')
  self.assertFalse(any('wappass' in call.args[0] for call in request.call_args_list))

if __name__=='__main__':unittest.main()
