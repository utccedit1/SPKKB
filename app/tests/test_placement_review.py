"""Collision evidence must follow motion and reject incomplete observations."""
import unittest
from ks import placement_review as P
FONT='/System/Library/Fonts/Supplemental/Arial.ttf'

class PlacementReviewTests(unittest.TestCase):
 def setUp(self):
  self.entry=dict(text='WWW',x=.6,y=0,size=5,scale=1,start=0,end=1)
  self.canvas=dict(width=1000,height=1000)
 def observations(self,**changes):
  return [dict(time=t,faces=[],hands=[],camera='one',complete=True,**changes) for t in (0,.5,1)]
 def check_review(self,obs,scenes=None):return P.review([self.entry],scenes or [],obs,self.canvas,FONT)
 def test_clean_area_and_measured_font_width(self):
  obs=self.observations();obs[1]['faces']=[dict(x=.74,y=.49,width=.02,height=.02,confidence=.99)]
  self.assertFalse(self.check_review(obs)['safe']) # WWW extends left from its .8 center to .729
  self.entry['text']='iii'
  self.assertTrue(self.check_review(obs)['safe'])
 def test_mid_zoom_face_collision(self):
  obs=self.observations()
  for o in obs:o['faces']=[dict(x=.64,y=.48,width=.02,height=.04,confidence=.99)]
  self.assertTrue(self.check_review(obs)['safe'])
  scene=dict(start=0,end=1,x=0,y=0,scale_from=1,scale_to=1,scale_points=[[0,1],[.5,2],[1,1]])
  self.assertFalse(self.check_review(obs,[scene])['safe'])
 def test_hand_collision(self):
  obs=self.observations();obs[1]['hands']=[dict(x=.78,y=.49,width=.04,height=.03,confidence=.9)]
  self.assertFalse(self.check_review(obs)['safe'])
 def test_missing_or_incomplete_sample_is_not_safe(self):
  self.assertFalse(self.check_review(self.observations()[:2])['safe'])
  obs=self.observations();obs[1]['complete']=False
  self.assertFalse(self.check_review(obs)['safe'])
 def test_camera_change_requires_separate_review(self):
  obs=self.observations();obs[1]['camera']='two'
  self.assertFalse(self.check_review(obs)['safe'])
 def test_schedule_includes_knots_cut_sides_and_limits(self):
  times=P.sample_schedule(0,1,[dict(start=0,end=1,scale_points=[[.33,1.3]])],[.7])
  self.assertIn(.33,times);self.assertTrue(any(.66<t<.7 for t in times));self.assertTrue(any(.7<t<.74 for t in times))
  with self.assertRaises(ValueError):P.sample_schedule(0,91)
 def test_unmeasured_font_never_certifies(self):
  self.assertFalse(P.review([self.entry],[],self.observations(),self.canvas,'')['safe'])
 def test_invalid_animation_and_scale_fail_closed(self):
  for field,value in [('scale',-1),('points',[dict(scale=float('nan'),dx=0,dy=0)])]:
   self.entry[field]=value
   self.assertFalse(self.check_review(self.observations())['safe'])
   self.entry.pop(field)
 def test_entrance_envelope_and_outline_are_checked(self):
  self.entry.update(text='iii',points=[dict(scale=4,dx=0,dy=0)])
  obs=self.observations();obs[1]['hands']=[dict(x=.74,y=.49,width=.02,height=.02,confidence=.9)]
  self.assertFalse(self.check_review(obs)['safe'])
 def test_exclusive_endpoint_uses_scene_left_limit(self):
  self.entry.update(text='iii')
  obs=self.observations()
  obs[-1]['faces']=[dict(x=.64,y=.49,width=.02,height=.02,confidence=.99)]
  scene=dict(start=0,end=1,x=0,y=0,scale_from=1,scale_to=2)
  self.assertFalse(self.check_review(obs,[scene])['safe'])
 def test_invalid_scene_transform_cannot_hide_collision(self):
  scene=dict(start=0,end=1,x=float('nan'),y=0,scale_from=1,scale_to=1)
  obs=self.observations();obs[1]['hands']=[dict(x=.78,y=.49,width=.04,height=.03,confidence=.9)]
  self.assertFalse(self.check_review(obs,[scene])['safe'])
 def test_motion_hold_after_text_requires_complete_inframe_face_evidence(self):
  self.entry.update(start=1,end=2,text='iii')
  scene=dict(start=1,end=6,x=0,y=0,scale_from=2,scale_to=2)
  obs=[dict(time=1+i*.5,faces=[],hands=[],camera='one',complete=True) for i in range(11)]
  self.assertTrue(self.check_review(obs,[scene])['safe'])
  obs[8]['faces']=[dict(x=.8,y=.4,width=.1,height=.1,confidence=.99)]
  self.assertFalse(self.check_review(obs,[scene])['safe'])
  obs[8]['faces']=[];obs[8]['complete']=False
  self.assertFalse(self.check_review(obs,[scene])['safe'])
 def test_hand_overlap_after_text_has_gone_does_not_reject_motion(self):
  self.entry.update(start=1,end=2,text='iii')
  scene=dict(start=1,end=6,x=0,y=0,scale_from=1,scale_to=1)
  obs=[dict(time=1+i*.5,faces=[],hands=[],camera='one',complete=True) for i in range(11)]
  obs[8]['hands']=[dict(x=.78,y=.49,width=.04,height=.03,confidence=.9)]
  self.assertTrue(self.check_review(obs,[scene])['safe'])

class EntranceEnvelopeTests(unittest.TestCase):
 setUp=PlacementReviewTests.setUp
 observations=PlacementReviewTests.observations
 check_review=PlacementReviewTests.check_review
 def test_pop_overshoot_is_checked_even_when_settled_text_is_clear(self):
  obs=self.observations();obs[1]['faces']=[dict(x=.88,y=.49,width=.005,height=.02,confidence=.99)]
  self.assertTrue(self.check_review(obs)['safe']);self.entry['motion']='pop';self.assertFalse(self.check_review(obs)['safe'])
 def test_slide_checks_entrance_path_not_only_final_anchor(self):
  obs=self.observations();obs[1]['faces']=[dict(x=.7,y=.49,width=.01,height=.02,confidence=.99)]
  self.assertTrue(self.check_review(obs)['safe']);self.entry['motion']='slide';self.assertFalse(self.check_review(obs)['safe'])
 def test_unknown_motion_cannot_be_certified(self):
  self.entry['motion']='glitch';self.assertFalse(self.check_review(self.observations())['safe'])
