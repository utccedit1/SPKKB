import unittest
from ks import kinetic_display as D
class DisplayTests(unittest.TestCase):
 def test_percentages_use_digits_without_inventing_missing_unit(self):
  self.assertEqual(D.display('ยี่สิบเปอร์เซ็นต์'),'20%')
  self.assertEqual(D.display('สิบเปอร์เซ็นต์หรือห้าเปอร์เซ็นต์'),'10%หรือ5%')
  self.assertEqual(D.display('สิบห้า',percentage_context=True),'15')
  self.assertEqual(D.display('สิบห้า'),'สิบห้า')
 def test_longest_number_and_real_source_words_are_preserved(self):
  self.assertEqual(D.display('สามสิบเปอร์เซ็นต์บ้าง'),'30%บ้าง')
  self.assertEqual(D.display('รอบที่หนึ่ง'),'รอบที่หนึ่ง')
  self.assertEqual(D.display('หนึ่งร้อยยี่สิบเปอร์เซ็นต์'),'หนึ่งร้อยยี่สิบเปอร์เซ็นต์')
  self.assertIsNone(D.numeric_parts('สี่สิบเปอร์เซ็นต์'))
  self.assertEqual(D.display('เพื่อทำภารกิจให้สำเร็จ'),'เพื่อทำภารกิจให้สำเร็จ')
 def test_render_changes_only_display_not_source_and_removes_solid_boxes(self):
  import copy,json
  from test_caption_presets import draft
  from ks import kinetic_full as F,kinetic_text as K,kinetic_design as V
  d=draft();d['tracks'][0]['segments']=d['tracks'][0]['segments'][:1]
  d['tracks'][0]['segments'][0]['target_timerange']=dict(start=0,duration=3000000);d['duration']=3000000
  d['materials']['texts'][0]['content']=json.dumps(dict(text='สามสิบเปอร์เซ็นต์บ้างยี่สิบเปอร์เซ็นต์สิบห้า',styles=[]))
  plan=F.plan(d);before=copy.deepcopy(plan)
  self.assertEqual(plan['blocks'][0]['form'],'numeric')
  out,report=K.render(d,plan,font='')
  self.assertEqual(plan,before);self.assertEqual([e['text'] for e in report['entries']],['30%','20%','15'])
  self.assertTrue(all(not e['background'] for e in report['entries']))
  self.assertEqual(len({e['y'] for e in report['entries']}),1)
  self.assertEqual(len({e['size'] for e in report['entries']}),1)
  self.assertEqual(V.validate_saved(plan,d)['blocks'][0]['form'],'numeric')
 def test_decimal_negation_and_unsupported_range_are_not_flattened_into_tiles(self):
  for text in ('สิบเปอร์เซ็นต์เหลือศูนย์จุดห้าเปอร์เซ็นต์','สิบเปอร์เซ็นต์ไม่ใช่ยี่สิบเปอร์เซ็นต์','สิบเปอร์เซ็นต์ถึงสี่สิบเปอร์เซ็นต์'):
   self.assertIsNone(D.numeric_parts(text))
  self.assertEqual(D.display('ศูนย์จุดห้าเปอร์เซ็นต์'),'ศูนย์จุดห้าเปอร์เซ็นต์')
 def test_full_plan_split_cannot_turn_120_percent_into_20_percent(self):
  import json
  from test_caption_presets import draft
  from ks import kinetic_full as F,kinetic_text as K
  d=draft();d['tracks'][0]['segments']=d['tracks'][0]['segments'][:1];d['duration']=3000000;d['tracks'][0]['segments'][0]['target_timerange']=dict(start=0,duration=3000000)
  d['materials']['texts'][0]['content']=json.dumps(dict(text='หนึ่งร้อยยี่สิบเปอร์เซ็นต์',styles=[]))
  _,report=K.render(d,F.plan(d),font='',zone='upper')
  self.assertNotIn('20%',''.join(e['text'] for e in report['entries']))
