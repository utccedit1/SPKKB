import unittest
from ks.cli_lab_planning import complete_boundaries, stock_tokens, duration_feedback, validate_complete_boundaries, validation_summary
class PlanningRepairTests(unittest.TestCase):
 def test_rejects_real_speech_fragments_at_caption_boundaries(self):
  cases=[('ฝ่ายขายกับการตลาดมีความเข้าใจ', 'ในเป้าหมายของงานอีเวนต์ยังแตกต่างกัน'),
         ('บริษัทจ้างเราเพราะเราจะช่วยคิด', 'น่ะเราจะช่วยการคิดให้ลูกค้าด้วย')]
  for before, after in cases:
   captions=[dict(start=0,end=10,text=before,sources=['speaker']),
             dict(start=10.6,end=15,text=after,sources=['speaker'])]
   with self.subTest(after=after), self.assertRaisesRegex(ValueError,'เริ่มกลางความคิด'):
    validate_complete_boundaries({'cuts':[{'first_id':1,'last_id':1}]}, captions)
 def test_validation_summary_is_useful_without_echoing_private_error(self):
  self.assertIn('ความยาว',validation_summary(ValueError('ความยาวรวม 200 วินาที private fixture')))
  self.assertIn('รอยต่อ',validation_summary(ValueError('ช่วงตัดจบกลางประโยค private fixture')))
  self.assertIn('เรื่องเล่า',validation_summary(ValueError('ช่วงที่เลือกยังไม่เป็นเรื่องเดียวกัน private fixture')))
  self.assertNotIn('private fixture',validation_summary(ValueError('private fixture')))
 def test_rejects_known_incomplete_thai_ending_with_continuation(self):
  captions=[dict(start=0,end=10,text='น้องอาจจะมองเห็นภาพว่า'),dict(start=10.6,end=18,text='เราจะโปรโมทสินค้าอย่างไรได้บ้าง')]
  with self.assertRaisesRegex(ValueError,'ต่อความคิด'):
   validate_complete_boundaries({'cuts':[{'last_id':0}]},captions)
  validate_complete_boundaries({'cuts':[{'last_id':1}]},captions)
  captions[1]['start']=20
  validate_complete_boundaries({'cuts':[{'last_id':0}]},captions)
 def test_rejects_newly_observed_unfinished_lead_ins(self):
  for ending in ('ข้อที่สองก็คือ','มองย้อนกลับกันนะคะทีนี้'):
   captions=[dict(start=0,end=10,text=ending),dict(start=10.5,end=15,text='ต่อคำอธิบาย')]
   with self.subTest(ending=ending),self.assertRaisesRegex(ValueError,'ต่อความคิด'):
    validate_complete_boundaries({'cuts':[{'last_id':0}]},captions)
 def test_rejects_real_highlight_split_between_data_and_qualifier(self):
  captions=[dict(start=224.10,end=239.67,text='เราจะวัดผลมันยังไงการวัดผลมันเป็นการวัดผลด้วยข้อมูล',sources=['interview']),dict(start=240.90,end=249.0,text='ที่จับต้องได้แล้วเราก็จะต้องออกแบบเครื่องมือ',sources=['interview'])]
  with self.assertRaisesRegex(ValueError,'จบกลางประโยค'):
   validate_complete_boundaries({'cuts':[{'first_id':0,'last_id':0}]},captions)
  captions[1]['sources']=['other']
  validate_complete_boundaries({'cuts':[{'first_id':0,'last_id':0}]},captions)
 def test_rejects_unfulfilled_three_question_promise(self):
  captions=[dict(start=i*5,end=i*5+4,text=text,sources=['interview']) for i,text in enumerate((
   'คิดสามคำถามง่ายง่าย', 'ข้อที่หนึ่งมีเป้าหมายอะไร', 'การวัดผลด้วยข้อมูล',
   'ข้อที่สองเลือกทีมอย่างไร', 'ข้อที่สามใช้งบเท่าไหร่'))]
  with self.assertRaisesRegex(ValueError,'สามคำถาม'):
   validate_complete_boundaries({'cuts':[{'first_id':0,'last_id':2}]},captions)
  with self.assertRaisesRegex(ValueError,'สามคำถาม'):
   validate_complete_boundaries({'cuts':[{'first_id':1,'last_id':2},{'first_id':4,'last_id':4}]},captions)
  validate_complete_boundaries({'cuts':[{'first_id':0,'last_id':1},{'first_id':3,'last_id':4}]},captions)
  validate_complete_boundaries({'cuts':[{'first_id':1,'last_id':2}]},captions)
 def test_rejects_cut_after_unfinished_hypothetical_or_before_purpose_clause(self):
  captions=[
   dict(id=0,start=0,end=15,text='ก่อนบรีฟอยากให้ตั้งคำถามสำคัญ',sources=['s1']),
   dict(id=1,start=15.5,end=30,text='สำหรับการจัดอีเวนต์นึงนะว่าเป้าหมายคืออะไร',sources=['s1']),
   dict(id=2,start=30.5,end=40,text='ที่จับต้องได้แล้วเราก็ต้องออกแบบเครื่องมือสมมุติว่าน้องอยากได้',sources=['s1']),
   dict(id=3,start=41.0,end=55,text='เอ็นเกจเมนต์น้องอาจต้องสร้างคิวอาร์โค้ดเตรียมรอไว้',sources=['s1']),
  ]
  with self.assertRaisesRegex(ValueError,'เริ่มกลางความคิด'):
   validate_complete_boundaries({'cuts':[{'first_id':1,'last_id':3}]},captions)
  with self.assertRaisesRegex(ValueError,'จบกลางประโยค'):
   validate_complete_boundaries({'cuts':[{'first_id':0,'last_id':2}]},captions)
  fixed=complete_boundaries({'cuts':[{'first_id':1,'last_id':2,'role':'hook'}]},captions,90)
  self.assertEqual((fixed['cuts'][0]['first_id'],fixed['cuts'][0]['last_id']),(0,3))
 def test_rejects_missing_subject_and_unfinished_no_matter_clause(self):
  captions=[dict(start=0,end=3,text='สิ่งสำคัญนี้'),dict(start=3.5,end=8,text='ไม่เคยเปลี่ยนไปเลยก็คือต้องตอบโจทย์'),dict(start=8.5,end=12,text='ทำได้ไม่ว่าเงินจะแค่ไหน'),dict(start=12.5,end=15,text='ก็ต้องคุยกันก่อน')]
  with self.assertRaisesRegex(ValueError,'เริ่มกลางความคิด'):
   validate_complete_boundaries({'cuts':[{'first_id':1,'last_id':2}]},captions)
  with self.assertRaisesRegex(ValueError,'จบกลางประโยค'):
   validate_complete_boundaries({'cuts':[{'first_id':0,'last_id':2}]},captions)
 def test_exact_phrase_and_punctuation_repair_without_mutating_input(self):
  raw={'stock_requests':[{'query':'Office, paper-documents','required_terms':['paper documents'],'alternatives':[{'query':'office desk','required_terms':['OFFICE']}]}]}
  result=stock_tokens(raw)['stock_requests'][0]
  self.assertEqual(result['required_terms'],['paper','documents']);self.assertEqual(result['query'],'Office paper documents')
  self.assertEqual(result['alternatives'][0]['required_terms'],['office']);self.assertEqual(raw['stock_requests'][0]['query'],'Office, paper-documents')
 def test_mismatched_essential_concept_never_removed(self):
  raw={'stock_requests':[{'query':'office desk','required_terms':['university']}]}
  self.assertEqual(stock_tokens(raw),raw)
 def test_realistic_over_budget_feedback(self):
  captions=[dict(start=0,end=200),dict(start=200,end=392.72)]
  report=duration_feedback({'cuts':[dict(first_id=0,last_id=0),dict(first_id=1,last_id=1)]},captions,300,360)
  self.assertEqual(report['actual_total_seconds'],392.72);self.assertEqual(report['seconds_over_maximum'],32.72);self.assertEqual(report['target_seconds'],330)
 def test_highlight_feedback_does_not_require_every_source(self):
  captions=[dict(start=0,end=10)]
  report=duration_feedback({'cuts':[]},captions,5,10,require_all=False)
  self.assertNotIn('all sources',report['instruction'])
  self.assertIn('all sources',duration_feedback({'cuts':[]},captions,5,10)['instruction'])

