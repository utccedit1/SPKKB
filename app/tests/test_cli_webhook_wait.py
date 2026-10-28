import socket,threading,time,unittest,urllib.error
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
 def test_hard_deadline_never_accepts_late_result(self):
  release=threading.Event()
  try:
   with patch.object(CE,'call_webhook',side_effect=lambda *a,**k:release.wait(1)),patch.object(W,'PLAN_TIMEOUT',.03),patch.object(W,'POLL_SECONDS',.01):
    with self.assertRaisesRegex(TimeoutError,'ยังไม่ได้สร้างหรือแก้โปรเจกต์'):W.request('captions')
  finally:release.set()
