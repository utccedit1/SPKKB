import copy,json,sys,tempfile,threading,time,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ks import unified_history as H,feature_tasks as F,event_jobs as J,event_clip as E,event_timeline as T,core_engine as C

class WorkflowTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.p=self.root/'Timelines'/'main';self.p.mkdir(parents=True)
  self.d={'id':'main','duration':4000000,'materials':{'texts':[{'id':'m','type':'subtitle','content':json.dumps({'text':'คำเดิม เนื้อหาครบ','styles':[{'range':[0,16],'size':12}]})}],'videos':[{'id':'v','path':str(self.root/'video.mp4')}]},'tracks':[{'type':'text','segments':[{'id':'s','material_id':'m','target_timerange':{'start':0,'duration':4000000}}]},{'type':'video','segments':[{'id':'vs','material_id':'v','speed':1,'source_timerange':{'start':0,'duration':4000000},'target_timerange':{'start':0,'duration':4000000}}]}]}
  (self.root/'video.mp4').write_bytes(b'fixture');self.write(self.d);self.closed=patch.object(T,'ensure_closed');self.closed.start();self.addCleanup(self.closed.stop)
 def write(self,d):
  raw=json.dumps(d).encode();(self.p/'draft_info.json').write_bytes(raw);(self.root/'draft_info.json').write_bytes(raw)
 def cfg(self):return C.api_captions(str(self.p),current=True)
 def test_history_restores_and_preserves_recovery_before_restore(self):
  initial=(self.p/'draft_info.json').read_bytes();one=H.checkpoint(str(self.p));changed=copy.deepcopy(self.d);changed['duration']=5000000;self.write(changed);before=(self.p/'draft_info.json').read_bytes()
  result=H.restore(str(self.p),{'id':'checkpoint:'+one['backup_name'],'source_hash':H.digest(before)})
  self.assertEqual((self.p/'draft_info.json').read_bytes(),initial);self.assertEqual((self.root/'draft_info.json').read_bytes(),initial)
  self.assertEqual(T.read_checkpoint(str(self.p),result['backup_name'])['draft_info.json'],before)
 def test_legacy_restore_clears_caption_cache_and_is_visible_in_history(self):
  initial=(self.p/'draft_info.json').read_bytes();(self.p/'draft_info_backup.json').write_bytes(initial);(self.p/'draft_info_original.json').write_text('{}');self.write(dict(self.d,duration=5000000))
  result=H.restore(str(self.p),{'id':'initial:original'});self.assertTrue(result['ok']);self.assertFalse((self.p/'draft_info_original.json').exists());self.assertEqual((self.root/'draft_info.json').read_bytes(),initial)
  self.assertIn('initial:original',[r['id'] for r in H.listing(str(self.p))['items']])
 def test_stale_or_corrupt_restore_does_not_change_any_files(self):
  one=H.checkpoint(str(self.p));before=(self.p/'draft_info.json').read_bytes()
  with self.assertRaises(ValueError):H.restore(str(self.p),{'id':'checkpoint:'+one['backup_name'],'source_hash':'stale'})
  (self.p/T.BACKUPS/one['backup_name']/'draft_info.json').write_bytes(b'corrupt')
  with self.assertRaises(ValueError):H.restore(str(self.p),{'id':'checkpoint:'+one['backup_name']})
  self.assertEqual((self.p/'draft_info.json').read_bytes(),before)
 def test_transaction_failure_restores_mirror_and_live(self):
  before=(self.p/'draft_info.json').read_bytes();real=T.replace_files;calls=[]
  def broken(proj,files):
   calls.append(True)
   if len(calls)==1:T.atomic_write(self.p/'draft_info.json',b'{}');raise OSError('disk full')
   real(proj,files)
  with patch.object(T,'replace_files',side_effect=broken):
   with self.assertRaises(OSError):H.commit_draft(str(self.p),dict(self.d,duration=123),before,'before_audio_align')
  self.assertEqual((self.p/'draft_info.json').read_bytes(),before);self.assertEqual((self.root/'draft_info.json').read_bytes(),before)
 def test_raw_cut_requires_matching_media_and_continuous_timeline(self):
  cfg={**self.cfg(),'video':str(self.root/'video.mp4'),'video_stamp':F.media_stamp(str(self.root/'video.mp4')),'segments':[[0,1],[2,4]]}
  bad=dict(cfg,video_stamp={})
  with self.assertRaises(ValueError):F.safe_raw_cut(str(self.p),bad)
  result=F.safe_raw_cut(str(self.p),cfg);self.assertTrue(result['ok']);self.assertEqual(result['duration'],3)
  self.assertEqual((self.root/'draft_info.json').read_bytes(),(self.p/'draft_info.json').read_bytes())
  with self.assertRaises(ValueError):F.safe_raw_cut(str(self.p),{**self.cfg(),**{'video':cfg['video'],'video_stamp':cfg['video_stamp'],'segments':[[0,1]]}})
 def test_read_job_uses_displayed_source_and_rejects_external_change(self):
  cfg=self.cfg();seen=[]
  def suggest(folder,data):
   seen.append(json.loads((Path(folder)/'draft_info.json').read_bytes()));return {'ok':True,'suggestions':[]}
  with patch.object(C,'api_ai_suggest',side_effect=suggest):F.run(str(self.p),'suggest',cfg)
  self.assertEqual(seen[0]['id'],'main')
  def changed(folder,data):self.write(dict(self.d,duration=9000000));return {'ok':True,'suggestions':[]}
  with patch.object(C,'api_ai_suggest',side_effect=changed):
   with self.assertRaises(ValueError):F.run(str(self.p),'suggest',cfg)
 def test_audio_align_uses_current_draft_and_preserves_absolute_timing(self):
  import ce_features as cf
  cfg={**self.cfg(),'caption_current':True,'audio_b64':'fixture','api_key':'fake','max_words':10}
  (self.p/'draft_info_original.json').write_text('{}')
  with patch.object(cf,'call_gemini_audio',return_value=json.dumps([{'start':1,'end':2,'text':'เนื้อหาใหม่'}])):
   result=F.run(str(self.p),'align',cfg)
  self.assertTrue(result['ok']);d=json.loads((self.p/'draft_info.json').read_bytes());seg=d['tracks'][0]['segments'][0];self.assertEqual(seg['target_timerange']['start'],1000000)
  self.assertEqual((self.p/'draft_info.json').read_bytes(),(self.root/'draft_info.json').read_bytes());self.assertFalse((self.p/'draft_info_original.json').exists())
 def test_audio_align_rejects_stale_selection_before_calling_ai(self):
  with patch.object(C,'api_ai_align_audio') as ai:
   with self.assertRaises(ValueError):F.run(str(self.p),'align',{**self.cfg(),'caption_current':False})
  ai.assert_not_called()
 def test_cancelled_local_process_is_stopped(self):
  import ce_autoclip as ac
  calls=[]
  def progress(**kw):
   calls.append(True)
   if len(calls)>1:raise InterruptedError('cancelled')
  E._CONTEXT.progress=progress
  try:
   start=time.monotonic()
   with self.assertRaises(InterruptedError):ac.ac_run([sys.executable,'-c','import time;time.sleep(10)'])
   self.assertLess(time.monotonic()-start,3)
  finally:E._CONTEXT.__dict__.clear()
 def test_generic_job_reports_errors_and_is_owner_scoped(self):
  with J._lock:J._jobs.clear()
  with patch.object(F,'run',return_value={'error':'bad response'}):
   result=J.start('owner',str(self.p),'silence',{})
   for thread in threading.enumerate():
    if thread.name.startswith('event-'):thread.join(2)
  self.assertEqual(J.status('owner',result['job_id'])['state'],'failed');self.assertFalse(J.status('other',result['job_id'])['ok'])

if __name__=='__main__':unittest.main()
