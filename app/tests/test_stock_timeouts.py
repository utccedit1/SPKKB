import unittest
from ks.stock_accounts import timeout_message,JOB_TIMEOUT
class TimeoutMessages(unittest.TestCase):
 def test_stage_is_preserved_in_timeout_message(self):
  self.assertIn('ยังไม่ได้รับงาน',timeout_message({}))
  self.assertIn('ยังไม่ได้ดาวน์โหลด',timeout_message({'stage':'search','request':{'query':'coupon'}}))
  self.assertIn('ยังไม่ได้ไฟล์ครบ',timeout_message({'stage':'download'}))
  self.assertIn('coupon',timeout_message({'stage':'selected','request':{'query':'coupon'}}))
 def test_budget_matches_extension(self):self.assertEqual(JOB_TIMEOUT,480)

class ProbeTimeouts(unittest.TestCase):
 def test_probe_has_explicit_deadline(self):
  import subprocess
  from unittest.mock import patch
  from ks import stock_browser as B
  with patch('ks.core_engine.ac_ffprobe_bin',return_value='ffprobe'),patch.object(B.subprocess,'run',side_effect=subprocess.TimeoutExpired('ffprobe',20)) as run:
   with self.assertRaisesRegex(B.StockError,'20 วินาที'):B._duration('/private/app/media.mp4')
   self.assertEqual(run.call_args.kwargs['timeout'],20)

class FileAccessDeadline(unittest.TestCase):
 def test_stalled_copy_fails_without_accepting_late_result(self):
  from unittest.mock import patch
  from ks import stock_accounts as A
  job=dict(state='running',verify_step='starting',verifying=True)
  with patch.dict(A._jobs,{'deadlinecase':job}),patch.object(A.job_store,'save'):
   A._copy_deadline('deadlinecase',job)
   self.assertEqual(job['state'],'failed')
   self.assertIn('Downloads Folder',job['message'])
   self.assertFalse(job['verifying'])
 def test_probe_and_completed_jobs_are_not_failed(self):
  from unittest.mock import patch
  from ks import stock_accounts as A
  for state,step in [('running','probing'),('done','starting'),('failed','starting')]:
   job=dict(state=state,verify_step=step)
   with patch.dict(A._jobs,{'deadlinecase':job}),patch.object(A.job_store,'save') as save:
    A._copy_deadline('deadlinecase',job)
    self.assertEqual(job['state'],state);save.assert_not_called()
