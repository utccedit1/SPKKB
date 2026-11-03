import copy,json,unittest
from unittest.mock import patch
from ks import core_engine as CE,cli_lab_webhook as W,event_clip as E
import ce_ai as AI
import ce_config as C

class GeminiEditorialRouting(unittest.TestCase):
 def test_switching_feature_to_gemini_clears_utcc_flag(self):
  cfg={'ai_backend':'webhook','webhook_utcc':True,'ai_routes':{'autoclip':{'backend':'gemini'}}}
  with C.ai_feature('autoclip'):out=C._apply_ai_route(copy.deepcopy(cfg))
  self.assertEqual(out['ai_backend'],'gemini');self.assertFalse(out['webhook_utcc'])
 def test_direct_gemini_provider_does_not_require_utcc(self):
  with patch.object(CE,'load_config',return_value={'gemini_api_key':'fixture-key','gemini_model':'fixture-model','webhook_utcc':True}):
   cfg,label=E.provider_config('gemini')
  self.assertEqual(cfg['ai_backend'],'gemini');self.assertFalse(cfg['webhook_utcc']);self.assertIn('Gemini',label)
 def test_editorial_dispatch_uses_selected_gemini_conf_even_when_global_is_utcc(self):
  class Response:
   def __enter__(self):return self
   def __exit__(self,*args):pass
   def read(self):return json.dumps({'candidates':[{'content':{'parts':[{'text':'{"cuts":[]}'}]}}]}).encode()
  cfg={'ai_backend':'gemini','webhook_utcc':False,'gemini_api_key':'fixture-key','gemini_model':'fixture-model'}
  with patch.object(AI,'load_config',return_value={'ai_backend':'webhook','webhook_utcc':True,'webhook_url':'https://example.invalid'}),patch.object(AI,'_pick_available_model',side_effect=lambda m:m),patch.object(AI,'_task_stage',return_value=False),patch.object(AI.urllib.request,'urlopen',return_value=Response()) as send,patch.object(CE,'call_webhook',side_effect=AssertionError('UTCC must not be called')):
   result=W.request('fictional timed captions',conf=cfg,utcc=True,system='JSON',max_tokens=1024)
  self.assertEqual(result,'{"cuts":[]}');self.assertEqual(send.call_count,1)
  req=send.call_args.args[0];self.assertIn('/fixture-model:generateContent',req.full_url)
  self.assertEqual(json.loads(req.data)['generationConfig']['maxOutputTokens'],1024)
 def test_missing_key_fails_without_calling_webhook(self):
  with patch.object(CE,'call_webhook',side_effect=AssertionError('unexpected request')):
   with self.assertRaisesRegex(ValueError,'Gemini'):W.request('fixture',conf={'ai_backend':'gemini'})
 def test_route_ui_exposes_key_names_and_active_labels_without_secrets(self):
  import ce_features as F
  cfg={'gemini_keys':[{'name':'My Gemini','key':'fixture-secret'}],'gemini_model':'fixture-model','ai_backend':'gemini','ai_routes':{}}
  with patch.object(F,'load_config',return_value=cfg):out=F.api_get_ai_routes()
  self.assertEqual(out['keys'],['My Gemini']);self.assertIn('gemini',out['backends'])
  self.assertTrue(all(f['active_label'] for f in out['features']))
  self.assertNotIn('fixture-secret',json.dumps(out))
 def test_cli_single_plan_honors_explicit_gemini_without_utcc(self):
  from ks import cli_lab as L
  import tempfile
  from pathlib import Path
  with tempfile.TemporaryDirectory() as folder:
   p=Path(folder);(p/'draft_info.json').write_text(json.dumps({'duration':60000000,'materials':{'texts':[{'id':'m','content':json.dumps({'text':'fictional speech'})}]},'tracks':[{'type':'text','segments':[{'id':'s','material_id':'m','target_timerange':{'start':0,'duration':10000000}}]}]}))
   requested=[]
   def provider(backend):
    requested.append(backend)
    if backend!='gemini':raise AssertionError('wrong provider')
    return {'ai_backend':'gemini','gemini_api_key':'fixture-key'},'Gemini'
   with patch.object(E,'provider_config',side_effect=provider),patch.object(W,'request',return_value='{"start":0,"end":10,"reason":"fixture"}'),patch.object(L,'_store_plan'):
    out=L.handle('alice',p,{'action':'plan','mode':'single','instruction':'fictional request','backend':'gemini'})
   self.assertTrue(out['ok']);self.assertEqual(requested,['gemini'])
 def test_align_route_uses_selected_gemini_key_for_audio(self):
  cfg={'audio_backend':'webhook','audio_api_key':'old-fixture','gemini_api_key':'main-fixture','gemini_keys':[{'name':'audio-key','key':'selected-fixture'}],'ai_routes':{'align':{'backend':'gemini','key_name':'audio-key','model':'audio-model'}}}
  with C.ai_feature('align'):out=C._apply_ai_route(copy.deepcopy(cfg))
  self.assertEqual(out['audio_backend'],'gemini');self.assertEqual(out['audio_api_key'],'selected-fixture');self.assertEqual(out['gemini_model'],'audio-model')
 def test_gemini_cancellation_discards_late_response_without_webhook(self):
  import threading
  release=threading.Event()
  def progress(message):
   if 'ผ่านไป' in message:raise InterruptedError('cancelled fixture')
  try:
   with patch.object(CE,'call_gemini',side_effect=lambda *a,**k:release.wait(1)),patch.object(CE,'call_webhook',side_effect=AssertionError('no fallback')),patch.object(W,'POLL_SECONDS',.01):
    with self.assertRaises(InterruptedError):W.request('fixture',conf={'ai_backend':'gemini','gemini_api_key':'fixture'},progress=progress)
  finally:release.set()
 def test_sfx_picker_reports_align_route_instead_of_global_audio_webhook(self):
  from ks import sfx_library
  cfg={'audio_backend':'webhook','audio_webhook_url':'https://example.invalid','gemini_api_key':'fixture','ai_routes':{'align':{'backend':'gemini'}}}
  with patch.object(CE,'load_config',side_effect=lambda:C._apply_ai_route(copy.deepcopy(cfg))):
   self.assertEqual(sfx_library.provider(),'Gemini งานเสียง')
