import unittest
from ks import kinetic_styles as S
class StyleTests(unittest.TestCase):
 def plan(self):
  return dict(blocks=[dict(cue_id=str(i),form=f,enabled=True,framing='keep',units=[dict(text='คำจริง',start=i*3,end=i*3+2,motion='rise',tone='accent',weight='hero',row=0)]) for i,f in enumerate(['stack','question','punch','numeric'])])
 def test_styles_change_density_and_motion_without_changing_source(self):
  p=self.plan();clean=S.apply(p,'clean');impact=S.apply(p,'impact')
  self.assertLess(sum(b['enabled'] for b in clean['blocks']),sum(b['enabled'] for b in impact['blocks']))
  self.assertEqual(impact['blocks'][2]['camera_move'],'snap_to_cut')
  self.assertEqual(impact['blocks'][2]['units'][0]['text'],'คำจริง')
  self.assertEqual(impact['blocks'][2]['units'][0]['start'],6)
  self.assertNotIn('camera_move',p['blocks'][2])
 def test_unknown_style_rejected(self):
  with self.assertRaises(ValueError):S.apply(self.plan(),'anything')

 def test_clean_long_explanation_keeps_one_reviewable_beat(self):
  p=self.plan()
  for b in p['blocks']:b['form']='stack'
  result=S.apply(p,'clean')
  self.assertTrue(any(b['enabled'] for b in result['blocks']))

class StyleRouteTests(unittest.TestCase):
 from test_kinetic_text import KineticServiceTests as _Fixture
 setUp=_Fixture.setUp
 def test_ai_route_does_not_silently_ignore_whole_clip_recipe(self):
  from ks import kinetic_jobs as J,cli_lab_webhook as W
  from unittest.mock import patch
  meta=J.handle('alice',self.proj,dict(action='kinetic_meta'))
  with patch.object(W,'request',side_effect=AssertionError('must reject before provider')),self.assertRaisesRegex(ValueError,'ทั้งคลิป'):
   J.handle('alice',self.proj,dict(action='kinetic_plan',ids=['one'],style='impact',source_hash=meta['source_hash'],media_hash=meta['media_hash']))

class StyleCutMotionTests(unittest.TestCase):
 def test_matched_impact_holds_past_text_until_existing_cut(self):
  from ks import kinetic_scene as C
  from test_kinetic_scene import SceneTests
  p=dict(blocks=[dict(cue_id='a',form='matched',framing='keep',enabled=True,units=[dict(text='เพื่อทำ',start=1,end=2,motion='rise'),dict(text='ภารกิจให้สำเร็จ',start=1.5,end=2,motion='rise')])])
  result=S.apply(p,'impact');scenes=C.scenes(result['blocks'],SceneTests().fixture())
  self.assertEqual(len(scenes),1)
  self.assertEqual(scenes[0]['end'],6)
  self.assertAlmostEqual(C.frame(scenes[0],1.3)['scale'],1.3)
  self.assertAlmostEqual(C.frame(scenes[0],5.9)['scale'],1.3)
  self.assertEqual(p['blocks'][0]['units'][1]['text'],'ภารกิจให้สำเร็จ')
  self.assertEqual(C.scenes(S.apply(p,'clean')['blocks']),[])
  self.assertEqual(S.apply(p,'original')['blocks'],p['blocks'])
