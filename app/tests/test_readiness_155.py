"""Regression cases for the seven readiness findings (synthetic inputs only)."""
import unittest

def run_probes():
 import sys,os,json,tempfile,copy,io,urllib.error
 from pathlib import Path
 from unittest.mock import patch
 sys.path.insert(0,str(Path('app').resolve()))
 from ks import ce_ai as AI,cli_lab_commit as C,event_timeline as T,ce_config as CFG
 results={}
 # Personal key quota failure must not silently select the shared key pool.
 seen=[]
 def ai_call(key,*args,**kwargs):
  seen.append(key)
  if key=='fixture-personal':raise urllib.error.HTTPError('https://example.invalid',429,'quota',{},io.BytesIO(b'fixture'))
  return 'fixture result'
 with patch('ce_config.load_config',return_value={}),patch.object(AI,'call_gemini',side_effect=ai_call),patch.object(AI,'_load_config_raw',return_value={'gemini_keys':[{'name':'shared','key':'fixture-shared'}]}):
  try:value=AI._gemini_with_fallback('fixture-personal','fixture-model','synthetic prompt','synthetic system')
  except RuntimeError:value=('',None)
 results['shared_key_fallback']={'confirmed':seen!=['fixture-personal'],'calls':len(seen),'result_returned':value[0]=='fixture result'}
 # Generic CLI import ignores a new material's catalog entry even when output has it.
 with tempfile.TemporaryDirectory() as tmp,patch.object(T,'ensure_closed'),patch.dict(os.environ,{'KS_JOB_STATE_DIR':tmp+'/receipts'}):
  root=Path(tmp);project=root/'project';out=root/'output';project.mkdir();out.mkdir()
  old=root/'old.mp4';old.write_bytes(b'old fixture');new=out/'new.mp4';new.write_bytes(b'new fixture')
  draft={'id':'fixture-project','duration':6000000,'materials':{'videos':[{'id':'old','path':str(old),'local_material_id':'old-entry'}]},'tracks':[{'type':'video','segments':[{'id':'s','material_id':'old','target_timerange':{'start':0,'duration':6000000}}]}]}
  edited=copy.deepcopy(draft);edited['materials']['videos'].append({'id':'new','path':str(new),'local_material_id':'new-entry'})
  edited['tracks'].append({'type':'video','segments':[{'id':'new-s','material_id':'new','target_timerange':{'start':1000000,'duration':2000000}}]})
  (project/'draft_info.json').write_text(json.dumps(draft));(out/'draft_info.json').write_text(json.dumps(edited))
  (project/'draft_meta_info.json').write_text(json.dumps({'draft_id':'fixture-project','draft_materials':[{'type':0,'value':[{'id':'old-entry','file_Path':str(old)}]}]}))
  (out/'draft_meta_info.json').write_text(json.dumps({'draft_id':'fixture-project','draft_materials':[{'type':0,'value':[{'id':'new-entry','file_Path':str(new)}]}]}))
  ticket=C.preview('fixture-owner',project,out);C.commit('fixture-owner',project,ticket['install_id'])
  final=json.loads((project/'draft_info.json').read_bytes());meta=json.loads((project/'draft_meta_info.json').read_bytes())
  mat=next(m for m in final['materials']['videos'] if m['id']=='new')
  entries=[e for g in meta['draft_materials'] for e in g['value']]
  results['generic_import_catalog']={'confirmed':not any(e.get('id')==mat['local_material_id'] for e in entries),'media_file_exists':Path(mat['path']).is_file(),'new_material_id_registered':any(e.get('id')==mat['local_material_id'] for e in entries)}
 # Project-local recognition cannot change provider credentials; other state is scoped.
 from ks import proofread as P
 with tempfile.TemporaryDirectory() as tmp,patch.object(P,'CONFIG_DIR',tmp):
  saved_context=CFG.STATE._context.set(dict(CFG.STATE._data()))
  CFG.STATE.bind('fixture-session-a','fixture-user-a',workspace='one');P.remember('FixtureVocabulary')
  CFG.STATE.bind('fixture-session-b','fixture-user-b',workspace='two');words=P.lexicon()
  results['proofread_lexicon_shared']={'confirmed':'FixtureVocabulary' in words,'read_by_second_account':bool(words)}
  CFG.STATE._context.reset(saved_context)
 # Legacy restore/audio alignment leaves existing timeline mirrors stale.
 from ks import unified_history as H,core_engine as CE
 with tempfile.TemporaryDirectory() as tmp,patch.object(T,'ensure_closed'):
  p=Path(tmp);live={'id':'history-fixture','duration':3000000,'materials':{},'tracks':[]};old=dict(live,duration=6000000)
  raw=json.dumps(live).encode()
  for name in ('draft_info.json','draft_content.json','template-2.tmp'):(p/name).write_bytes(raw)
  (p/'draft_info_backup.json').write_text(json.dumps(old))
  H.restore(p,{'id':'initial:original'})
  results['legacy_restore_mirrors']={'confirmed':json.loads((p/'draft_info.json').read_bytes())!=json.loads((p/'template-2.tmp').read_bytes()),'live_duration':json.loads((p/'draft_info.json').read_bytes())['duration'],'mirror_duration':json.loads((p/'template-2.tmp').read_bytes())['duration']}
 # Render real synthetic media; tests do not depend on audit files.
 from ks import ce_autoclip as AC
 with tempfile.TemporaryDirectory() as tmp:
  for audio in (False,True):
   video=str(Path(tmp)/('audio.mp4' if audio else 'silent.mp4'))
   command=[AC.ac_ffmpeg_bin(),'-y','-f','lavfi','-i','testsrc2=size=160x90:rate=10:duration=1']
   if audio:command+=['-f','lavfi','-i','sine=frequency=440:duration=1','-c:a','aac']
   rc,_,err=AC.ac_run(command+['-c:v','libx264',video])
   if rc:raise AssertionError(err)
   output=str(Path(tmp)/('render-audio.mp4' if audio else 'render-silent.mp4'))
   AC.ac_render_segments(video,[(0,.3),(.5,.9)],output)
   rc,streams,err=AC.ac_run([AC.ac_ffprobe_bin(),'-v','error','-show_entries','stream=codec_type','-of','csv=p=0',output])
   assert rc==0 and 'video' in streams and ('audio' in streams)==audio,(streams,err)
  results['silent_video_export']={'confirmed':False,'output_created':True}
 return results

