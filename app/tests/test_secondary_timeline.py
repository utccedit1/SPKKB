import copy, hashlib, json, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ks import event_timeline as T, caption_resegment as R, unified_history as H, apply_guard as G

class SecondaryTimelineTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.root=Path(self.tmp.name);self.p=self.root/'Timelines'/'second';self.p.mkdir(parents=True)
  self.d={'id':'second','duration':6000000,'materials':{'texts':[{'id':'m','content':json.dumps({'text':'จริงจริง น้องน้อง','styles':[]})}]},'tracks':[{'type':'text','segments':[{'id':'s','material_id':'m','target_timerange':{'start':0,'duration':6000000}}]}]}
  self.raw=json.dumps(self.d).encode();(self.p/'draft_info.json').write_bytes(self.raw)
  self.main=json.dumps(dict(self.d,id='main')).encode();(self.root/'draft_info.json').write_bytes(self.main)
  self.sibling=self.root/'Timelines'/'main';self.sibling.mkdir();(self.sibling/'draft_info.json').write_bytes(self.main)
  (self.root/'draft_meta_info.json').write_bytes(b'{"tm_duration":123}')
  self.closed=patch.object(T,'ensure_closed');self.closed.start();self.addCleanup(self.closed.stop)
 def assert_main_untouched(self):
  self.assertEqual((self.root/'draft_info.json').read_bytes(),self.main)
  self.assertEqual((self.sibling/'draft_info.json').read_bytes(),self.main)
  self.assertEqual((self.root/'draft_meta_info.json').read_bytes(),b'{"tm_duration":123}')
 def test_resegment_secondary_and_restore(self):
  result=R.run(str(self.p),{'max_words':20})
  self.assertTrue(result['ok']);self.assertNotEqual((self.p/'draft_info.json').read_bytes(),self.raw)
  self.assert_main_untouched()
  H.restore(str(self.p),{'id':'checkpoint:'+result['backup_name']})
  self.assertEqual((self.p/'draft_info.json').read_bytes(),self.raw);self.assert_main_untouched()
 def test_generation_commit_secondary(self):
  digest=hashlib.sha1(self.raw).hexdigest()
  prepared=G.prepare(str(self.p),{'source_hash':digest,'state_hash':digest})
  G.commit(str(self.p),prepared,dict(self.d,duration=123))
  self.assertEqual(json.loads((self.p/'draft_info.json').read_bytes())['duration'],123);self.assert_main_untouched()
 def test_old_checkpoint_wrong_mirror_never_restores_root(self):
  backup=T.checkpoint(str(self.p),'manual');manifest=json.loads((backup/'manifest.json').read_bytes())
  (backup/'__project_draft_info.json').write_bytes(self.main)
  manifest['files']['__project_draft_info.json']=hashlib.sha256(self.main).hexdigest()
  (backup/'manifest.json').write_text(json.dumps(manifest))
  H.restore(str(self.p),{'id':'checkpoint:'+backup.name});self.assert_main_untouched()
 def test_commit_and_stale_guard(self):
  H.commit_draft(str(self.p),dict(self.d,duration=456),self.raw,'manual');self.assert_main_untouched()
  with self.assertRaises(ValueError):H.commit_draft(str(self.p),self.d,self.raw,'manual')
  self.assert_main_untouched()

 def test_cut_secondary_keeps_main_and_can_restore(self):
  with patch.object(T.E,'transcript',side_effect=lambda proj:(json.loads((Path(proj)/'draft_info.json').read_bytes()),[],hashlib.sha256((Path(proj)/'draft_info.json').read_bytes()).hexdigest())):
   result=T.apply(str(self.p),{'source_hash':hashlib.sha256(self.raw).hexdigest(),'segments':[[0,3]]})
  self.assertEqual(result['duration'],3);self.assert_main_untouched()
  H.restore(str(self.p),{'id':'checkpoint:'+result['backup_name']})
  self.assertEqual((self.p/'draft_info.json').read_bytes(),self.raw);self.assert_main_untouched()
