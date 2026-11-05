import io,json,socket,unittest,urllib.error
from unittest.mock import patch
from ks import core_engine as CE,cli_lab_webhook as W
import ce_ai as AI

class Response:
 def __enter__(self):return self
 def __exit__(self,*args):pass
 def read(self):return json.dumps({'candidates':[{'content':{'parts':[{'text':'{"cuts":[]}'}]}}]}).encode()

def unavailable():return urllib.error.HTTPError('https://example.invalid',503,'private echo',{},io.BytesIO(b'private body'))

class GeminiUnavailableRetryTests(unittest.TestCase):
 def request(self,transport,progress=lambda m:None):
  with patch.object(AI,'_task_stage',return_value=False),patch.object(AI,'_pick_available_model',side_effect=lambda m:m),patch.object(AI.urllib.request,'urlopen',side_effect=transport) as send,patch.object(W.time,'sleep'),patch.object(CE,'call_webhook',side_effect=AssertionError('no UTCC fallback')):
   out=W.request('fictional captions',conf={'ai_backend':'gemini','gemini_api_key':'fixture-key','gemini_model':'fixture-model'},retry_unavailable=True,progress=progress)
   return out,send.call_count
 def test_explicit_503_recovers_using_same_model_after_announcing_retry(self):
  messages=[];out,count=self.request([unavailable(),Response()],messages.append)
  self.assertEqual(out,'{"cuts":[]}');self.assertEqual(count,2)
  self.assertTrue(any('503' in m and 'ลอง' in m for m in messages))
 def test_repeated_503_stops_after_three_requests(self):
  count=[]
  def send(*a,**k):count.append(1);raise unavailable()
  with self.assertRaisesRegex(RuntimeError,'503'):self.request(send)
  self.assertEqual(len(count),3)
 def test_read_timeout_is_never_retried(self):
  count=[]
  def send(*a,**k):count.append(1);raise socket.timeout('read timed out')
  with self.assertRaises(TimeoutError):self.request(send)
  self.assertEqual(len(count),1)
 def test_cancellation_before_retry_prevents_second_post(self):
  count=[]
  def send(*a,**k):count.append(1);raise unavailable()
  def progress(message):
   if '503' in message:raise InterruptedError('cancelled')
  with self.assertRaises(InterruptedError):self.request(send,progress)
  self.assertEqual(len(count),1)
 def test_quota_exhaustion_is_never_retried(self):
  count=[]
  def send(*a,**k):count.append(1);raise urllib.error.HTTPError('https://example.invalid',429,'quota',{},io.BytesIO(b''))
  with self.assertRaisesRegex(RuntimeError,'429'):self.request(send)
  self.assertEqual(len(count),1)
 def test_cancellation_after_backoff_prevents_second_post(self):
  count=[]
  def send(*a,**k):count.append(1);raise unavailable()
  def progress(message):
   if 'ตรวจสถานะก่อนลอง' in message:raise InterruptedError('cancelled')
  with self.assertRaises(InterruptedError):self.request(send,progress)
  self.assertEqual(len(count),1)
 def test_daily_quota_is_distinguished_without_echoing_provider_body(self):
  body={'error':{'message':'private provider body','details':[{'@type':'type.googleapis.com/google.rpc.QuotaFailure','violations':[{'quotaId':'GenerateRequestsPerDayPerProjectPerModel-FreeTier'}]}]}}
  def send(*a,**k):raise urllib.error.HTTPError('https://example.invalid?key=private',429,'private',{},io.BytesIO(json.dumps(body).encode()))
  with self.assertRaises(RuntimeError) as caught:self.request(send)
  self.assertIn('รายวัน',str(caught.exception));self.assertNotIn('private',str(caught.exception))
 def test_minute_quota_is_distinguished_from_daily_exhaustion(self):
  body={'error':{'details':[{'violations':[{'quotaId':'GenerateRequestsPerMinutePerProjectPerModel'}]}]}}
  def send(*a,**k):raise urllib.error.HTTPError('https://example.invalid',429,'quota',{},io.BytesIO(json.dumps(body).encode()))
  with self.assertRaises(RuntimeError) as caught:self.request(send)
  self.assertIn('ต่อนาที',str(caught.exception));self.assertNotIn('รายวัน',str(caught.exception))
