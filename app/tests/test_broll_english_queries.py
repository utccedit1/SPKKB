import json,unittest
from unittest.mock import patch
from contextlib import nullcontext
from ks import broll as B
class EnglishBroll(unittest.TestCase):
 def run_suggestion(self,response=None,error=None):
  rows=[dict(index=0,start=0,end=5,text='นักศึกษากำลังทำงานร่วมกัน')]
  with patch.object(B,'_collect_windows',return_value=(rows,None)),patch.object(B.CE,'effective_ai_label',return_value={'label':'test'}),patch.object(B.CE,'ai_feature',return_value=nullcontext()),patch.object(B.CE,'load_config',return_value={'ai_backend':'webhook'}),patch.object(B.CE,'call_webhook',side_effect=error,return_value=json.dumps(response)):
   return B.suggest('/fixture',{})
 def test_timeout_never_turns_thai_caption_into_search(self):
  result=self.run_suggestion(error=RuntimeError('read timed out'));self.assertIn('error',result);self.assertNotIn('items',result);self.assertIn('read timed out',result['error'])
 def test_only_english_query_and_alternatives_are_returned(self):
  result=self.run_suggestion([dict(start=0,end=4,query='นักศึกษาทำงาน',keywords=['students working together','นักศึกษา'],label='งานกลุ่ม')])
  item=result['items'][0];self.assertEqual(item['query'],'students working together');self.assertEqual(item['keywords'],['students working together']);self.assertEqual(item['label'],'งานกลุ่ม')
 def test_all_thai_suggestions_report_format_error(self):
  result=self.run_suggestion([dict(start=0,end=4,query='นักศึกษา',keywords=['มหาวิทยาลัย'])]);self.assertIn('ภาษาอังกฤษ',result['error'])
