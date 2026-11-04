import copy,unittest
from ks import kinetic_styles as S

def beat(i,text,form='matched',role='detail',start=None):
 return dict(cue_id=str(i),form=form,editorial_role=role,enabled=True,framing='keep',units=[dict(text=text,start=i*3 if start is None else start,end=(i*3 if start is None else start)+2,motion='rise')])
class EditorialRhythmTests(unittest.TestCase):
 def test_detail_beats_rest_while_contrast_and_payoff_are_retained(self):
  p=dict(blocks=[beat(0,'รายละเอียดการเตรียมเอกสาร'),beat(1,'ไม่ใช่ราคาแต่เป็นคุณค่า','contrast','contrast'),beat(2,'ข้อมูลประกอบเพิ่มเติม'),beat(3,'ทำภารกิจให้สำเร็จ','matched','result')]);before=copy.deepcopy(p)
  out=S.apply(p,'story');self.assertEqual([b['enabled'] for b in out['blocks']],[False,True,False,True]);self.assertEqual(out['blocks'][1]['camera_move'],'snap_to_cut');self.assertEqual(p,before)
 def test_repeated_phrase_does_not_pulse_again_within_same_thought(self):
  p=dict(blocks=[beat(0,'ประหยัด 30%','numeric','numeric'),beat(1,'ประหยัด 30%','numeric','numeric'),beat(4,'ผลลัพธ์ที่ดีขึ้น','matched','result')]);out=S.apply(p,'impact')
  self.assertTrue(out['blocks'][0]['enabled']);self.assertFalse(out['blocks'][1]['enabled']);self.assertTrue(out['blocks'][2]['enabled']);self.assertTrue(out['blocks'][1]['editorial_reason'])
 def test_close_low_value_beat_yields_to_nearby_number(self):
  p=dict(blocks=[beat(0,'คำถามที่ควรคิด','question','question',start=1),beat(1,'ลดลง 20%','numeric','numeric',start=2)]);out=S.apply(p,'story')
  self.assertEqual([b['enabled'] for b in out['blocks']],[False,True])
 def test_original_preserves_every_manual_decision(self):
  p=dict(blocks=[beat(0,'ข้อมูลประกอบ')]);p['blocks'][0].update(enabled=False,camera_move='cinematic');self.assertEqual(S.apply(p,'original')['blocks'],p['blocks'])

class MeasuredRhythmTests(unittest.TestCase):
 def test_spacing_uses_selected_phrase_onset_not_paragraph_start(self):
  from ks import kinetic_jobs as J
  import json
  d=dict(materials=dict(texts=[dict(id='a',type='subtitle',content=json.dumps(dict(text='รายละเอียดทั่วไปผลลัพธ์ดีขึ้น',styles=[]))),dict(id='b',type='subtitle',content=json.dumps(dict(text='ลดลง 20%',styles=[])))]),tracks=[dict(type='text',segments=[dict(id='one',material_id='a',target_timerange=dict(start=0,duration=10000000)),dict(id='two',material_id='b',target_timerange=dict(start=10000000,duration=2000000))])])
  d['tracks'].append(dict(type='video',segments=[dict(target_timerange=dict(start=0,duration=12000000))]))
  p=dict(blocks=[dict(cue_id='one',form='matched',editorial_role='result',enabled=True,units=[dict(text='ผลลัพธ์ดีขึ้น',start=0,end=10,motion='rise')]),dict(cue_id='two',form='numeric',editorial_role='numeric',enabled=True,units=[dict(text='ลดลง 20%',start=10,end=12,motion='rise')])])
  settings=dict(style='story',caption_one_line=True,caption_phrases={'one':[dict(text='รายละเอียดทั่วไป',start=0,end=9),dict(text='ผลลัพธ์ดีขึ้น',start=9,end=10)]})
  out=J._style_plan(d,p,settings)
  self.assertEqual([b['enabled'] for b in out['blocks']],[False,True])

class NearbyCutRhythmTests(unittest.TestCase):
 def test_recipe_holds_to_near_cut_but_does_not_hold_for_a_minute(self):
  from ks import kinetic_jobs as J
  from test_kinetic_scene import SceneTests
  p=dict(blocks=[beat(0,'ผลลัพธ์ดีขึ้น','punch','result',start=3)])
  d=SceneTests().fixture();seg=d['tracks'][0]['segments'][0];seg['target_timerange']['duration']=60000000;d['duration']=60000000
  out=J._style_plan(d,p,dict(style='impact'));self.assertEqual(out['blocks'][0]['camera_move'],'snap_in_out')
  seg['target_timerange']['duration']=8000000;d['duration']=8000000
  self.assertEqual(J._style_plan(d,p,dict(style='impact'))['blocks'][0]['camera_move'],'snap_to_cut')
  p['blocks'][0]['camera_move']='snap_to_cut';self.assertEqual(J._style_plan(d,p,dict(style='original'))['blocks'][0]['camera_move'],'snap_to_cut')
