import unittest
from ks import assisted_framing as A
class FaceFramingTests(unittest.TestCase):
 def test_only_confident_consistent_single_faces_produce_bounded_geometry(self):
  face=dict(x=.35,y=.15,width=.12,height=.2,confidence=.99)
  result=A.propose([[face],[dict(face,x=.36)],[face]])
  self.assertIsNotNone(result);self.assertEqual(result['video_x'],0);self.assertGreaterEqual(result['video_scale'],1)
  for samples in ([],[[],[face],[face]],[[face,face],[face],[face]],[[dict(face,confidence=.2)]]*3,[[face],[dict(face,x=.8)],[face]]):self.assertIsNone(A.propose(samples))
 def test_free_text_space_keeps_source_frame_and_crowded_space_is_not_forced(self):
  face=dict(x=.35,y=.15,width=.12,height=.2,confidence=.99)
  result=A.propose([[face]]*3)
  self.assertIsNotNone(result)
  self.assertEqual((result['video_x'],result['video_y'],result['video_scale']),(0,0,1))
  left=A.propose([[dict(face,x=.67)]]*3)
  self.assertEqual(left['text_x'],-.51);self.assertEqual(left['video_scale'],1)
  crowded=dict(face,x=.36,width=.30)
  self.assertIsNone(A.propose([[crowded]]*3))

 def test_composition_is_validated_and_distinct_geometry_does_not_merge(self):
  from ks import kinetic_scene as C
  with self.assertRaises(ValueError):C.composition({'video_x':float('nan')})
  with self.assertRaises(ValueError):C.composition({'time':12})
  base=dict(framing='speaker_left',units=[dict(start=0,end=1)])
  other=dict(base,units=[dict(start=1,end=2)],composition=dict(video_x=-.04))
  self.assertEqual(len(C.scenes([base,other])),2)
 def test_adjacent_consistent_camera_uses_one_anchor_and_uncertainty_breaks_it(self):
  face=dict(x=.35,y=.15,width=.12,height=.2,confidence=.99)
  def record(i,x=.35):
   samples=[[dict(face,x=x)]]*3
   return dict(index=i,start=i,end=i+1,camera=('A',)*3,samples=samples,proposed=A.propose(samples),block={})
  a,b=record(0),record(1,.36);b['start']=1.4;groups=A._groups([a,b]);self.assertEqual(len(groups),1);self.assertEqual(len(groups[0]['records']),2)
  uncertain=record(1);uncertain['proposed']=None
  self.assertEqual(len(A._groups([a,uncertain,record(2)])),2)

