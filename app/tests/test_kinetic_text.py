import copy,json,unittest
from ks import kinetic_text as K

def cues():
 return [dict(id='cue',text='หลักการ ยังใช้ได้',start=2,duration=3,words=[dict(word='หลักการ',start=0,end=.8),dict(word='ยัง',start=1,end=1.4),dict(word='ใช้ได้',start=1.5,end=2.7)])]
def plan():
 return {'blocks':[{'cue_id':'cue','units':[{'first':0,'last':0,'row':0,'weight':'support','tone':'base','motion':'rise'},{'first':1,'last':2,'row':1,'weight':'hero','tone':'accent','motion':'pop'}]}]}
class KineticTests(unittest.TestCase):
 def test_valid_plan_uses_source_words_and_measured_onsets(self):
  p=K.validate(plan(),cues());self.assertEqual(p['blocks'][0]['units'][1]['text'],'ยังใช้ได้');self.assertEqual(p['blocks'][0]['units'][1]['start'],3)
 def test_rejects_invalid_source_references_overlap_nan_and_unmeasured_words(self):
  for change in [('first',-1),('last',8),('row',3),('weight','giant'),('tone','#ff0000'),('motion','glitch'),('first',True)]:
   p=plan();p['blocks'][0]['units'][1][change[0]]=change[1]
   with self.subTest(change=change),self.assertRaises(ValueError):K.validate(p,cues())
  p=plan();p['blocks'][0]['units'][1]['first']=0
  with self.assertRaises(ValueError):K.validate(p,cues())
  c=cues();c[0]['words'][1]['start']=float('nan')
  with self.assertRaises(ValueError):K.validate(plan(),c)
  c=cues();c[0]['words']=[]
  with self.assertRaises(ValueError):K.validate(plan(),c)
 def test_renderer_adds_separate_timed_words_and_keeps_original_tracks(self):
  d={'duration':6000000,'canvas_config':{'width':1920,'height':1080},'materials':{'texts':[]},'tracks':[]}
  from test_caption_presets import draft
  native=draft();native['duration']=6000000;native['canvas_config']=d['canvas_config'];before=copy.deepcopy(native)
  out,report=K.render(native,K.validate(plan(),cues()),font='',zone='left')
  self.assertEqual(native,before);self.assertEqual(out['tracks'][:-2],before['tracks'])
  entries=[s for t in out['tracks'] if t.get('ks_role')=='kinetic_super' for s in t['segments']]
  self.assertEqual([s['target_timerange']['start'] for s in entries],[2000000,3000000])
  self.assertEqual(len(entries),2);self.assertTrue(report['native_review_required'])
  mats={m['id']:m for m in out['materials']['texts']}
  sizes=[mats[s['material_id']]['font_size'] for s in entries];self.assertGreater(sizes[1],sizes[0])
 def test_prompt_contains_app_skill_and_never_allows_new_dialogue(self):
  prompt,system=K.prompt(cues(),zone='left');self.assertIn('chuaydai-editing',system);self.assertIn('first',system);self.assertIn('หลักการ',prompt)

class KineticServiceTests(unittest.TestCase):
 def setUp(self):
  import tempfile,os
  from unittest.mock import patch
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  from pathlib import Path
  self.root=Path(self.tmp.name);self.proj=self.root/'project';self.proj.mkdir()
  from test_caption_presets import draft
  self.d=draft();self.d['tracks'][0]['segments']=self.d['tracks'][0]['segments'][:1]
  self.d['tracks'][0]['segments'][0]['target_timerange']={'start':0,'duration':3000000}
  self.d['materials']['texts'][0]['content']=json.dumps({'text':'หลักการ ยังใช้ได้','styles':[]})
  self.d['materials']['texts'][0]['words']={'text':['หลักการ',' ','ยังใช้ได้'],'start_time':[0,800,1000],'end_time':[800,800,2700]}
  (self.proj/'draft_info.json').write_text(json.dumps(self.d));self.raw=(self.proj/'draft_info.json').read_bytes()
  self.env=patch.dict(os.environ,KS_JOB_STATE_DIR=str(self.root/'receipts'));self.env.start();self.addCleanup(self.env.stop)
 def test_ai_plan_is_skill_grounded_and_prepare_is_owned_copy(self):
  from ks import kinetic_jobs as J,event_clip as E,cli_lab_webhook as W,caption_studio as S
  from unittest.mock import patch
  meta=J.handle('alice',self.proj,{'action':'kinetic_meta'})
  raw={'blocks':[{'cue_id':'one','units':[{'first':0,'last':0,'row':0,'weight':'support','tone':'base','motion':'rise'},{'first':1,'last':1,'row':1,'weight':'hero','tone':'accent','motion':'pop'}]}]}
  with patch.object(E,'provider_config',return_value=({'ai_backend':'gemini','gemini_api_key':'fixture'},'Gemini')),patch.object(W,'request',return_value=json.dumps(raw)) as ai:
   planned=J.handle('alice',self.proj,dict(action='kinetic_plan',ids=['one'],source_hash=meta['source_hash'],media_hash=meta['media_hash']))
  self.assertIn('chuaydai-editing',ai.call_args.kwargs['system'])
  with self.assertRaises(ValueError):J.handle('bob',self.proj,dict(action='kinetic_prepare',plan_id=planned['plan_id']))
  with patch.object(S,'output_root',return_value=self.root/'outputs'):
   built=J.handle('alice',self.proj,dict(action='kinetic_prepare',plan_id=planned['plan_id']))
  self.assertTrue(built['result_id']);self.assertEqual((self.proj/'draft_info.json').read_bytes(),self.raw)
 def test_cancellation_before_plan_persistence_leaves_no_usable_plan(self):
  from ks import kinetic_jobs as J,event_clip as E,cli_lab_webhook as W,job_store
  from unittest.mock import patch
  meta=J.handle('alice',self.proj,{'action':'kinetic_meta'})
  raw={'blocks':[{'cue_id':'one','units':[{'first':0,'last':0,'row':0,'weight':'support','tone':'base','motion':'rise'},{'first':1,'last':1,'row':1,'weight':'hero','tone':'accent','motion':'pop'}]}]}
  def progress(message):pass
  def cancelled(write):raise InterruptedError('fixture cancellation')
  progress.commit_plan=cancelled
  with patch.object(E,'provider_config',return_value=({'ai_backend':'gemini','gemini_api_key':'fixture'},'Gemini')),patch.object(W,'request',return_value=json.dumps(raw)):
   with self.assertRaises(InterruptedError):J.handle('alice',self.proj,dict(action='kinetic_plan',ids=['one'],source_hash=meta['source_hash'],media_hash=meta['media_hash']),progress)
  self.assertEqual(list(job_store.records('alice','plans')),[])

