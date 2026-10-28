import pathlib,sys,unittest
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from ks import event_clip as E
class LanguageTests(unittest.TestCase):
 def test_english_source(self):
  self.assertIn('SOURCE LANGUAGE: English',E.caption_language_rule([{'text':'We need a creative strategy for our community.'}]))
 def test_thai_with_loanwords(self):
  self.assertIn('SOURCE LANGUAGE: Thai',E.caption_language_rule([{'text':'เราควรวางแผนเนื้อหาให้เหมาะสมกับกลุ่มผู้ชม Content'}]))
 def test_webhook_prompt(self):
  rule=E.caption_language_rule([{'text':'This is an English presentation.'}])
  with patch.object(E._CONTEXT,'conf',{'ai_backend':'webhook','webhook_utcc':True},create=True),patch.object(E._CONTEXT,'language_rule',rule,create=True),patch.object(E.CE,'call_webhook',return_value='[{"summary":"English summary"}]') as call:
   E.ask('สรุปเนื้อหา')
  prompt=call.call_args.args[0];self.assertIn('SOURCE LANGUAGE: English',prompt);self.assertIn('JSON examples do not set',prompt)
if __name__=='__main__':unittest.main()
