import socket,threading,time,unittest,urllib.error,http.client,io
from unittest.mock import patch
from ks import cli_lab_webhook as W,core_engine as CE
import ce_ai as AI
class EditorialWebhookWait(unittest.TestCase):
 def test_waits_with_progress_and_one_long_request(self):
  def delayed(*args,**kwargs):time.sleep(.045);return '{"cuts":[]}'
  messages=[]
  with patch.object(CE,'call_webhook',side_effect=delayed) as call,patch.object(W,'POLL_SECONDS',.01):result=W.request('timed subtitles',conf={'webhook_url':'https://example.invalid/hook'},progress=messages.append)
  self.assertEqual(result,'{"cuts":[]}');self.assertEqual(call.call_count,1);self.assertEqual(call.call_args.kwargs['timeout'],300);self.assertEqual(call.call_args.kwargs['max_retries'],1);self.assertTrue(any('ผ่านไป' in message for message in messages))
 def test_cancel_discards_late_answer(self):
  release=threading.Event()
  def delayed(*args,**kwargs):release.wait(1);return 'late'
  def progress(message):
   if 'ผ่านไป' in message:raise InterruptedError('cancelled')
  try:
   with patch.object(CE,'call_webhook',side_effect=delayed) as call,patch.object(W,'POLL_SECONDS',.01):
    with self.assertRaises(InterruptedError):W.request('captions',progress=progress)
    self.assertEqual(call.call_count,1)
  finally:release.set()
 def test_read_timeout_does_not_retry_or_switch_hosts(self):
  with patch.object(AI,'_task_stage',return_value=False),patch.object(AI.urllib.request,'urlopen',side_effect=socket.timeout('The read operation timed out')) as send:
   with self.assertRaisesRegex(RuntimeError,'ไม่ส่งคำขอซ้ำ'):AI.call_webhook('captions',conf={'webhook_url':'https://chat.utcc.ac.th/hook'},timeout=300,max_retries=3)
   self.assertEqual(send.call_count,1)
 def test_wrapped_timeout_does_not_retry(self):
  with patch.object(AI,'_task_stage',return_value=False),patch.object(AI.urllib.request,'urlopen',side_effect=urllib.error.URLError(socket.timeout('timeout'))) as send:
   with self.assertRaisesRegex(RuntimeError,'หมดเวลารอเชื่อมต่อ'):AI.call_webhook('captions',conf={'webhook_url':'https://example.invalid/hook'},max_retries=3)
   self.assertEqual(send.call_count,1)
 def test_editorial_request_reports_real_network_timeouts_as_timeout(self):
  for failure in (socket.timeout('read timed out'),urllib.error.URLError(socket.timeout('connect timed out'))):
   with self.subTest(kind=type(failure).__name__),patch.object(AI,'_task_stage',return_value=False),patch.object(AI.urllib.request,'urlopen',side_effect=failure) as send:
    with self.assertRaises(TimeoutError):W.request('fixture',conf={'webhook_url':'https://example.invalid/hook'})
    self.assertEqual(send.call_count,1)
 def test_editorial_request_does_not_misclassify_connection_refusal_as_timeout(self):
  with patch.object(AI,'_task_stage',return_value=False),patch.object(AI.urllib.request,'urlopen',side_effect=urllib.error.URLError('connection refused')) as send:
   with self.assertRaises(RuntimeError) as caught:W.request('fixture',conf={'webhook_url':'https://example.invalid/hook'})
   self.assertNotIsInstance(caught.exception,TimeoutError);self.assertEqual(send.call_count,1)
 def test_incomplete_response_never_reposts_to_alternate_host(self):
  class Broken:
   status=200
   def __enter__(self):return self
   def __exit__(self,*a):pass
   def read(self):raise http.client.IncompleteRead(b'partial')
  with patch.object(AI,'_task_stage',return_value=False),patch.object(AI.urllib.request,'urlopen',return_value=Broken()) as send:
   with self.assertRaisesRegex(RuntimeError,'ไม่ส่งคำขอซ้ำ'):AI.call_webhook('captions',conf={'webhook_url':'https://chat.utcc.ac.th/hook'},max_retries=3)
   self.assertEqual(send.call_count,1)
 def test_http_error_does_not_expose_echoed_private_text(self):
  err=urllib.error.HTTPError('https://example.invalid/hook',500,'error',{},io.BytesIO(b'sensitive fixture echo'))
  with patch.object(AI,'_task_stage',return_value=False),patch.object(AI.urllib.request,'urlopen',side_effect=err):
   with self.assertRaises(RuntimeError) as caught:AI.call_webhook('captions',conf={'webhook_url':'https://example.invalid/hook'},max_retries=1)
   self.assertNotIn('sensitive fixture',str(caught.exception));self.assertIn('500',str(caught.exception))
 def test_502_does_not_report_success_or_send_again(self):
  err=urllib.error.HTTPError('https://example.invalid/hook',502,'gateway',{},io.BytesIO(b''))
  messages=[]
  with patch.object(AI,'_task_stage',return_value=False),patch.object(AI.urllib.request,'urlopen',side_effect=err) as send:
   with self.assertRaisesRegex(RuntimeError,'502'):W.request('fixture',conf={'webhook_url':'https://example.invalid/hook'},progress=messages.append)
  self.assertEqual(send.call_count,1)
  self.assertFalse(any('ได้รับคำตอบ AI' in message for message in messages))
 def test_hard_deadline_never_accepts_late_result(self):
  release=threading.Event()
  try:
   with patch.object(CE,'call_webhook',side_effect=lambda *a,**k:release.wait(1)),patch.object(W,'PLAN_TIMEOUT',.03),patch.object(W,'POLL_SECONDS',.01):
    with self.assertRaisesRegex(TimeoutError,'ยังไม่ได้สร้างหรือแก้โปรเจกต์'):W.request('captions')
  finally:release.set()
 def test_json_provider_error_is_not_a_plan_or_a_reason_to_repost(self):
  for response in ('{"error":"private fixture quota message"}',{'error':{'message':'private fixture quota message'}}):
   messages=[]
   with patch.object(CE,'call_webhook',return_value=response) as send:
    with self.assertRaises(RuntimeError) as caught:W.request('captions',progress=messages.append)
   self.assertEqual(send.call_count,1)
   self.assertNotIn('private fixture',str(caught.exception))
   self.assertFalse(any('ได้รับคำตอบ AI' in m for m in messages))
