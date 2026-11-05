import json,tempfile,copy,unittest
from pathlib import Path
from unittest.mock import patch
from ks import cli_lab as L,cli_lab_story as S
class FinishOptionsTests(unittest.TestCase):
 def test_unknown_style_and_media_conflicts_reject_before_ai(self):
  from ks import editorial_finish as F
  for data in [dict(editing_finish='random'),dict(editing_finish=True),dict(editing_finish='story',mode='single'),dict(editing_finish='story',auto_stock=True),dict(editing_finish='impact',music='/a'),dict(editing_finish='story',editing_camera='yes'),dict(editing_camera=True),dict(editing_finish='story',effects=True),dict(editing_finish='story',style_captions=True)]:
   with self.subTest(data=data),self.assertRaises(ValueError):F.option(data)
  self.assertEqual(F.option(dict(editing_finish='story',mode='story')),'story')
  self.assertEqual(F.option({}),'off')
class FinishPipelineTests(unittest.TestCase):
 from test_kinetic_text import KineticServiceTests as _Fixture
 setUp=_Fixture.setUp
 def test_finish_and_publish_keep_report_and_original_speech(self):
  from ks import editorial_finish as F,assisted_framing as A,caption_presets as P
  from test_kinetic_scene import SceneTests
  self.d['tracks']+=SceneTests().fixture()['tracks'];self.d['duration']=6000000
  path=self.proj/'draft_info.json';path.write_text(json.dumps(self.d));before=copy.deepcopy(self.d)
  def observation(draft,plan,project,progress,settings=None,allow_motion_fallback=False):return plan,dict(accepted=0,uncertain=1,note='fixture: cannot certify placement')
  with patch.object(A,'assist',side_effect=observation),patch('ks.audio_levels.normalize_speech',return_value={}):out=F.decorate(self.proj,dict(editing_finish='story'),lambda m:None)
  self.assertEqual([text for _,seg,mat,text in P.caption_rows(out)],[text for _,seg,mat,text in P.caption_rows(before)])
  report=json.loads((self.proj/'kinetic_text_report.json').read_text());self.assertTrue(report['requires_visual_review']);self.assertTrue((self.proj/'editorial_quality_report.json').is_file())
  published=S.publish(self.proj,out,self.root/'published');self.assertTrue((published/'kinetic_text_report.json').is_file());self.assertTrue((published/'editorial_finish_report.json').is_file())

class FinishMediaChangeTests(unittest.TestCase):
 from test_kinetic_text import KineticServiceTests as _Fixture
 setUp=_Fixture.setUp
 def test_changed_media_prevents_publishing_decorated_draft(self):
  from ks import editorial_finish as F,assisted_framing as A
  from test_kinetic_scene import SceneTests
  video=SceneTests().fixture()['tracks'][0];video['segments'][0]['material_id']='source-video'
  media=self.root/'media.mp4';media.write_bytes(b'initial');self.d['materials']['videos']=[dict(id='source-video',path=str(media),type='video')];self.d['tracks'].append(video);self.d['duration']=6000000
  path=self.proj/'draft_info.json';path.write_text(json.dumps(self.d));raw=path.read_bytes()
  def changed(draft,plan,project,progress,settings=None,allow_motion_fallback=False):
   media.write_bytes(b'changed-media-content');return plan,dict(accepted=0,uncertain=1)
  with patch.object(A,'assist',side_effect=changed),self.assertRaisesRegex(ValueError,'สื่อเปลี่ยน'):
   F.decorate(self.proj,dict(editing_finish='story'),lambda m:None)
  self.assertEqual(path.read_bytes(),raw)

class FinalMediaCheckTests(unittest.TestCase):
 from test_kinetic_text import KineticServiceTests as _Fixture
 setUp=_Fixture.setUp
 def test_media_changed_during_audio_normalization_cannot_be_published(self):
  from ks import editorial_finish as F,assisted_framing as A
  from test_kinetic_scene import SceneTests
  video=SceneTests().fixture()['tracks'][0];video['segments'][0]['material_id']='source-video';media=self.root/'media.mp4';media.write_bytes(b'initial')
  self.d['materials']['videos']=[dict(id='source-video',path=str(media),type='video')];self.d['tracks'].append(video);self.d['duration']=6000000;(self.proj/'draft_info.json').write_text(json.dumps(self.d))
  def observe(draft,plan,project,progress,settings=None,allow_motion_fallback=False):return plan,dict(accepted=0,uncertain=1)
  def changed(*args):media.write_bytes(b'changed-at-last-stage');return {}
  with patch.object(A,'assist',side_effect=observe),patch('ks.audio_levels.normalize_speech',side_effect=changed),self.assertRaisesRegex(ValueError,'สื่อเปลี่ยน'):
   F.decorate(self.proj,dict(editing_finish='story'),lambda m:None)
  self.assertFalse((self.proj/'editorial_finish_report.json').exists())

