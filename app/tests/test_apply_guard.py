import copy,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ks import core_engine as C,apply_guard as G,event_timeline as T

class ApplySafetyTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.root=Path(self.tmp.name);self.p=self.root/'Timelines'/'main';self.p.mkdir(parents=True)
  self.d={'id':'main','duration':3000000,'materials':{'texts':[{'id':'m','type':'subtitle','content':json.dumps({'text':'new content matters','styles':[{'range':[0,19],'size':12}]})}]},'tracks':[{'type':'text','segments':[{'id':'s','material_id':'m','target_timerange':{'start':0,'duration':3000000}}]}]}
  self.write(self.d);self.closed=patch.object(T,'ensure_closed');self.closed.start();self.addCleanup(self.closed.stop)
 def write(self,d):
  raw=json.dumps(d).encode();(self.p/'draft_info.json').write_bytes(raw);(self.root/'draft_info.json').write_bytes(raw)
 def cfg(self):return {**C.api_captions(str(self.p)), 'karaoke_on':True,'super_on':False,'min_words':1}
 def test_long_caption_does_not_silently_skip_highlight(self):
  text='how much AI has involved into the businesses'
  self.d['materials']['texts'][0]['content']=json.dumps({'text':text,'styles':[{'range':[0,len(text)],'size':12}]});self.write(self.d)
  result=C.api_apply(str(self.p),{**self.cfg(),'max_chars':40})
  self.assertTrue(result['ok']);self.assertIn('ซับยาว 1 ท่อน',result['msg'])
  d=json.loads((self.p/'draft_info.json').read_text());segments=d['tracks'][0]['segments'];self.assertGreater(len(segments),1)
  self.assertEqual(sum(s['target_timerange']['duration'] for s in segments),3000000)
  materials={m['id']:m for m in d['materials']['texts']}
  self.assertTrue(all(json.loads(materials[s['material_id']]['content'])['text']==text for s in segments))
 def test_length_threshold_never_disables_effect_across_styles(self):
  texts=['the source captions keep the effect working','this is a longer English caption with complete context that still needs highlighting in every project','การสร้างเนื้อหาที่มีคุณภาพต้องรักษาความหมายของประโยคต้นฉบับไว้ให้ครบถ้วนและเข้าใจง่าย']
  for text in texts:
   for mode in ['line','word_box','color_sweep','box_travel']:
    with self.subTest(text=text,mode=mode):
     self.d['materials']['texts'][0]['content']=json.dumps({'text':text,'styles':[{'range':[0,len(text)],'size':12}]});self.write(self.d)
     cfg={**C.api_captions(str(self.p),current=True),'karaoke_on':True,'super_on':False,'min_words':1,'max_chars':20,'karaoke_style':mode}
     result=C.api_apply(str(self.p),cfg);self.assertTrue(result.get('ok'),result);self.assertIn('ไลน์เน้น 1 ซับ',result['msg']);self.assertIn('ซับยาว 1 ท่อน',result['msg'])
     output=json.loads((self.p/'draft_info.json').read_bytes());self.assertEqual(sum(s['target_timerange']['duration'] for s in output['tracks'][0]['segments']),3000000)
 def test_length_fix_respects_explicit_selection(self):
  text='a long caption outside the selection must remain unchanged'
  self.d['materials']['texts'][0]['content']=json.dumps({'text':text,'styles':[{'range':[0,len(text)],'size':12}]});self.write(self.d)
  out=C.api_apply(str(self.p),{**self.cfg(),'only':[],'max_chars':10})
  self.assertTrue(out['ok']);self.assertIn('ไลน์เน้น 0 ซับ',out['msg']);draft=json.loads((self.p/'draft_info.json').read_bytes());self.assertEqual(len(draft['tracks'][0]['segments']),1)
 def test_single_word_gets_effect_even_with_legacy_two_word_setting(self):
  for text in ['Yes','จริง','AI']:
   for mode in ['line','word_box','color_sweep','box_travel']:
    with self.subTest(text=text,mode=mode):
     self.d['materials']['texts'][0]['content']=json.dumps({'text':text,'styles':[{'range':[0,len(text)],'size':12}]});self.write(self.d)
     cfg={**C.api_captions(str(self.p),current=True),'karaoke_on':True,'super_on':False,'min_words':2,'karaoke_style':mode,'normal_color':'#ffffff','highlight_color':'#ffee00'}
     result=C.api_apply(str(self.p),cfg);self.assertTrue(result.get('ok'),result);self.assertIn('ไลน์เน้น 1 ซับ',result['msg'])
     output=json.loads((self.p/'draft_info.json').read_bytes());tracks=[t for t in output['tracks'] if t.get('type')=='text'];self.assertTrue(all(t['segments'] for t in tracks));self.assertEqual(sum(s['target_timerange']['duration'] for s in tracks[0]['segments']),3000000)
     materials={m['id']:m for m in output['materials']['texts']};self.assertTrue(all(s['material_id']!='m' for t in tracks for s in t['segments']))
 def test_single_word_outside_selection_stays_unchanged(self):
  self.d['materials']['texts'][0]['content']=json.dumps({'text':'Yes','styles':[]});self.write(self.d)
  result=C.api_apply(str(self.p),{**self.cfg(),'only':[],'min_words':2});self.assertTrue(result['ok']);output=json.loads((self.p/'draft_info.json').read_bytes());self.assertEqual(output['tracks'][0]['segments'][0]['material_id'],'m')
 def test_external_edit_rejected_without_any_writes_and_reload_preserves_edit(self):
  first=C.api_apply(str(self.p),self.cfg());self.assertTrue(first['ok']);stale=self.cfg()
  changed=json.loads((self.p/'draft_info.json').read_bytes());m=changed['materials']['texts'][0];content=json.loads(m['content']);content['text']='latest edit survives';m['content']=json.dumps(content);self.write(changed)
  before={str(p):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
  result=C.api_apply(str(self.p),stale);self.assertIn('error',result)
  self.assertEqual(before,{str(p):p.read_bytes() for p in self.root.rglob('*') if p.is_file()})
  cfg=self.cfg();self.assertTrue(C.api_apply(str(self.p),cfg)['ok'])
  saved=json.loads((self.p/'draft_info.json').read_bytes());self.assertTrue(any('latest edit survives' in m['content'] for m in saved['materials']['texts']))
 def test_repeat_uses_known_baseline_and_backup_restores_all_files(self):
  cfg=self.cfg();self.assertTrue(C.api_apply(str(self.p),cfg)['ok']);cfg=self.cfg()
  before=(self.p/'draft_info.json').read_bytes();result=C.api_apply(str(self.p),cfg);self.assertTrue(result['ok'])
  self.assertEqual((self.p/'draft_info.json').read_bytes(),(self.root/'draft_info.json').read_bytes())
  self.assertEqual(T.read_checkpoint(str(self.p),result['backup_name'])['draft_info.json'],before)
  self.assertEqual(C.api_captions(str(self.p))['captions'][0]['text'],'new content matters')
 def test_missing_hash_or_open_capcut_never_creates_backup(self):
  self.assertIn('error',C.api_apply(str(self.p),{'karaoke_on':True}))
  with patch.object(T,'ensure_closed',side_effect=ValueError('CapCut running')):
   self.assertIn('error',C.api_apply(str(self.p),self.cfg()))
  self.assertFalse((self.p/T.BACKUPS).exists());self.assertFalse((self.p/'draft_info_original.json').exists())
 def test_edit_during_generation_does_not_overwrite_latest(self):
  prepared=G.prepare(str(self.p),self.cfg());changed=copy.deepcopy(self.d);changed['duration']=4000000;self.write(changed)
  with self.assertRaises(ValueError):G.commit(str(self.p),prepared,self.d)
  self.assertEqual(json.loads((self.p/'draft_info.json').read_bytes())['duration'],4000000)
 def test_commit_failure_rolls_back_live_and_cache(self):
  prepared=G.prepare(str(self.p),self.cfg());real=T.replace_files;calls=[]
  def fail_once(proj,files):
   calls.append(True)
   if len(calls)==1:
    T.atomic_write(self.p/'draft_info.json',b'{}');raise OSError('disk error')
   return real(proj,files)
  before=(self.p/'draft_info.json').read_bytes()
  with patch.object(T,'replace_files',side_effect=fail_once):
   with self.assertRaises(OSError):G.commit(str(self.p),prepared,self.d)
  self.assertEqual((self.p/'draft_info.json').read_bytes(),before)
  self.assertFalse((self.p/'draft_info_original.json').exists())
 def test_caption_loading_is_read_only_even_with_stale_cache(self):
  (self.p/'draft_info_original.json').write_text('{}');before={str(p):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
  C.api_captions(str(self.p));self.assertEqual(before,{str(p):p.read_bytes() for p in self.root.rglob('*') if p.is_file()})
