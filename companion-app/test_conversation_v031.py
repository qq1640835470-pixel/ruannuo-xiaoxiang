import pathlib,tempfile,unittest,json
from unittest.mock import patch
import server,chat_history
class ConversationV031(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.old=server.DATA,server.DB;server.DATA=pathlib.Path(self.tmp.name);server.DB=server.DATA/'a.sqlite';server.init()
 def tearDown(self):server.DATA,server.DB=self.old;self.tmp.cleanup()
 def test_history_pagination_and_literal_search(self):
  for i in range(75):server.add_message('user','记录 '+str(i))
  with server.connect() as c:
   first=chat_history.page(c);second=chat_history.page(c,before=first['next_before']);match=chat_history.page(c,query='记录 73')
  self.assertEqual(len(first['messages']),30);self.assertTrue(first['has_more']);self.assertTrue(set(x['id'] for x in first['messages']).isdisjoint(x['id'] for x in second['messages']));self.assertEqual(len(match['messages']),1)
 def test_same_request_does_not_replay_action(self):
  with patch('server.chat',return_value={'reply':'done','actions':[]}) as chat:
   a=server.chat_once('hello','a'*32);b=server.chat_once('hello','a'*32);self.assertEqual(a,b);chat.assert_called_once()
  with self.assertRaises(ValueError):server.chat_once('different','a'*32)
 def test_uncertain_request_is_not_replayed(self):
  with patch('server.chat',side_effect=RuntimeError('timeout')):
   with self.assertRaises(RuntimeError):server.chat_once('open qq','b'*32)
  with patch('server.chat') as chat:
   self.assertTrue(server.chat_once('open qq','b'*32)['pending']);chat.assert_not_called()
 def test_route_request_without_origin_does_not_invent_lines(self):
  with patch('maps_routes.status',return_value={'configured':False}):
   result=server.local_chat('帮我查查怎么去深圳北站？')
  self.assertIn('从哪里出发',result['reply']);self.assertNotIn('1号线',result['reply'])
 def test_empty_model_response_is_retryable_error(self):
  with self.assertRaisesRegex(ValueError,'没有返回'):
   server.consume_model_result({'calls':[],'text':'  ','model':'test','usage':{}},'hello','id','local',{})
 def test_local_backend_runs_when_cloud_disabled(self):
  with server.connect() as c:c.execute("UPDATE settings SET value='\"local\"' WHERE key='provider'")
  answer={'text':'本机你好','calls':[],'model':'qwen3-4b-q4_k_m','usage':{'estimate_cny':0}}
  with patch('local_runtime.status',return_value={'installed':True}),patch('providers.chat',return_value=answer) as chat:
   result=server.chat('聊聊音乐');self.assertEqual(result['reply'],'本机你好');self.assertEqual(chat.call_args.args[0],'local')
if __name__=='__main__':unittest.main()
