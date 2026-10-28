import base64,json,sys,tempfile,unittest,wave,math,struct
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ks import sfx_library as S,core_engine as C

class SoundTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.audio=self.root/'sound.wav'
  with wave.open(str(self.audio),'wb') as f:
   f.setnchannels(1);f.setsampwidth(2);f.setframerate(16000);f.writeframes(b''.join(struct.pack('<h',int(5000*math.sin(i*2*math.pi*440/16000))) for i in range(8000)))
  self.store=patch.object(S.Config,'CONFIG_DIR',str(self.root/'settings'));self.store.start();self.addCleanup(self.store.stop)
  self.conf=patch.object(C,'load_config',return_value={'gemini_api_key':'test'});self.conf.start();self.addCleanup(self.conf.stop)
 def cfg(self):return {'dir':str(self.root),'file':'sound.wav','send_audio':True}
 def test_manual_description_persists_and_invalidates_when_file_changes(self):
  S.save(str(self.root),'sound.wav','short soft chime');self.assertEqual(S.descriptions(str(self.root)),{'sound.wav':'short soft chime'});self.assertEqual(S.entries(str(self.root))['sound.wav']['source'],'human')
  self.audio.write_bytes(self.audio.read_bytes()+b'changed');self.assertEqual(S.descriptions(str(self.root)),{})
 def test_real_audio_bytes_sent_once_and_result_cached(self):
  def listen(*args,**kw):
   data=base64.b64decode(args[3]);self.assertTrue(data.startswith(b'RIFF'));self.assertGreater(len(data),1000);self.assertNotIn('sound.wav',args[2]);self.assertEqual(kw['mime'],'audio/wav');return json.dumps({'description':'เสียงโทนสูงสั้น','use':'เน้นคำ','avoid':'ประเด็นเศร้า'})
  with patch.object(C,'call_gemini_audio',side_effect=listen) as ai:
   result=S.analyze(self.cfg());again=S.analyze(self.cfg())
  self.assertTrue(result['audio_sent']);self.assertEqual(result['entries']['sound.wav']['source'],'audio_ai');self.assertTrue(again['cached']);ai.assert_called_once()
 def test_bad_audio_provider_result_not_saved(self):
  with patch.object(C,'call_gemini_audio',return_value='{"error":"audio unavailable"}'):
   with self.assertRaises(ValueError):S.analyze(self.cfg())
  self.assertEqual(S.entries(str(self.root)),{})
 def test_upload_requires_explicit_request_and_configured_audio_provider(self):
  with patch.object(C,'call_gemini_audio') as ai:
   with self.assertRaises(ValueError):S.analyze({**self.cfg(),'send_audio':False})
   with patch.object(C,'load_config',return_value={'ai_backend':'webhook','webhook_url':'https://example.test'}):
    with self.assertRaises(ValueError):S.analyze(self.cfg())
   ai.assert_not_called()
 def test_traversal_and_symlink_escape_are_rejected(self):
  with tempfile.TemporaryDirectory() as outside:
   p=Path(outside)/'outside.wav';p.write_bytes(self.audio.read_bytes());(self.root/'escape.wav').symlink_to(p)
   for rel in ['../outside.wav','escape.wav']:
    with self.assertRaises(ValueError):S.save(str(self.root),rel,'test')

 def test_audio_task_does_not_depend_on_caption_reload_or_edit_project(self):
  from ks import feature_tasks as F
  with patch.object(S,'analyze',return_value={'ok':True}) as analyze,patch.object(F,'validate_source',side_effect=AssertionError('must not read draft')):
   self.assertTrue(F.run('/not-a-project','sfx_listen',self.cfg())['ok'])
  analyze.assert_called_once()

 def test_blocked_folder_scan_times_out_and_reuses_one_worker(self):
  import threading
  import ce_features as F
  blocked=threading.Event()
  def walk(*args):blocked.wait(2);return []
  try:
   with patch.object(F,'_walk_sfx_files',side_effect=walk) as scanner,patch.object(F,'SFX_SCAN_TIMEOUT',0.01):
    for _ in range(2):
     with self.assertRaises(TimeoutError):F.list_sfx_files(str(self.root))
    scanner.assert_called_once()
  finally:blocked.set()

 def test_audio_timeout_is_clear_and_never_cached_as_listened(self):
  with patch.object(C,'call_gemini_audio',side_effect=TimeoutError):
   with self.assertRaisesRegex(ValueError,'ตอบช้า'):S.analyze(self.cfg())
  self.assertEqual(S.entries(str(self.root)),{})
