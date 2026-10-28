import pathlib,sys,unittest
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from ks import event_clip as E
class TranslationTests(unittest.TestCase):
 def setUp(self):
  self.rows=[{'id':7,'start':1,'end':3,'text':'We create','speaker':''},{'id':8,'start':3,'end':5,'text':'better opportunities.','speaker':''}]
  self.translation={'first_id':7,'last_id':8,'translation_th':'เราสร้างโอกาสที่ดีขึ้น','about_th':'การสร้างโอกาส'}
 def test_complete_sentence_uses_source_times(self):
  out=E.validated_translations([dict(self.translation,start=999)],self.rows)[0]
  self.assertEqual(out['start'],1);self.assertEqual(out['end'],5);self.assertEqual(out['source_text'],'We create better opportunities.')
 def test_uncertainty_preserved_and_shown_as_provisional(self):
  note='ซับต้นฉบับไม่ชัด กรุณาฟังเสียงยืนยัน'
  out=E.validated_translations([dict(self.translation,uncertainty_note_th=note)],self.rows)[0]
  self.assertEqual(out['uncertainty_note_th'],note)
  from ks.event_clip_ui import EVENT_UI
  self.assertIn('คำแปลเบื้องต้น (ต้องฟังยืนยัน)',EVENT_UI)
 def test_invalid_and_missing_coverage(self):
  for data in [[],[dict(self.translation,last_id=99)],[dict(self.translation,last_id=7)],[self.translation,self.translation],[dict(self.translation,first_id=True)],[dict(self.translation,translation_th='English only')]]:
   with self.subTest(data=data),self.assertRaises(ValueError):E.validated_translations(data,self.rows)
 def test_analyze_bilingual_same_request(self):
  response=[{'summary':'Creating opportunities','keywords':['opportunities'],'translations':[self.translation]}]
  with patch.object(E,'transcript',return_value=({},self.rows,'hash')),patch.object(E,'ask',return_value=response) as ask:
   out=E.analyze('translation-fixture',{'translate_th':True,'refresh_analysis':True})
  self.assertEqual(ask.call_count,1);self.assertIn('SOURCE_ROWS',ask.call_args.args[0]);self.assertEqual(out['topics'][0]['translations'][0]['translation_th'],'เราสร้างโอกาสที่ดีขึ้น')
 def test_disabled_needs_no_translation(self):
  with patch.object(E,'transcript',return_value=({},self.rows,'hash')),patch.object(E,'ask',return_value=[{'summary':'Creating opportunities','keywords':[]}]) as ask:
   out=E.analyze('translation-fixture',{'refresh_analysis':True})
  self.assertNotIn('SOURCE_ROWS',ask.call_args.args[0]);self.assertEqual(out['topics'][0]['translations'],[])
 def test_retries_bad_reference_without_extra_translate_call(self):
  bad=[{'summary':'Opportunities','translations':[dict(self.translation,last_id=999)]}]
  good=[{'summary':'Opportunities','translations':[self.translation]}]
  with patch.object(E,'transcript',return_value=({},self.rows,'hash')),patch.object(E,'ask',side_effect=[bad,good]) as ask:
   out=E.analyze('translation-retry-fixture',{'translate_th':True,'refresh_analysis':True})
  self.assertEqual(ask.call_count,2);self.assertEqual(out['topics'][0]['translations'][0]['last_id'],8)
 def test_incomplete_translation_fails_before_result(self):
  with patch.object(E,'transcript',return_value=({},self.rows,'hash')),patch.object(E,'ask',return_value=[{'summary':'Opportunities','translations':[]}]):
   with self.assertRaisesRegex(ValueError,'คำแปลรายท่อน'):E.analyze('translation-failed-fixture',{'translate_th':True,'refresh_analysis':True})
 def test_translation_cache_separate_and_reused(self):
  with patch.object(E,'transcript',return_value=({},self.rows,'hash')),patch.object(E,'ask',side_effect=[[{'summary':'English'}],[{'summary':'English','translations':[self.translation]}]]) as ask:
   E.analyze('translation-cache-fixture',{})
   first=E.analyze('translation-cache-fixture',{'translate_th':True})
   second=E.analyze('translation-cache-fixture',{'translate_th':True})
  self.assertEqual(ask.call_count,2);self.assertTrue(second['cached']);self.assertEqual(first['topics'],second['topics'])
if __name__=='__main__':unittest.main()
