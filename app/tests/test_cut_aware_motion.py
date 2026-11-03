import copy,unittest
from ks import kinetic_scene as S
import test_kinetic_scene as fixtures

class CutAwareMotionTests(unittest.TestCase):
 def draft(self):
  d=fixtures.SceneTests().fixture();a=d['tracks'][0]['segments'][0];a['target_timerange']['duration']=3000000;a['source_timerange']['duration']=3000000;b=copy.deepcopy(a);b.update(id='second',target_timerange=dict(start=3000000,duration=3000000),source_timerange=dict(start=40000000,duration=3000000));d['tracks'][0]['segments'].append(b);return d
 def block(self,a=1,b=2,move='snap_to_cut',**kwargs):return dict(framing='keep',camera_move=move,units=[dict(start=a,end=b)],**kwargs)
 def test_hold_extends_past_text_until_actual_cut_and_next_shot_unchanged(self):
  self.assertIn('snap_to_cut',S.MOVES)
  d=self.draft();before=copy.deepcopy(d);scenes=S.scenes([self.block()],d);self.assertEqual((scenes[0]['start'],scenes[0]['end']),(1,3))
  for at in [1.3,2,2.99]:self.assertAlmostEqual(S.frame(scenes[0],at)['scale'],1.3)
  out=S.apply(d,scenes);self.assertEqual(d,before);self.assertEqual(out['tracks'][0]['segments'][-1],d['tracks'][0]['segments'][-1])
 def test_caption_crossing_cut_does_not_zoom_the_next_shot(self):
  self.assertIn('snap_to_cut',S.MOVES)
  self.assertEqual(S.scenes([self.block(2,5)],self.draft())[0]['end'],3)
 def test_last_shot_holds_until_end_and_repeated_emphasis_does_not_reset(self):
  self.assertIn('snap_to_cut',S.MOVES)
  scenes=S.scenes([self.block(3,4),self.block(4.5,5)],self.draft());self.assertEqual(len(scenes),1);self.assertEqual(scenes[0]['end'],6);self.assertAlmostEqual(S.frame(scenes[0],4.5)['scale'],1.3)
 def test_hold_requires_unambiguous_picture_at_start(self):
  self.assertIn('snap_to_cut',S.MOVES)
  with self.assertRaises(ValueError):S.scenes([self.block()])
  d=self.draft();d['tracks'].append(copy.deepcopy(d['tracks'][0]))
  with self.assertRaises(ValueError):S.scenes([self.block()],d)
  d=self.draft();d['tracks'][0]['segments'][1]['target_timerange']['start']=4000000
  with self.assertRaises(ValueError):S.scenes([self.block(3.5,4.5)],d)
 def test_new_motion_preempts_hold_without_overlapping_native_or_preview_scenes(self):
  self.assertIn('cinematic',S.MOVES)
  scenes=S.scenes([self.block(),self.block(2.5,3,'cinematic')],self.draft());self.assertEqual([(s['start'],s['end']) for s in scenes],[(1,2.5),(2.5,3)])
 def test_cinematic_works_centered_with_keep_and_five_percent_ease(self):
  self.assertIn('cinematic',S.MOVES)
  s=S.scenes([self.block(1,5,'cinematic')],self.draft())[0];self.assertEqual((s['x'],s['y']),(0,0));self.assertAlmostEqual(S.frame(s,3)['scale'],1.025);self.assertAlmostEqual(S.frame(s,5)['scale'],1.05)
  self.assertAlmostEqual(S.frame(s,2)['scale'],1.0078125)

 def test_renderer_revalidates_saved_move_and_reports_same_cut_as_native(self):
  from test_caption_presets import draft
  from ks import kinetic_full as F,kinetic_design as D,kinetic_text as K
  d=draft();d['duration']=6000000;d['tracks']+=self.draft()['tracks'];p=F.plan(d);b=p['blocks'][0]
  edit=dict(cue_id=b['cue_id'],form=b['form'],rows=[u['text'] for u in b['units']],motion='pop',accent=0,enabled=True,framing='keep',camera_move='snap_to_cut')
  revised=D.revise(p,[edit],{b['cue_id']:'😀 เข้าใจผู้บริโภค'});checked=D.validate_saved(revised,d);out,report=K.render(d,checked,font='')
  self.assertEqual(checked['blocks'][0]['camera_move'],'snap_to_cut');self.assertEqual(report['scenes'][0]['end'],3)
  video=next(t for t in out['tracks'] if t['type']=='video');self.assertEqual(video['segments'][0]['common_keyframes'][0]['keyframe_list'][-1]['time_offset'],13000000)
  self.assertAlmostEqual(video['segments'][0]['common_keyframes'][0]['keyframe_list'][-1]['values'][0],1.3)
  self.assertEqual(video['segments'][-1]['source_timerange']['start'],40000000)
