import sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ks import caption_loanwords as L

class LoanwordTests(unittest.TestCase):
 def test_exact_replacements_keep_surrounding_speech(self):
  self.assertEqual(L.apply_replacements('ทำคอนเทนต์กับเอเจนซี่ค่ะ',[
   {'source':'คอนเทนต์','english':'Content','occurrence':1},
   {'source':'เอเจนซี่','english':'Agency','occurrence':1}]),'ทำ Content กับ Agency ค่ะ')
 def test_occurrence_targets_one_repeat(self):
  self.assertEqual(L.apply_replacements('คอนเทนต์ คอนเทนต์',[{'source':'คอนเทนต์','english':'Content','occurrence':2}]),'คอนเทนต์ Content')
 def test_invalid_or_overlapping_edits_refused(self):
  good={'source':'คอนเทนต์','english':'Content','occurrence':1}
  for edits in ([dict(good,source='ไม่มี')],[dict(good,english='เนื้อหา')],[dict(good,occurrence=True)],[good,good]):
   with self.assertRaises(ValueError):L.apply_replacements('คอนเทนต์',edits)
 def test_complete_coverage_required_and_retried(self):
  calls=[]
  def ask(*args):calls.append(args);return []
  warnings=[]
  result,count=L.convert([(0,None,None,'งาน')],{},ask,warnings)
  self.assertEqual(result,{0:'งาน'});self.assertEqual(count,0);self.assertTrue(warnings)
  self.assertEqual(len(calls),3)
 def test_no_changes_preserves_text(self):
  result,count=L.convert([(0,None,None,'ทำงานจริงๆ')],{},lambda *a:[{'index':0,'replacements':[]}])
  self.assertEqual(result,{0:'ทำงานจริงๆ'});self.assertEqual(count,0)

 def test_english_terms_and_normalization(self):
  for value in ['3D','AI/ML','R&D','C++','C#','.NET',"Creator’s","E-commerce"]:
   self.assertEqual(L.english_term(value),value)
  self.assertEqual(L.english_term(' “Content” '),'Content')
  for value in ['Content (เนื้อหา)','เนื้อหา','123','<script>','Content\nAgency']:
   self.assertIsNone(L.english_term(value))
 def test_invalid_english_keeps_original_after_retries(self):
  calls=[];warnings=[]
  def ask(*args):
   calls.append(1);return [{'index':0,'replacements':[{'source':'คอนเทนต์','english':'Content (เนื้อหา)','occurrence':1},{'source':'เอเจนซี่','english':'Agency','occurrence':1}]}]
  result,count=L.convert([(0,None,None,'คอนเทนต์กับเอเจนซี่')],{},ask,warnings)
  self.assertEqual(len(calls),1);self.assertEqual(result[0],'คอนเทนต์กับ Agency');self.assertEqual(count,1);self.assertEqual(len(warnings),1)

 def test_wrong_source_and_occurrence_skip_only_invalid(self):
  for bad in [{'source':'คอนเทนต์','english':'Content','occurrence':1},{'source':'เอเจนซี่','english':'Agency','occurrence':2},{'source':'เอเจนซี่','english':'Agency','occurrence':'1'},{'source':'เอเจนซี่','english':'Agency','occurrence':True},None]:
   good={'source':'เอเจนซี่','english':'Agency','occurrence':1}
   result,notes=L.reviewed_replacements('คอนเท้นต์กับเอเจนซี่',[bad,good])
   self.assertEqual(result,'คอนเท้นต์กับ Agency');self.assertTrue(notes)
 def test_conflicts_keep_all_conflicting_words_original(self):
  result,notes=L.reviewed_replacements('คอนเทนต์กับเอเจนซี่',[{'source':'คอนเทนต์','english':'Content','occurrence':1},{'source':'คอนเทนต์','english':'Context','occurrence':1},{'source':'เอเจนซี่','english':'Agency','occurrence':1}])
  self.assertEqual(result,'คอนเทนต์กับ Agency');self.assertTrue(notes)
 def test_all_invalid_keeps_exact_text(self):
  text='ไทยContent คอนเท้นต์'
  result,notes=L.reviewed_replacements(text,[{'source':'คอนเทนต์','english':'Content','occurrence':1}])
  self.assertEqual(result,text);self.assertTrue(notes)
 def test_bad_batch_keeps_original_without_partial_edits(self):
  warnings=[]
  result,count=L.convert([(7,None,None,'คอนเทนต์'),(19,None,None,'เอเจนซี่')],{},lambda *a:[{'index':7,'replacements':[{'source':'คอนเทนต์','english':'Content','occurrence':1}]}],warnings)
  self.assertEqual(result,{7:'คอนเทนต์',19:'เอเจนซี่'});self.assertEqual(count,0);self.assertTrue(warnings)
 def test_occurrence_is_per_caption_not_batch(self):
  warnings=[]
  result,count=L.convert([(7,None,None,'คอนเทนต์'),(19,None,None,'คอนเทนต์')],{},lambda *a:[{'index':7,'replacements':[{'source':'คอนเทนต์','english':'Content','occurrence':1}]},{'index':19,'replacements':[{'source':'คอนเทนต์','english':'Content','occurrence':2}]}],warnings)
  self.assertEqual(result,{7:'Content',19:'คอนเทนต์'});self.assertEqual(count,1);self.assertTrue(warnings)

 def test_mai_yamok_spaces_and_idempotence(self):
  for before,after in [('จริงๆแล้ว','จริง ๆ แล้ว'),('น้องๆทุกคน','น้อง ๆ ทุกคน'),('มากๆ','มาก ๆ'),('จริง ๆ แล้ว','จริง ๆ แล้ว'),('“จริงๆ”','“จริง ๆ”'),('จริงๆ\nน้องๆ','จริง ๆ\nน้อง ๆ')]:
   self.assertEqual(L.space_mai_yamok(before),after);self.assertEqual(L.space_mai_yamok(after),after)
 def test_report_identifies_word_original_time_and_occurrence(self):
  report=[];warnings=[]
  result,count=L.convert([(52,{'target_timerange':{'start':123450000}},None,'คอนเท้นต์')],{},lambda *a:[{'index':52,'replacements':[{'source':'คอนเทนต์','english':'Content','occurrence':1}]}],warnings,report)
  self.assertEqual(report[0]['source'],'คอนเทนต์');self.assertEqual(report[0]['original'],'คอนเท้นต์');self.assertEqual(report[0]['matches'],0);self.assertEqual(report[0]['start'],123.45);self.assertEqual(result[52],'คอนเท้นต์')
