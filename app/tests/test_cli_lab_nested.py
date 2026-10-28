import copy,tempfile,unittest
from pathlib import Path
from ks.cli_lab_nested import audio_view
from ks.cli_lab_story import resolve_media_paths
class NestedTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.path=Path(self.tmp.name);(self.path/'voice.wav').write_bytes(b'fixture')
  leaf=lambda id:dict(id=id,material_id='leaf',speed=1,volume=.5,source_timerange={'start':2000000,'duration':10000000},target_timerange={'start':0,'duration':10000000})
  child={'materials':{'videos':[{'id':'leaf','path':str(self.path/'voice.wav')}]},'tracks':[{'id':id,'type':'video','segments':[leaf(id)]} for id in ('voice','other')]}
  self.d={'duration':4000000,'materials':{'videos':[{'id':'wrapper','path':'','multi_camera_info':{'audio_open_track_id_list':['voice']}}],'drafts':[{'id':'child','draft':child}]},'tracks':[{'type':'video','segments':[dict(id='parent',material_id='wrapper',extra_material_refs=['child'],speed=1,volume=.8,source_timerange={'start':3000000,'duration':4000000},target_timerange={'start':0,'duration':4000000})]}]}
 def test_selected_camera_only_and_trim_mapping(self):
  before=copy.deepcopy(self.d);r=audio_view(self.d);s=r['tracks'][0]['segments'];self.assertEqual(len(s),1)
  self.assertEqual(s[0]['source_timerange'],{'start':5000000,'duration':4000000});self.assertAlmostEqual(s[0]['volume'],.4);self.assertEqual(self.d,before)
 def test_empty_audio_selection_means_muted(self):
  self.d['materials']['videos'][0]['multi_camera_info']['audio_open_track_id_list']=[]
  self.assertEqual(audio_view(self.d)['tracks'][0]['segments'],[])
 def test_missing_selected_track_rejected(self):
  self.d['materials']['videos'][0]['multi_camera_info']['audio_open_track_id_list']=['absent']
  with self.assertRaisesRegex(ValueError,'กล้องเสียง'):audio_view(self.d)
 def test_nested_placeholder_resolution(self):
  self.d['materials']['drafts'][0]['draft']['materials']['videos'][0]['path']='##_draftpath_placeholder_ABC_##/voice.wav'
  d=resolve_media_paths(self.d,self.path);self.assertEqual(d['materials']['drafts'][0]['draft']['materials']['videos'][0]['path'],str((self.path/'voice.wav').resolve()))
 def test_speed_maps_nested_source_to_outer_duration(self):
  self.d['tracks'][0]['segments'][0]['speed']=2
  r=audio_view(self.d);s=r['tracks'][0]['segments'][0];self.assertEqual(s['speed'],2);self.assertEqual(s['source_timerange']['duration'],7000000);self.assertEqual(s['target_timerange']['duration'],3500000)