class ReadinessRegression(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.results=run_probes()
 def test_shared_key_fallback(self):
  self.assertIn("shared_key_fallback",self.results)
  self.assertFalse(self.results["shared_key_fallback"]["confirmed"],self.results["shared_key_fallback"])
 def test_generic_import_catalog(self):
  self.assertIn("generic_import_catalog",self.results)
  self.assertFalse(self.results["generic_import_catalog"]["confirmed"],self.results["generic_import_catalog"])
 def test_proofread_lexicon_shared(self):
  self.assertIn("proofread_lexicon_shared",self.results)
  self.assertFalse(self.results["proofread_lexicon_shared"]["confirmed"],self.results["proofread_lexicon_shared"])
 def test_legacy_restore_mirrors(self):
  self.assertIn("legacy_restore_mirrors",self.results)
  self.assertFalse(self.results["legacy_restore_mirrors"]["confirmed"],self.results["legacy_restore_mirrors"])
 def test_silent_video_export(self):
  self.assertIn("silent_video_export",self.results)
  self.assertFalse(self.results["silent_video_export"]["confirmed"],self.results["silent_video_export"])

 def test_fallback_only_uses_current_owner_pool(self):
  from ks import ce_ai as AI,ce_config as CFG
  from unittest.mock import patch
  import urllib.error,io
  saved=CFG.STATE._context.set({'_current_uid':'fixture-owner'})
  self.addCleanup(CFG.STATE._context.reset,saved)
  calls=[]
  def call(key,*args,**kwargs):
   calls.append(key)
   if key=='fixture-primary':raise urllib.error.HTTPError('https://example.invalid',429,'quota',{},io.BytesIO(b'fixture'))
   return 'allowed result'
  with patch('ce_config.load_config',return_value={'gemini_keys':[{'key':'fixture-allowed'}]}),patch.object(AI,'call_gemini',side_effect=call),patch.object(AI,'_load_config_raw',side_effect=AssertionError('raw config forbidden')):
   self.assertEqual(AI._gemini_with_fallback('fixture-primary','model','fixture','fixture')[0],'allowed result')
  self.assertEqual(calls,['fixture-primary','fixture-allowed'])

 def test_placeholder_original_is_not_copied_or_reregistered(self):
  import sys,json,tempfile,os,copy
  from pathlib import Path
  from unittest.mock import patch
  from ks import cli_lab_commit as C,event_timeline as T
  with tempfile.TemporaryDirectory() as tmp,patch.object(T,'ensure_closed'),patch.dict(os.environ,{'KS_JOB_STATE_DIR':tmp+'/receipts'}):
   p=Path(tmp)/'project';o=Path(tmp)/'output';p.mkdir();o.mkdir();(p/'materials/video').mkdir(parents=True)
   original=p/'materials/video/original.mp4';original.write_bytes(b'fixture original')
   d={'id':'fixture','duration':6000000,'materials':{'videos':[{'id':'original','path':'##_draftpath_placeholder_ABC_##/materials/video/original.mp4','local_material_id':'original-entry'}]},'tracks':[{'type':'video','segments':[{'id':'s','material_id':'original','target_timerange':{'start':0,'duration':6000000}}]}]}
   e=copy.deepcopy(d);e['materials']['videos'][0]['path']=str(original)
   (p/'draft_info.json').write_text(json.dumps(d));(o/'draft_info.json').write_text(json.dumps(e));(p/'draft_meta_info.json').write_text(json.dumps({'draft_materials':[{'type':0,'value':[{'id':'original-entry','file_Path':str(original)}]}]}))
   preview=C.preview('fixture-owner',p,o);C.commit('fixture-owner',p,preview['install_id'])
   final=json.loads((p/'draft_info.json').read_bytes());material=final['materials']['videos'][0]
   result={'unchanged_original_copied':material['path']!=str(original),'original_catalog_id_changed':material['local_material_id']!='original-entry'}
  self.assertEqual(result,{'unchanged_original_copied':False,'original_catalog_id_changed':False})

 def test_copy_corruption_keeps_project_and_cleans_new_assets(self):
  from pathlib import Path
  from unittest.mock import patch
  import tempfile,json,os,copy,shutil
  from ks import cli_lab_commit as C,event_timeline as T
  with tempfile.TemporaryDirectory() as tmp,patch.object(T,'ensure_closed'),patch.dict(os.environ,{'KS_JOB_STATE_DIR':tmp+'/receipts'}):
   p=Path(tmp)/'project';out=Path(tmp)/'output';p.mkdir();out.mkdir()
   media=out/'new.mp4';media.write_bytes(b'new fixture')
   draft={'id':'fixture','duration':1000000,'materials':{'videos':[{'id':'new','path':str(media)}]},'tracks':[{'type':'video','segments':[{'id':'s','material_id':'new','target_timerange':{'start':0,'duration':1000000}}]}]}
   raw=json.dumps(draft).encode();(p/'draft_info.json').write_bytes(raw);(out/'draft_info.json').write_bytes(raw)
   ticket=C.preview('fixture-owner',p,out)
   def corrupt(src,dst):Path(dst).write_bytes(b'corrupted copy')
   with patch.object(C.shutil,'copyfile',side_effect=corrupt):
    with self.assertRaisesRegex(ValueError,'คัดลอก'):C.commit('fixture-owner',p,ticket['install_id'])
   self.assertEqual((p/'draft_info.json').read_bytes(),raw)
   self.assertFalse(list((p/'cli_lab_assets').glob('*')))
   self.assertTrue(C.commit('fixture-owner',p,ticket['install_id'])['ok'])

 def test_nested_and_root_audio_are_registered(self):
  from pathlib import Path
  from unittest.mock import patch
  import tempfile,json,os,copy
  from ks import cli_lab_commit as C,event_timeline as T
  from ks.cli_lab_nested import drafts
  with tempfile.TemporaryDirectory() as tmp,patch.object(T,'ensure_closed'),patch.dict(os.environ,{'KS_JOB_STATE_DIR':tmp+'/receipts'}):
   p=Path(tmp)/'project';out=Path(tmp)/'output';p.mkdir();out.mkdir()
   main=Path(tmp)/'main.mp4';main.write_bytes(b'fixture main')
   original={'id':'fixture','duration':1000000,'materials':{'videos':[{'id':'main','path':str(main)}]},'tracks':[{'type':'video','segments':[{'id':'s','material_id':'main','target_timerange':{'start':0,'duration':1000000}}]}]}
   edited=copy.deepcopy(original)
   for filename in ('root.wav','nested.wav'):(out/filename).write_bytes(b'fixture audio')
   edited['materials']['audios']=[{'id':'same-id','path':str(out/'root.wav')}]
   edited['materials']['drafts']=[{'id':'nested','draft':{'id':'child','materials':{'audios':[{'id':'same-id','path':str(out/'nested.wav')}]},'tracks':[]}}]
   (p/'draft_info.json').write_text(json.dumps(original));(out/'draft_info.json').write_text(json.dumps(edited))
   ticket=C.preview('fixture-owner',p,out);C.commit('fixture-owner',p,ticket['install_id'])
   final=json.loads((p/'draft_info.json').read_bytes());meta=json.loads((p/'draft_meta_info.json').read_bytes())
   entries=[e for group in meta['draft_materials'] for e in group['value']]
   audio=[m for node in drafts(final) for m in node['materials'].get('audios',[])]
   self.assertEqual(len(audio),2);self.assertEqual(len({m['local_material_id'] for m in audio}),2)
   for m in audio:
    self.assertTrue(Path(m['path']).is_file())
    self.assertTrue(any(e['id']==m['local_material_id'] and e['file_Path']==m['path'] and e['metetype']=='audio' for e in entries))
   self.assertEqual(final['materials']['videos'],original['materials']['videos'])
