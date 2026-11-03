import unittest,copy
from ks import kinetic_scene as C
class SceneTests(unittest.TestCase):
 def fixture(self):
  return dict(duration=6000000,tracks=[dict(type='video',segments=[dict(id='v',material_id='m',speed=1,source_timerange=dict(start=10000000,duration=6000000),target_timerange=dict(start=0,duration=6000000),clip=dict(scale=dict(x=1,y=1),transform=dict(x=0,y=0),rotation=0,alpha=1),common_keyframes=[],extra_material_refs=['nested'])])])
 def test_scene_splits_copy_preserving_source_and_global_motion(self):
  d=self.fixture();before=copy.deepcopy(d);blocks=[dict(framing='speaker_left',camera_move='push',units=[dict(start=1,end=3)]),dict(framing='speaker_left',camera_move='push',units=[dict(start=3.1,end=5)])]
  scenes=C.scenes(blocks);self.assertEqual(len(scenes),1)
  out=C.apply(d,scenes);self.assertEqual(d,before);segs=out['tracks'][0]['segments'];self.assertEqual([s['target_timerange']['duration'] for s in segs],[1000000,4000000,1000000]);self.assertEqual([s['source_timerange']['start'] for s in segs],[10000000,11000000,15000000]);self.assertEqual(segs[1]['extra_material_refs'],['nested'])
  self.assertAlmostEqual(C.frame(scenes[0],3)['scale'],1.105)
  self.assertEqual(segs[1]['common_keyframes'][0]['keyframe_list'][0]['time_offset'],11000000)
 def test_smooth_zoom_has_eased_progress_peak_and_return(self):
  for mode,quarter,middle,end in [('smooth_in',1.046875,1.15,1.3),('smooth_out',1.253125,1.15,1),('smooth_in_out',1.15,1.3,1)]:
   scene=C.scenes([dict(framing='speaker_left',camera_move=mode,composition=dict(video_x=0,video_y=0,video_scale=1),units=[dict(start=1,end=5)])])[0]
   self.assertAlmostEqual(C.frame(scene,2)['scale'],quarter)
   self.assertAlmostEqual(C.frame(scene,3)['scale'],middle)
   self.assertAlmostEqual(C.frame(scene,5)['scale'],end)
 def test_smooth_native_keeps_interior_curve_and_source_time_after_split(self):
  d=self.fixture();d['tracks'][0]['segments'][0]['speed']=2;d['tracks'][0]['segments'][0]['source_timerange']['duration']=12000000
  scene=C.scenes([dict(framing='speaker_left',camera_move='smooth_in_out',composition=dict(video_x=0,video_y=0,video_scale=1),units=[dict(start=1,end=5)])])
  out=C.apply(d,scene);segments=out['tracks'][0]['segments'];keys=segments[1]['common_keyframes'][0]['keyframe_list']
  self.assertGreater(len(keys),3)
  self.assertEqual(keys[0]['time_offset'],12000000)
  self.assertEqual(keys[-1]['time_offset'],20000000)
  peak=next(k for k in keys if k['time_offset']==16000000)
  self.assertAlmostEqual(peak['values'][0],1.3)
  self.assertEqual(segments[-1]['clip']['scale']['x'],1)
  self.assertEqual(segments[-1]['source_timerange']['start'],20000000)

 def test_smooth_default_is_centered_and_each_emphasis_has_own_reset(self):
  blocks=[dict(framing='speaker_left',camera_move='smooth_in',units=[dict(start=1,end=2)]),dict(framing='speaker_left',camera_move='smooth_in',units=[dict(start=2,end=3)])]
  scenes=C.scenes(blocks)
  self.assertEqual(len(scenes),2)
  self.assertEqual((scenes[0]['x'],scenes[0]['y']),(0,0))
  self.assertEqual(C.frame(scenes[1],2)['scale'],1)
  C.apply(self.fixture(),scenes)

 def test_snap_zoom_reaches_target_in_point_three_seconds_then_holds(self):
  for mode,values in [('snap_in',[1,1.15,1.3,1.3,1.3]),('snap_out',[1.3,1.15,1,1,1]),('snap_in_out',[1,1.15,1.3,1.3,1])]:
   with self.subTest(mode=mode):
    self.assertIn(mode,C.MOVES)
    scene=C.scenes([dict(framing='speaker_left',camera_move=mode,units=[dict(start=1,end=5)])])[0]
    self.assertEqual((scene['x'],scene['y']),(0,0))
    for time,want in zip([1,1.15,1.3,3,5],values):self.assertAlmostEqual(C.frame(scene,time)['scale'],want)
    self.assertAlmostEqual(C.frame(scene,1.075)['scale'],1.253125 if mode=='snap_out' else 1.046875)
    self.assertTrue(any(abs(t-1.3)<1e-9 for t,v in scene['scale_points']))
    if mode=='snap_in_out':
     self.assertTrue(any(abs(t-4.7)<1e-9 for t,v in scene['scale_points']))
     self.assertAlmostEqual(C.frame(scene,4.85)['scale'],1.15)

 def test_snap_short_beats_keep_middle_hold_and_reset_at_each_beat(self):
  blocks=[dict(framing='speaker_left',camera_move='snap_in_out',units=[dict(start=a,end=b)]) for a,b in [(1,1.3),(1.3,1.6)]]
  self.assertIn('snap_in_out',C.MOVES)
  scenes=C.scenes(blocks);self.assertEqual(len(scenes),2)
  for scene in scenes:
   a=scene['start']
   for offset,want in [(0,1),(.05,1.15),(.1,1.3),(.15,1.3),(.2,1.3),(.25,1.15),(.3,1)]:self.assertAlmostEqual(C.frame(scene,a+offset)['scale'],want)

 def test_snap_zoom_works_with_keep_framing_without_changing_text_geometry(self):
  block=dict(framing='keep',camera_move='snap_in',composition=dict(text_x=-.4,text_y=.4),units=[dict(start=1,end=5)])
  before=copy.deepcopy(block);scenes=C.scenes([block]);self.assertEqual(block,before)
  self.assertEqual(len(scenes),1);scene=scenes[0]
  self.assertEqual((scene['composition']['text_x'],scene['composition']['text_y']),(-.4,.4))
  self.assertEqual((scene['x'],scene['y']),(0,0));self.assertAlmostEqual(C.frame(scene,2)['scale'],1.3)
  self.assertEqual(C.scenes([dict(block,camera_move='static')]),[])
  self.assertEqual(C.scenes([dict(block,camera_move='smooth_in')]),[])

 def test_snap_native_preserves_ramp_knots_across_source_cut(self):
  self.assertIn('snap_in_out',C.MOVES)
  d=self.fixture();first=d['tracks'][0]['segments'][0];first['speed']=2;first['target_timerange']['duration']=1200000;first['source_timerange']['duration']=2400000
  second=copy.deepcopy(first);second.update(id='other',source_timerange=dict(start=40000000,duration=9600000),target_timerange=dict(start=1200000,duration=4800000));d['tracks'][0]['segments'].append(second)
  scene=C.scenes([dict(framing='speaker_left',camera_move='snap_in_out',units=[dict(start=1,end=5)])])
  before=copy.deepcopy(d);out=C.apply(d,scene);self.assertEqual(d,before)
  left,right=out['tracks'][0]['segments'][1:3]
  leftkeys=left['common_keyframes'][0]['keyframe_list'];rightkeys=right['common_keyframes'][0]['keyframe_list']
  self.assertGreater(len(leftkeys),3);self.assertAlmostEqual(leftkeys[-1]['values'][0],rightkeys[0]['values'][0])
  self.assertEqual(leftkeys[0]['time_offset'],12000000);self.assertEqual(rightkeys[0]['time_offset'],40000000)
  self.assertAlmostEqual(next(k for k in rightkeys if k['time_offset']==40200000)['values'][0],1.3)
  self.assertAlmostEqual(next(k for k in rightkeys if k['time_offset']==47000000)['values'][0],1.3)
  self.assertEqual(rightkeys[-1]['time_offset'],47600000);self.assertAlmostEqual(rightkeys[-1]['values'][0],1)

 def test_identity_text_placement_does_not_split_or_transform_picture(self):
  blocks=[dict(framing='speaker_left',camera_move='static',composition=dict(video_x=0,video_y=0,video_scale=1),units=[dict(start=1,end=3)])]
  scenes=C.scenes(blocks);self.assertEqual(scenes,[])
  d=self.fixture();self.assertEqual(C.apply(d,scenes),d)
 def test_shift_cannot_expose_canvas_edges_at_either_zoom_endpoint(self):
  unsafe=dict(start=1,end=4,move='static',x=-.45,y=0,scale_from=1.08,scale_to=1.08)
  with self.assertRaisesRegex(ValueError,'ขอบภาพ'):C.apply(self.fixture(),[unsafe])
  unsafe.update(x=-.1,scale_from=1.2,scale_to=1.05)
  with self.assertRaisesRegex(ValueError,'ขอบภาพ'):C.apply(self.fixture(),[unsafe])

 def test_existing_transform_is_rejected_and_default_keeps_it(self):
  d=self.fixture();d['tracks'][0]['segments'][0]['clip']['scale']['x']=1.2
  self.assertEqual(C.apply(d,[]),d)
  with self.assertRaises(ValueError):C.apply(d,[dict(start=1,end=4,move='static',x=-.4,y=-.02,scale_from=1.08,scale_to=1.08)])
 def test_keep_beat_breaks_a_scene_and_does_not_get_reframed(self):
  unit=lambda a,b:[dict(start=a,end=b)]
  scenes=C.scenes([dict(framing='speaker_left',units=unit(0,1)),dict(units=unit(1,1.1)),dict(framing='speaker_left',units=unit(1.1,2))])
  self.assertEqual(len(scenes),2)
 def test_motion_continues_at_existing_cut_and_source_keys_use_each_source(self):
  d=self.fixture();first=d['tracks'][0]['segments'][0];first['target_timerange']['duration']=3000000;first['source_timerange']['duration']=3000000
  second=copy.deepcopy(first);second.update(id='other',source_timerange=dict(start=40000000,duration=3000000),target_timerange=dict(start=3000000,duration=3000000));d['tracks'][0]['segments'].append(second)
  scenes=C.scenes([dict(framing='speaker_left',camera_move='push',units=[dict(start=1,end=5)])]);out=C.apply(d,scenes);segs=out['tracks'][0]['segments'];left=segs[1]['common_keyframes'][0]['keyframe_list'][-1];right=segs[2]['common_keyframes'][0]['keyframe_list'][0]
  self.assertAlmostEqual(left['values'][0],right['values'][0]);self.assertEqual(right['time_offset'],40000000)

 def test_reverse_and_endpoint_fades_cannot_be_silently_changed_by_splitting(self):
  scene=C.scenes([dict(framing='speaker_left',units=[dict(start=1,end=5)])])
  d=self.fixture();d['tracks'][0]['segments'][0]['is_reverse']=True
  with self.assertRaises(ValueError):C.apply(d,scene)
  d=self.fixture();d['materials']={'audio_fades':[dict(id='fade',fade_in_duration=1000000,fade_out_duration=1000000)]};d['tracks'][0]['segments'][0]['extra_material_refs'].append('fade')
  with self.assertRaises(ValueError):C.apply(d,scene)