class BoundaryFeedbackTests(unittest.TestCase):
 def test_detects_opening_continuation_after_same_source(self):
  captions=[dict(start=0,end=4,text='การสื่อสารสำคัญ',sources=['s1']),dict(start=4.5,end=8,text='เพราะฉะนั้นต้องรู้จักลูกค้า',sources=['s1'])]
  with self.assertRaisesRegex(ValueError,'เริ่มกลางความคิด'):
   validate_complete_boundaries({'cuts':[{'first_id':1,'last_id':1}]},captions)
 def test_allows_new_source_and_long_pause(self):
  captions=[dict(start=0,end=4,text='สรุปประเด็น',sources=['s1']),dict(start=4.5,end=8,text='เพราะฉะนั้นต้องรู้จักลูกค้า',sources=['s2'])]
  validate_complete_boundaries({'cuts':[{'first_id':1,'last_id':1}]},captions)
  captions[1]['sources']=['s1'];captions[1]['start']=8
  validate_complete_boundaries({'cuts':[{'first_id':1,'last_id':1}]},captions)
 def test_feedback_explains_boundary_with_adjacent_original_caption_and_time(self):
  captions=[dict(start=0,end=4,text='ประเด็นก่อนหน้า'),dict(start=4.5,end=8,text='เพราะฉะนั้นต้องรู้จักลูกค้า'),dict(start=8.5,end=12,text='ต่อเรื่อง')]
  feedback=duration_feedback({'cuts':[dict(first_id=1,last_id=1)]},captions,5,10)
  self.assertEqual(feedback['boundary_context'][0]['previous']['id'],0)
  self.assertEqual(feedback['boundary_context'][0]['next']['id'],2)
  self.assertEqual(feedback['boundary_context'][0]['previous']['text'],'ประเด็นก่อนหน้า')
  self.assertEqual(feedback['boundary_context'][0]['previous']['end'],4)
 def test_complete_boundaries_extends_whole_adjacent_captions_without_touching_timestamps(self):
  captions=[
   dict(id=0,start=0,end=15,text='ขั้นแรกของการวางแผน',sources=['s1']),
   dict(id=1,start=15.5,end=35,text='เพราะฉะนั้นเราต้องดูว่า',sources=['s1']),
   dict(id=2,start=35.4,end=55,text='การวัดผลมันเป็นการวัดผลด้วยข้อมูล',sources=['s1']),
   dict(id=3,start=55.8,end=72,text='ที่จับต้องได้และนำไปปรับทีมต่อ',sources=['s1']),
   dict(id=4,start=73,end=90,text='สรุปบทเรียนของงานนี้',sources=['s1']),
  ]
  snapshot=[dict(c) for c in captions]
  raw={'cuts':[{'first_id':1,'last_id':2,'role':'hook'},{'first_id':4,'last_id':4,'role':'conclusion'}]}
  fixed=complete_boundaries(raw,captions,90)
  self.assertEqual(fixed['cuts'][0]['first_id'],0)
  self.assertEqual(fixed['cuts'][0]['last_id'],3)
  validate_complete_boundaries(fixed,captions)
  self.assertEqual(captions,snapshot)
 def test_complete_boundaries_respects_allowed_set_and_duration_ceiling(self):
  captions=[
   dict(id=0,start=0,end=30,text='ประเด็นตั้งต้นที่ทำให้เราคิดว่า',sources=['s1']),
   dict(id=1,start=30.5,end=65,text='คำอธิบายส่วนขยายที่ยาวเกินเพดาน',sources=['s1']),
   dict(id=2,start=66,end=90,text='สรุปจบครบถ้วน',sources=['s1']),
  ]
  raw={'cuts':[{'first_id':0,'last_id':0,'role':'hook'},{'first_id':2,'last_id':2,'role':'conclusion'}]}
  # Extending cut 0 to include id=1 would push total from 54s to 89s > high=80s -> must NOT extend!
  fixed=complete_boundaries(raw,captions,80)
  self.assertEqual(fixed['cuts'][0]['last_id'],0)
  with self.assertRaisesRegex(ValueError,'ต่อความคิด'):
   validate_complete_boundaries(fixed,captions)
