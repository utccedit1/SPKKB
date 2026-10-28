import json,socket,unittest
from unittest.mock import patch
from ks import webhook_diagnostics as D,core_engine as CE
import ce_ai as AI
class Diagnostics(unittest.TestCase):
 def setUp(self):D._records.clear()
 def test_transport_metadata_has_no_contents_or_credentials_and_is_owner_scoped(self):
  token=D.begin('one','https://example.invalid/hook?secret=private','autoclip',1500,9000,10000,300);D.update(token,'reading_body',200);D.update(token,'timeout')
  rows=D.recent('one');self.assertEqual(rows[0]['phase'],'reading_body');self.assertEqual(rows[0]['state'],'timeout');self.assertEqual(D.recent('two'),[])
  text=json.dumps(rows);self.assertNotIn('private',text);self.assertNotIn('example.invalid',text);self.assertNotIn('owner',text)
 def test_timeout_before_headers_records_real_phase(self):
  with patch.object(AI,'_task_stage',return_value=False),patch.object(AI.urllib.request,'urlopen',side_effect=socket.timeout('slow')):
   with self.assertRaises(RuntimeError):AI.call_webhook('private speech text',conf={'webhook_url':'https://example.invalid/hook'},max_retries=1)
  row=D.recent('')[-1];self.assertEqual(row['phase'],'waiting_headers');self.assertEqual(row['state'],'timeout');self.assertEqual(row['input_chars'],len('private speech text'));self.assertNotIn('private speech text',json.dumps(row))
 def test_report_compares_actual_routes_without_exposing_webhook_url(self):
  cfg={'ai_backend':'gemini'}
  with patch.object(CE,'load_config',return_value=cfg),patch('ks.event_clip.provider_config',return_value=({'webhook_url':'https://example.invalid/private'},'UTCC')):
   result=D.report('one')
  self.assertIn('คนละเส้นทาง',result['output']);self.assertNotIn('https://',result['output'])

 def test_pending_request_reports_current_elapsed_time(self):
  with patch.object(D.time,'monotonic',return_value=10):D.begin('one','https://example.invalid','autoclip',1,1,100,300)
  with patch.object(D.time,'monotonic',return_value=15):self.assertEqual(D.recent('one')[0]['elapsed'],5)