class SceneServiceTests(unittest.TestCase):
 from test_kinetic_text import KineticServiceTests as _Fixture
 setUp=_Fixture.setUp
 def test_saved_scene_preview_matches_prepared_copy_and_is_owner_bound(self):
  from ks import kinetic_jobs as J,caption_studio as S
  from unittest.mock import patch
  import json
  media=self.root/'fixture.mp4';media.write_bytes(b'fixture')
  self.d['materials']['videos']=[dict(id='video',path=str(media),has_audio=True)]
  self.d['tracks'].insert(0,dict(type='video',segments=[dict(id='v',material_id='video',target_timerange=dict(start=0,duration=3000000),source_timerange=dict(start=7000000,duration=3000000),clip=dict(scale=dict(x=1,y=1),transform=dict(x=0,y=0)),speed=1,common_keyframes=[],extra_material_refs=[])]))
  (self.proj/'draft_info.json').write_text(json.dumps(self.d));original=(self.proj/'draft_info.json').read_bytes()
  meta=J.handle('alice',self.proj,dict(action='kinetic_meta'));p=J.handle('alice',self.proj,dict(action='kinetic_full_plan',source_hash=meta['source_hash'],media_hash=meta['media_hash']))
  b=p['plan']['blocks'][0];edit=dict(cue_id=b['cue_id'],rows=[u['text'] for u in b['units']],form='stack',accent=len(b['units'])-1,motion='rise',enabled=True,framing='speaker_left',camera_move='push')
  p=J.handle('alice',self.proj,dict(action='kinetic_revise',plan_id=p['plan_id'],edits=[edit]));self.assertEqual(len(p['preview']['scenes']),1)
  with self.assertRaises(ValueError):J.handle('bob',self.proj,dict(action='kinetic_prepare',plan_id=p['plan_id']))
  with patch.object(S,'output_root',return_value=self.root/'outputs'):built=J.handle('alice',self.proj,dict(action='kinetic_prepare',plan_id=p['plan_id']))
  from pathlib import Path
  report=json.loads((Path(built['destination'])/'kinetic_text_report.json').read_text());self.assertEqual(report,p['preview']);self.assertEqual((self.proj/'draft_info.json').read_bytes(),original)
