import unittest
from ks import kinetic_jobs as J
class SemanticSettingsTests(unittest.TestCase):
 def test_semantic_mode_is_explicit_boolean_and_requires_measured_phrase_mode(self):
  for data in [dict(semantic_ai='yes'),dict(semantic_ai=True,caption_one_line=False)]:
   with self.subTest(data=data),self.assertRaises(ValueError):J._settings(data)
  self.assertTrue(J._settings(dict(semantic_ai=True,caption_one_line=True))['semantic_ai'])

class SemanticFullPlanTests(unittest.TestCase):
 from test_kinetic_text import KineticServiceTests as _Fixture
 setUp=_Fixture.setUp
 def test_gemini_selection_is_saved_and_prepare_uses_the_same_plan(self):
  import json
  from pathlib import Path
  from unittest.mock import patch
  from ks import event_clip as E,cli_lab_webhook as W,caption_studio as S
  meta=J.handle('alice',self.proj,dict(action='kinetic_meta'))
  choice=dict(blocks=[dict(cue_id='one',rows=['หลักการ ยังใช้ได้'],form='punch',role='result',accent=0)])
  with patch.object(E,'provider_config',return_value=({'ai_backend':'gemini','gemini_api_key':'fixture'},'Gemini')),patch.object(W,'request',return_value=choice):
   result=J.handle('alice',self.proj,dict(action='kinetic_full_plan',source_hash=meta['source_hash'],media_hash=meta['media_hash'],semantic_ai=True,caption_one_line=True,backend='gemini'))
  self.assertIn('Gemini',result['provider']);self.assertEqual(result['plan']['blocks'][0]['units'][0]['text'],'หลักการ ยังใช้ได้')
  with patch.object(S,'output_root',return_value=self.root/'outputs'):
   ready=J.handle('alice',self.proj,dict(action='kinetic_prepare',plan_id=result['plan_id']))
  report=json.loads((Path(ready['destination'])/'kinetic_text_report.json').read_text());self.assertEqual(report['entries'],result['preview']['entries']);self.assertEqual((self.proj/'draft_info.json').read_bytes(),self.raw)
 def test_provider_timeout_has_no_retry_or_local_success_fallback(self):
  from unittest.mock import patch
  from ks import event_clip as E,cli_lab_webhook as W,cli_lab as L
  meta=J.handle('alice',self.proj,dict(action='kinetic_meta'))
  with patch.object(E,'provider_config',return_value=({'ai_backend':'gemini','gemini_api_key':'fixture'},'Gemini')),patch.object(W,'request',side_effect=TimeoutError('fixture timeout')) as request,patch.object(L,'_store_plan',side_effect=AssertionError('must not persist')):
   with self.assertRaises(TimeoutError):J.handle('alice',self.proj,dict(action='kinetic_full_plan',source_hash=meta['source_hash'],media_hash=meta['media_hash'],semantic_ai=True,caption_one_line=True,backend='gemini'))
   self.assertEqual(request.call_count,1)
