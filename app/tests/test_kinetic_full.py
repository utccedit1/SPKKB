import copy,json,unittest
from ks import kinetic_text as K
class FullTypographyTests(unittest.TestCase):
 def test_matched_rows_have_equal_visual_width_and_natural_font_sizes(self):
  units=[dict(text='เพื่อทำ',row=0,weight='support'),dict(text='ภารกิจให้สำเร็จ',row=1,weight='hero')]
  g=K.geometry(units,1920,1080,'left',layout='matched',font='')
  self.assertAlmostEqual(g[0]['width'],g[1]['width'],places=5)
  self.assertGreater(g[0]['size'],g[1]['size'])
  self.assertAlmostEqual(g[0]['x'],g[1]['x'])
 def test_whole_clip_plan_preserves_source_and_labels_cue_timing(self):
  from test_caption_presets import draft
  from ks import kinetic_full as F,caption_presets as P
  d=draft();d['duration']=129200000;d['canvas_config']={'width':1920,'height':1080}
  t=d['tracks'][0];base=copy.deepcopy(t['segments'][0]);t['segments']=[];m=copy.deepcopy(d['materials']['texts'][0]);d['materials']['texts']=[]
  for i in range(57):
   s=copy.deepcopy(base);s.update(id='s'+str(i),material_id='m'+str(i),target_timerange=dict(start=i*2200000,duration=2000000));t['segments'].append(s)
   mat=copy.deepcopy(m);mat.update(id=s['material_id'],content=json.dumps({'text':'เพื่อทำภารกิจให้สำเร็จ','styles':[]}));d['materials']['texts'].append(mat)
  before=copy.deepcopy(d);p=F.plan(d)
  self.assertEqual(len(p['blocks']),57);self.assertEqual(p['duration'],129.2)
  self.assertEqual(p['blocks'][0]['units'][0]['text'],'เพื่อทำ')
  self.assertEqual(p['blocks'][0]['units'][1]['text'],'ภารกิจให้สำเร็จ')
  self.assertTrue(all(u['timing']=='caption' for b in p['blocks'] for u in b['units']))
  out,report=K.render(d,p,font='',layout='matched',caption_preset='punch')
  self.assertEqual(d,before);self.assertEqual(out['duration'],d['duration'])
  self.assertTrue(report['captions_styled']);self.assertEqual(report['layout'],'matched')
  for _,s,m,text in P.caption_rows(out):self.assertTrue(s['common_keyframes'])
 def test_full_proxy_walks_every_selected_shot_boundary(self):
  from ks.kinetic_proxy import sources
  from unittest.mock import patch
  calls=[]
  def at(d,t):
   calls.append(t);return dict(path='/fixture',offset=t,remaining=(2 if t<2 else 5)-t,speed=1,photo=False)
  with patch('ks.caption_studio.source_at',side_effect=at):parts=sources({'duration':5000000})
  self.assertEqual([p['duration'] for p in parts],[2,3]);self.assertEqual(calls,[0,2])
 def test_proxy_frames_use_absolute_timeline_boundaries_without_drift(self):
  from ks.kinetic_proxy import frame_counts
  parts=[dict(start=i*1.01,duration=1.01) for i in range(100)]
  frames=frame_counts(parts)
  self.assertEqual(sum(frames),3030)
  self.assertEqual(frames[:3],[30,31,30])
  for i in range(1,101):self.assertLessEqual(abs(sum(frames[:i])-i*30.3),.500001)

class FullServiceTests(unittest.TestCase):
 from test_kinetic_text import KineticServiceTests as _Fixture
 setUp=_Fixture.setUp
 def test_full_local_plan_never_calls_ai_and_prepares_owned_copy(self):
  from ks import kinetic_jobs as J,caption_studio as S,cli_lab_webhook as W
  from unittest.mock import patch
  meta=J.handle('alice',self.proj,{'action':'kinetic_meta'})
  with patch.object(W,'request',side_effect=AssertionError('local plan must not call AI')):
   planned=J.handle('alice',self.proj,dict(action='kinetic_full_plan',source_hash=meta['source_hash'],media_hash=meta['media_hash'],layout='matched',caption_preset='rise'))
  self.assertEqual(planned['plan']['kind'],'caption_full');self.assertTrue(planned['preview']['captions'])
  with self.assertRaises(ValueError):J.handle('bob',self.proj,dict(action='kinetic_prepare',plan_id=planned['plan_id']))
  with patch.object(S,'output_root',return_value=self.root/'outputs'):
   result=J.handle('alice',self.proj,dict(action='kinetic_prepare',plan_id=planned['plan_id']))
  self.assertTrue(result['result_id']);self.assertEqual((self.proj/'draft_info.json').read_bytes(),self.raw)
 def test_full_local_cancelled_plan_is_not_persisted(self):
  from ks import kinetic_jobs as J,job_store
  meta=J.handle('alice',self.proj,{'action':'kinetic_meta'})
  def progress(message):pass
  def cancelled(write):raise InterruptedError('cancelled')
  progress.commit_plan=cancelled
  with self.assertRaises(InterruptedError):J.handle('alice',self.proj,dict(action='kinetic_full_plan',source_hash=meta['source_hash'],media_hash=meta['media_hash']),progress)
  self.assertEqual(list(job_store.records('alice','plans')),[])

class FontMetricsTests(unittest.TestCase):
 def test_matched_width_uses_selected_font_advances_not_character_counts(self):
  from unittest.mock import patch
  with patch('ks.font_measure.advance',side_effect=lambda text,font:100 if text=='เพื่อทำ' else 250):
   g=K.geometry([dict(text='เพื่อทำ',row=0,weight='support'),dict(text='ภารกิจให้สำเร็จ',row=1,weight='hero')],1920,1080,'left',layout='matched',font='/fixture.ttf')
  self.assertAlmostEqual(g[0]['size']*100,g[1]['size']*250)
