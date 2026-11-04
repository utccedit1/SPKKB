"""Exercise actual render geometry, replacing only local frame extraction/detection."""
import copy,unittest
from unittest.mock import patch
from ks import assisted_framing as A,kinetic_text as K
from test_kinetic_text import cues,plan
from test_caption_presets import draft
FONT='/System/Library/Fonts/Supplemental/Arial.ttf'

class AssistedMotionReviewTests(unittest.TestCase):
 def setUp(self):
  import tempfile
  from pathlib import Path
  temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
  media=Path(temp.name)/'fixture.mp4';media.write_bytes(b'fixture')
  self.d=draft();self.d['duration']=6000000;self.d['canvas_config']=dict(width=1920,height=1080)
  self.d['materials']['videos']=[dict(id='video',path=str(media))]
  self.d['tracks'].insert(0,dict(type='video',segments=[dict(id='v',material_id='video',target_timerange=dict(start=0,duration=6000000),source_timerange=dict(start=0,duration=6000000),clip=dict(scale=dict(x=1,y=1),transform=dict(x=0,y=0)),speed=1,common_keyframes=[],extra_material_refs=[])]))
  self.plan=K.validate(plan(),cues());self.plan['blocks'][0]['camera_move']='smooth_in_out'
 def run_assist(self,observer):
  with patch.object(A,'_observe',side_effect=observer):return A.assist(self.d,self.plan,'/tmp',settings=dict(font=FONT,zone='left'))
 def test_clean_evidence_preserves_zoom_and_original_plan(self):
  before=copy.deepcopy(self.plan)
  out,report=self.run_assist(lambda *args:dict(faces=[],hands=[],complete=True))
  self.assertEqual(report['accepted'],1);self.assertEqual(out['blocks'][0]['camera_move'],'smooth_in_out')
  self.assertEqual(out['blocks'][0]['composition']['video_scale'],1);self.assertEqual(self.plan,before)
  self.assertGreater(report['records'][0]['checked_samples'],3)
 def test_hand_collision_at_midpoint_rejects_all_candidates(self):
  def observer(source,time,*args):return dict(faces=[],hands=[dict(x=0,y=0,width=1,height=1,confidence=.9)] if abs(time-3.5)<.001 else [],complete=True)
  out,report=self.run_assist(observer)
  self.assertEqual(report['accepted'],0);self.assertEqual(out,self.plan)
  self.assertTrue(any('hands overlap' in s for s in report['records'][0]['reasons']))
 def test_vision_unavailable_cannot_accept(self):
  _,report=self.run_assist(lambda *args:dict(faces=[],hands=[],complete=False))
  self.assertEqual(report['accepted'],0)
 def test_source_switch_remains_uncertain(self):
  from ks import caption_studio as S
  original=S.source_at
  def switched(d,t):
   result=original(d,t)
   if t>3:result['path']='/tmp/other-fixture.mp4'
   return result
  with patch.object(S,'source_at',side_effect=switched):
   _,report=self.run_assist(lambda *args:dict(faces=[],hands=[],complete=True))
  self.assertEqual(report['accepted'],0)
 def test_mid_zoom_knot_face_collision_is_not_skipped(self):
  times=[]
  def observer(source,time,*args):
   times.append(time)
   return dict(faces=[dict(x=0,y=0,width=1,height=1,confidence=.99)] if abs(time-3.5)<.001 else [],hands=[],complete=True)
  _,report=self.run_assist(observer)
  self.assertEqual(report['accepted'],0);self.assertIn(3.5,times)
  self.assertTrue(any('faces overlap' in s for s in report['records'][0]['reasons']))
 def test_cached_frames_are_not_reextracted_for_each_candidate(self):
  times=[]
  def observer(source,time,*args):
   times.append(time);return dict(faces=[],hands=[],complete=False)
  self.run_assist(observer)
  self.assertEqual(len(times),len(set(times)))
 def test_snap_hold_observations_extend_beyond_text_until_cut(self):
  self.plan['blocks'][0]['camera_move']='snap_to_cut'
  times=[]
  def observer(source,time,*args):
   times.append(time)
   return dict(faces=[dict(x=.9,y=.4,width=.09,height=.1,confidence=.99)] if time>=5.5 else [],hands=[],complete=True)
  _,report=self.run_assist(observer)
  self.assertGreater(max(times),5)
  self.assertEqual(report['accepted'],0)
 def test_automatic_opt_in_static_fallback_reports_face_clipping_adjustment(self):
  def observer(*args):return dict(faces=[dict(x=.89,y=.6,width=.09,height=.1,confidence=.99)],hands=[],complete=True)
  out,report=self.run_assist(observer)
  self.assertEqual(report['accepted'],0);self.assertEqual(out,self.plan)
  with patch.object(A,'_observe',side_effect=observer):
   out,report=A.assist(self.d,self.plan,'/tmp',settings=dict(font=FONT,zone='left'),allow_motion_fallback=True)
  self.assertEqual(report['accepted'],1);self.assertEqual(out['blocks'][0]['camera_move'],'static')
  self.assertEqual(report['motion_adjustments'],1);self.assertEqual(report['records'][0]['motion_adjusted_from'],'smooth_in_out')
 def test_free_opposite_anchor_keeps_zoom_even_with_fallback_enabled(self):
  def observer(*args):return dict(faces=[dict(x=.68,y=.2,width=.1,height=.2,confidence=.99)],hands=[],complete=True)
  with patch.object(A,'_observe',side_effect=observer):
   out,report=A.assist(self.d,self.plan,'/tmp',settings=dict(font=FONT,zone='left'),allow_motion_fallback=True)
  self.assertEqual(report['accepted'],1);self.assertEqual(report['motion_adjustments'],0)
  self.assertEqual(out['blocks'][0]['camera_move'],'smooth_in_out')
 def test_static_fallback_still_requires_original_hold_evidence(self):
  self.plan['blocks'][0]['camera_move']='snap_to_cut'
  def observer(source,time,*args):
   return dict(faces=[dict(x=.89,y=.6,width=.09,height=.1,confidence=.99)],hands=[],complete=time<5.5)
  with patch.object(A,'_observe',side_effect=observer):
   out,report=A.assist(self.d,self.plan,'/tmp',settings=dict(font=FONT,zone='left'),allow_motion_fallback=True)
  self.assertEqual(report['accepted'],0);self.assertEqual(out,self.plan)
  self.assertEqual(report['records'][0]['interval'],[2,6])
