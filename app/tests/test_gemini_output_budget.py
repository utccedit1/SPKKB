import json,unittest
from unittest.mock import patch
from ks import core_engine as CE,cli_lab_webhook as W
import ce_ai as AI

class Response:
 def __init__(self,data):self.data=data
 def __enter__(self):return self
 def __exit__(self,*a):pass
 def read(self):return json.dumps(self.data).encode()

class GeminiOutputBudgetTests(unittest.TestCase):
 def test_editorial_thinking_reserves_room_for_actual_json(self):
  response=Response({'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'{"cuts":[]}'}]}}]})
  with patch.object(AI,'_task_stage',return_value=False),patch.object(AI,'_pick_available_model',side_effect=lambda m:m),patch.object(AI.urllib.request,'urlopen',return_value=response) as send:
   result=W.request('fictional captions',conf={'ai_backend':'gemini','gemini_api_key':'fixture','gemini_model':'gemini-3.6-flash'},max_tokens=3072)
  config=json.loads(send.call_args.args[0].data)['generationConfig']
  self.assertEqual(config.get('thinkingConfig'),{'thinkingLevel':'low'})
  self.assertEqual(config['maxOutputTokens'],5120)
  self.assertEqual(result,'{"cuts":[]}')
 def test_token_limited_response_never_becomes_a_successful_plan(self):
  response=Response({'candidates':[{'finishReason':'MAX_TOKENS','content':{'parts':[{'text':'{"cuts":[]}'}]}}]})
  with patch.object(AI,'_task_stage',return_value=False),patch.object(AI,'_pick_available_model',side_effect=lambda m:m),patch.object(AI.urllib.request,'urlopen',return_value=response) as send:
   with self.assertRaisesRegex(RuntimeError,'โทเคน'):AI.call_gemini('fixture','gemini-3.6-flash','fictional captions',conf={'ai_backend':'gemini'},max_retries=1)
  self.assertEqual(send.call_count,1)
 def test_thought_text_does_not_get_mixed_into_json(self):
  response=Response({'candidates':[{'finishReason':'STOP','content':{'parts':[{'thought':True,'text':'internal reasoning'},{'text':'{"ok":true}'}]}}]})
  with patch.object(AI,'_task_stage',return_value=False),patch.object(AI,'_pick_available_model',side_effect=lambda m:m),patch.object(AI.urllib.request,'urlopen',return_value=response):
   out=AI.call_gemini('fixture','gemini-3.6-flash','fictional captions',conf={'ai_backend':'gemini'},max_retries=1)
  self.assertEqual(out,'{"ok":true}')
 def test_editorial_model_stays_selected_when_global_pool_prefers_other_model(self):
  response=Response({'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'{"ok":true}'}]}}]})
  with patch.object(AI,'_task_stage',return_value=False),patch.object(AI,'_pick_available_model',return_value='gemini-flash-latest'),patch.object(AI.urllib.request,'urlopen',return_value=response) as send:
   out=W.request('fictional captions',conf={'ai_backend':'gemini','gemini_api_key':'fixture','gemini_model':'gemini-3.6-flash'})
  self.assertEqual(out,'{"ok":true}')
  self.assertIn('/gemini-3.6-flash:generateContent',send.call_args.args[0].full_url)