class KineticAdmissionTests(unittest.TestCase):
 def test_repeated_client_request_recovers_same_job_without_second_ai_call(self):
  import tempfile,threading,os
  from unittest.mock import patch
  from ks import cli_lab as L
  ready=threading.Event();release=threading.Event();finished=threading.Event();calls=[]
  def handle(*args):
   calls.append(1);ready.set();release.wait(2);finished.set();return {'ok':True}
  with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,KS_JOB_STATE_DIR=folder),patch.object(L,'_jobs',{}),patch.object(L,'handle',side_effect=handle):
   try:
    data={'operation':'kinetic_plan','request_id':'a'*32,'ids':['one']}
    first=L.start_job('alice',folder,data);self.assertTrue(ready.wait(2))
    second=L.start_job('alice',folder,data);self.assertEqual(first['job_id'],second['job_id']);self.assertEqual(calls,[1])
    with self.assertRaises(ValueError):L.start_job('alice',folder,dict(data,ids=['two']))
   finally:
    release.set()
    for worker in threading.enumerate():
     if worker.name.startswith('cli-lab-'):worker.join(3)

class ThaiWordAlignmentTests(unittest.TestCase):
 def test_thai_bpe_fragments_merge_to_real_words_without_inventing_times(self):
  from ks.cli_lab_alignment import lexical_words
  raw=[dict(word='ท',start=0,end=0,probability=.7),dict(word='ี่',start=0,end=.06,probability=.9),dict(word='ด',start=.06,end=.16,probability=.9),dict(word='ู',start=.16,end=.24,probability=.9)]
  out=lexical_words(raw,'ที่ดู')
  self.assertEqual([w['word'] for w in out],['ที่','ดู'])
  self.assertEqual([(w['start'],w['end']) for w in out],[(0,.06),(.06,.24)])
 def test_lexical_merge_rejects_missing_text_and_preserves_low_confidence(self):
  from ks.cli_lab_alignment import lexical_words
  with self.assertRaises(ValueError):lexical_words([dict(word='ผิด',start=0,end=1,probability=.9)],'คำเดิม')
  out=lexical_words([dict(word='ที่',start=0,end=.2,probability=.01)],'ที่')
  self.assertLess(out[0]['probability'],.15)
 def test_lexical_alignment_consumes_more_than_400_tokens_in_prefixes(self):
  import numpy as np
  from ks.cli_lab_alignment import align_windows
  class Tokenizer:
   def encode(self,text):return list(range(len(text.split())))
  class Model:
   count=0
   def feature_extractor(self,audio):return np.zeros((80,max(1,len(audio)//160)))
   def encode(self,value):return value
   def find_alignment(self,tok,tokens,*args):
    self.count+=1;n=len(tokens[0]);return [[dict(word=(' ' if i or self.count>1 else '')+'word',start=i*.01,end=(i+1)*.01,probability=.9) for i in range(n)]]
  words=align_windows(Model(),Tokenizer(),np.zeros(10*16000),' '.join(['word']*401),10,lambda x:x,lexical=True)
  self.assertEqual(len(words),401)