class AssistServiceTests(unittest.TestCase):
 def setUp(self):
  from test_kinetic_text import KineticServiceTests
  KineticServiceTests.setUp(self)
  import json
  media=self.root/'fixture.mp4';media.write_bytes(b'fixture')
  self.d['materials']['videos']=[dict(id='video',path=str(media),has_audio=True)]
  self.d['tracks'].insert(0,dict(type='video',segments=[dict(id='v',material_id='video',target_timerange=dict(start=0,duration=3000000),source_timerange=dict(start=7000000,duration=3000000),clip=dict(scale=dict(x=1,y=1),transform=dict(x=0,y=0)),speed=1,common_keyframes=[],extra_material_refs=[])]))
  (self.proj/'draft_info.json').write_text(json.dumps(self.d));self.raw=(self.proj/'draft_info.json').read_bytes()
 def test_assisted_receipt_is_owned_cancellable_and_prepares_same_geometry(self):
  from ks import kinetic_jobs as J,job_store,caption_studio as S
  from unittest.mock import patch
  import copy,json
  from pathlib import Path
  meta=J.handle('alice',self.proj,dict(action='kinetic_meta'));p=J.handle('alice',self.proj,dict(action='kinetic_full_plan',source_hash=meta['source_hash'],media_hash=meta['media_hash']))
  def assist(draft,plan,project,progress):
   out=copy.deepcopy(plan);out['blocks'][0].update(framing='speaker_left',camera_move='static',composition=dict(video_x=-.03,video_y=.01,video_scale=1.05,text_x=.5,text_y=.4));return out,dict(accepted=1,uncertain=0)
  with patch.object(A,'assist',side_effect=assist) as detector:
   with self.assertRaises(ValueError):J.handle('bob',self.proj,dict(action='kinetic_assist',plan_id=p['plan_id']))
   detector.assert_not_called()
   before=list(job_store.records('alice','plans'))
   def progress(message):pass
   def cancelled(write):raise InterruptedError('cancelled')
   progress.commit_plan=cancelled
   with self.assertRaises(InterruptedError):J.handle('alice',self.proj,dict(action='kinetic_assist',plan_id=p['plan_id']),progress)
   self.assertEqual(list(job_store.records('alice','plans')),before)
   assisted=J.handle('alice',self.proj,dict(action='kinetic_assist',plan_id=p['plan_id']))
  self.assertNotEqual(assisted['plan_id'],p['plan_id']);self.assertEqual(assisted['preview']['scenes'][0]['x'],-.03)
  with patch.object(S,'output_root',return_value=self.root/'outputs'):built=J.handle('alice',self.proj,dict(action='kinetic_prepare',plan_id=assisted['plan_id']))
  self.assertEqual(json.loads((Path(built['destination'])/'kinetic_text_report.json').read_text()),assisted['preview']);self.assertEqual((self.proj/'draft_info.json').read_bytes(),self.raw)
  block=assisted['plan']['blocks'][0];edit=dict(cue_id=block['cue_id'],rows=[u['text'] for u in block['units']],form=block['form'],accent=len(block['units'])-1,motion='rise',enabled=True,framing='speaker_left',composition=dict(video_x=-.04))
  manual=J.handle('alice',self.proj,dict(action='kinetic_revise',plan_id=assisted['plan_id'],edits=[edit]));self.assertNotIn('assistance',job_store.load('alice','plans',manual['plan_id']))
 def test_no_confident_result_does_not_create_a_success_receipt(self):
  from ks import kinetic_jobs as J,job_store
  from unittest.mock import patch
  meta=J.handle('alice',self.proj,dict(action='kinetic_meta'));p=J.handle('alice',self.proj,dict(action='kinetic_full_plan',source_hash=meta['source_hash'],media_hash=meta['media_hash']));before=list(job_store.records('alice','plans'))
  with patch.object(A,'assist',return_value=(p['plan'],dict(accepted=0,uncertain=1))):
   with self.assertRaises(ValueError):J.handle('alice',self.proj,dict(action='kinetic_assist',plan_id=p['plan_id']))
  self.assertEqual(list(job_store.records('alice','plans')),before)

class SampleCanvasTests(unittest.TestCase):
 def test_portrait_and_landscape_faces_are_sampled_in_displayed_canvas_space(self):
  from ks import core_engine as CE
  import subprocess
  binary=CE.ac_ffmpeg_bin()
  if not binary:self.skipTest('ffmpeg unavailable')
  for source,canvas,padding in [('100x200',dict(width=1920,height=1080),'horizontal'),('200x100',dict(width=1080,height=1920),'vertical')]:
   w,h,filter=A.sample_geometry(canvas)
   r=subprocess.run([binary,'-nostdin','-v','error','-f','lavfi','-i','color=c=red:s='+source,'-vf',filter,'-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','pipe:1'],capture_output=True,check=True)
   self.assertEqual(len(r.stdout),w*h*3)
   def pixel(x,y):return tuple(r.stdout[(y*w+x)*3:(y*w+x)*3+3])
   self.assertGreater(pixel(w//2,h//2)[0],240)
   for x,y in ([(w//10,h//2),(w*9//10,h//2)] if padding=='horizontal' else [(w//2,h//10),(w//2,h*9//10)]):self.assertLess(max(pixel(x,y)),5)