class CleanupChoiceTests(unittest.TestCase):
 def test_selected_speech_cleanup_is_applied_and_audited(self):
  from ks import editorial_finish as F,cli_lab_alignment as A
  from test_cli_lab_polish import PolishTests
  draft,times=PolishTests().fixture()
  with tempfile.TemporaryDirectory() as folder,patch.object(A,'align_existing',return_value=times):
   out=F._cleanup(draft,Path(folder),dict(clean_speech=True,trim_silence=False),lambda m:None)
   self.assertEqual(out['duration'],2700000)
   self.assertEqual(len(json.loads((Path(folder)/'speech_cleanup.json').read_text())['removed']),1)

class FinishStoryRouteTests(unittest.TestCase):
 from test_cli_lab_story import StoryTests as _Fixture
 setUp=_Fixture.setUp
 def test_invalid_finish_stops_before_provider(self):
  with patch.object(L.E,'provider_config',side_effect=AssertionError('must reject before provider')),self.assertRaises(ValueError):
   L.handle('owner',self.root,dict(action='plan',mode='story',editing_finish='random',instruction='เลือกเรื่องเดียว'))
 def test_story_plan_persists_selected_finish_without_legacy_effects(self):
  import os
  from ks import job_store
  with patch.dict(os.environ,KS_JOB_STATE_DIR=str(self.root/'receipts')),patch.object(L.E,'provider_config',return_value=({},'UTCC')),patch('ks.cli_lab_webhook.request',return_value=json.dumps(self.raw)):
   result=L.handle('owner',self.root,dict(action='plan',mode='story',editing_finish='story',instruction='เลือกเรื่องเดียว',min_seconds=8,max_seconds=12,clean_speech=False,effects=False,style_captions=False))
   record=job_store.load('owner','plans',result['plan_id'])
  self.assertEqual(record['editing_finish'],'story');self.assertFalse(record['effects']);self.assertFalse(record['style_captions'])

class AutomaticPlacementRestTests(unittest.TestCase):
 from test_kinetic_text import KineticServiceTests as _Fixture
 setUp=_Fixture.setUp
 def test_unverified_automatic_supers_rest_but_speech_remains_complete(self):
  from ks import editorial_finish as F,assisted_framing as A,caption_presets as P
  original=copy.deepcopy(self.d)
  def observe(draft,plan,project,progress,settings=None,allow_motion_fallback=False):
   return plan,dict(accepted=0,uncertain=len(plan['blocks']),records=[dict(cue_id=b['cue_id'],safe=False,interval=[0,3],reasons=['faces overlap text']) for b in plan['blocks']])
  with patch.object(A,'assist',side_effect=observe),patch('ks.audio_levels.normalize_speech',return_value={}):
   out=F.decorate(self.proj,dict(editing_finish='story'),lambda m:None)
  report=json.loads((self.proj/'kinetic_text_report.json').read_text())
  self.assertEqual(report['units'],0,'automatic finish must not leave unverified supers on screen')
  self.assertEqual([t for _,s,m,t in P.caption_rows(out)],[t for _,s,m,t in P.caption_rows(original)])
  self.assertTrue(report['placement_rests'])

class PlacementConvergenceTests(unittest.TestCase):
 def test_resting_first_zoom_rechecks_survivor_under_new_scene(self):
  from ks import editorial_finish as F,assisted_framing as A
  plan=dict(blocks=[dict(cue_id='first',enabled=True),dict(cue_id='second',enabled=True)])
  def observe(draft,current,project,progress,**kwargs):
   first=current['blocks'][0]['enabled']
   active=[b for b in current['blocks'] if b['enabled']]
   return current,dict(accepted=1 if first else 0,uncertain=1,records=[dict(cue_id=b['cue_id'],safe=(first and b['cue_id']=='second'),interval=[0,3],reasons=['faces overlap text']) for b in active])
  with patch.object(A,'assist',side_effect=observe):
   final,evidence,rests=F._place({},plan,Path('/fixture'),{},lambda m:None)
  self.assertTrue(final['caption_only'])
  self.assertFalse(any(b['enabled'] for b in final['blocks']))
  self.assertEqual({r['cue_id'] for r in rests},{'first','second'})
