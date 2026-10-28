import json,sys,unittest
from pathlib import Path
from unittest.mock import patch
from contextlib import nullcontext
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ks import broll as B

class MemeTests(unittest.TestCase):
 def suggest(self,data,mode):
  with patch.object(B,'_collect_windows',return_value=([{'index':0,'start':0,'end':5,'text':'surprised by the result'}],None)),patch.object(B.CE,'effective_ai_label',return_value={'label':'test'}),patch.object(B.CE,'ai_feature',return_value=nullcontext()),patch.object(B.CE,'load_config',return_value={'ai_backend':'gemini','gemini_api_key':'test'}),patch.object(B.CE,'call_gemini',return_value=json.dumps(data)) as call:
   value=B.suggest('/fixture',{'media_kind':mode});prompt=call.call_args.args[2]
  return value,prompt
 def test_meme_mode_uses_meme_sources_and_context(self):
  result,prompt=self.suggest([{'start':1,'end':3,'query':'surprised pikachu','label':'ตกใจ','kind':'footage'}],'meme');item=result['items'][0]
  self.assertEqual(item['kind'],'meme');self.assertIn('https://tenor.com/search/surprised-pikachu-gifs',[x['url'] for x in item['search_links']]);self.assertIn('ไม่แทรกมุก',prompt)
 def test_mixed_keeps_both_types(self):
  result,_=self.suggest([{'start':0,'end':2,'query':'students walking','kind':'footage'},{'start':2,'end':4,'query':'confused reaction','kind':'meme'}],'mixed');self.assertEqual([x['kind'] for x in result['items']],['footage','meme'])
 def test_empty_meme_result_is_honest_and_not_random(self):
  result,_=self.suggest([],'meme');self.assertEqual(result['items'],[]);self.assertIn('warn',result)
 def test_outside_timeline_and_nonfinite_ranges_rejected(self):
  result,_=self.suggest([{'start':float('nan'),'end':3,'query':'reaction'},{'start':10,'end':12,'query':'reaction'}],'mixed');self.assertIn('error',result)
 def test_links_encode_untrusted_query(self):
  links=B.search_links('a?x=1 & <script>','meme');self.assertTrue(all('<script>' not in x['url'] and ' ' not in x['url'] for x in links))

 def test_generated_overlays_excluded_and_repeated_highlight_lines_merged(self):
  import tempfile
  with tempfile.TemporaryDirectory() as folder:
   d={'materials':{'texts':[{'id':'m','content':json.dumps({'text':'Yes','styles':[]})}]},'tracks':[{'type':'text','segments':[{'id':'s1','material_id':'m','target_timerange':{'start':0,'duration':500000}},{'id':'s2','material_id':'m','target_timerange':{'start':500000,'duration':500000}}]},{'type':'text','name':'Super Text','segments':[{'id':'overlay','material_id':'m','target_timerange':{'start':0,'duration':1000000}}]}]}
   (Path(folder)/'draft_info.json').write_text(json.dumps(d));rows,error=B._collect_windows(folder)
  self.assertIsNone(error);self.assertEqual(len(rows),1);self.assertEqual(rows[0]['end'],1)
