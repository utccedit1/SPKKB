import copy,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ks import caption_loanwords as L,caption_resegment as R,event_clip as E,event_timeline as T

class CaptionResegmentTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.proj=Path(self.tmp.name)/'Project'/'Timelines'/'main';self.proj.mkdir(parents=True)
  self.text='one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty'
  self.draft={'id':'main','duration':6000000,'materials':{'texts':[{'id':'m','content':json.dumps({'text':self.text,'styles':[]})}]},'tracks':[{'type':'text','segments':[{'id':'s','material_id':'m','target_timerange':{'start':0,'duration':6000000}}]}]}
  self.raw=json.dumps(self.draft).encode();(self.proj/'draft_info.json').write_bytes(self.raw)
  (self.proj.parent.parent/'draft_info.json').write_bytes(self.raw)
  self.addCleanup(E._CONTEXT.__dict__.clear);E._CONTEXT.conf={'ai_backend':'webhook'}
 def run_split(self,responses):
  with patch.object(T,'ensure_closed'),patch.object(R,'ask',side_effect=responses):return R.run(str(self.proj),{'max_words':10})
 def test_repetition_spelling_and_grammatical_exceptions(self):
  cases={'จริงจริง':'จริงๆ','น้องน้อง':'น้องๆ','จริง จริง':'จริงๆ',
         'เล็กเล็กน้อยน้อย':'เล็กๆน้อยๆ','ทำตามมากมาก':'ทำตามมากๆ',
         'ที่ที่เรา':'ที่ ที่เรา','ที่ ที่เรา':'ที่ ที่เรา',
         'จริงใจจริงใจ':'จริงใจจริงใจ','น้องน้องสาว':'น้องน้องสาว',
         'คนคนนี้':'คนคนนี้','จริงๆ':'จริงๆ','จริงจริงจริง':'จริงๆ'}
  for source,expected in cases.items():
   with self.subTest(source=source):
    self.assertEqual(R.normalize_repetitions(source),L.space_mai_yamok(expected))
    self.assertEqual(R.normalize_repetitions(expected),L.space_mai_yamok(expected))
 def test_short_caption_normalized_without_ai_or_timing_changes(self):
  d=copy.deepcopy(self.draft);d['materials']['texts'][0]['content']=json.dumps({'text':'จริงจริง น้องน้อง ที่ที่เรา','styles':[]})
  raw=json.dumps(d).encode();(self.proj/'draft_info.json').write_bytes(raw)
  (self.proj.parent.parent/'draft_info.json').write_bytes(raw)
  with patch.object(T,'ensure_closed'),patch.object(R,'ask') as ai:
   result=R.run(str(self.proj),{'max_words':20})
  ai.assert_not_called();self.assertEqual(result['normalized'],1)
  saved=json.loads((self.proj/'draft_info.json').read_bytes());seg=saved['tracks'][0]['segments'][0]
  mat=next(m for m in saved['materials']['texts'] if m['id']==seg['material_id'])
  self.assertEqual(json.loads(mat['content'])['text'],'จริง ๆ น้อง ๆ ที่ ที่เรา')
  self.assertEqual(seg['target_timerange'],d['tracks'][0]['segments'][0]['target_timerange'])
  self.assertEqual(T.read_checkpoint(str(self.proj),result['backup_name'])['draft_info.json'],raw)

 def test_loanwords_on_short_caption_force_utcc_and_keep_time(self):
  d=copy.deepcopy(self.draft);d['materials']['texts'][0]['content']=json.dumps({'text':'ทำคอนเทนต์ค่ะ','styles':[]})
  raw=json.dumps(d).encode();(self.proj/'draft_info.json').write_bytes(raw)
  (self.proj.parent.parent/'draft_info.json').write_bytes(raw)
  with patch.object(T,'ensure_closed'),patch.object(E,'provider_config',return_value=({'ai_backend':'webhook','webhook_utcc':True},'UTCC')) as route,patch.object(R,'ask',return_value=[{'index':0,'replacements':[{'source':'คอนเทนต์','english':'Content','occurrence':1}]}]) as ai:
   result=R.run(str(self.proj),{'max_words':20,'english_loanwords':True})
  route.assert_called_once_with('utcc');self.assertTrue(ai.call_args[0][1]['webhook_utcc'])
  self.assertEqual(result['loanword_changed'],1)
  saved=json.loads((self.proj/'draft_info.json').read_bytes());seg=saved['tracks'][0]['segments'][0]
  mat=next(m for m in saved['materials']['texts'] if m['id']==seg['material_id'])
  self.assertEqual(json.loads(mat['content'])['text'],'ทำ Content ค่ะ')
  self.assertEqual(seg['target_timerange'],d['tracks'][0]['segments'][0]['target_timerange'])
  self.assertEqual(T.read_checkpoint(str(self.proj),result['backup_name'])['draft_info.json'],raw)

 def test_loaded_current_caption_hash_is_accepted(self):
  from ks.ce_project import api_captions
  listing=api_captions(str(self.proj),current=True)
  words=self.text.split()
  with patch.object(T,'ensure_closed'),patch.object(R,'ask',return_value=[{'index':0,'phrases':[' '.join(words[:10]),' '.join(words[10:])]}]):
   result=R.run(str(self.proj),{'max_words':10,'state_hash':listing['state_hash']})
  self.assertTrue(result['ok'])
  self.assertEqual(result['state_hash'],api_captions(str(self.proj),current=True)['state_hash'])
 def test_current_caption_loading_bypasses_stale_original(self):
  from ks.ce_project import api_captions,project_paths,mark_applied_output
  paths=project_paths(str(self.proj));old=copy.deepcopy(self.draft)
  old['materials']['texts'][0]['content']=json.dumps({'text':'old captions','styles':[]})
  Path(paths['orig']).write_text(json.dumps(old));mark_applied_output(paths)
  self.assertEqual(api_captions(str(self.proj))['captions'][0]['text'],'old captions')
  current=api_captions(str(self.proj),current=True)
  self.assertEqual(current['captions'][0]['text'],self.text)
  self.assertNotEqual(current['state_hash'],api_captions(str(self.proj))['state_hash'])
 def test_stale_current_hash_still_refuses_without_writing(self):
  with patch.object(T,'ensure_closed'):
   with self.assertRaises(ValueError):R.run(str(self.proj),{'state_hash':'old'})
  self.assertEqual((self.proj/'draft_info.json').read_bytes(),self.raw)

 def test_eleven_words_keeps_phrase_and_preserves_text_time_and_mirrors(self):
  words=self.text.split();p=[' '.join(words[:11]),' '.join(words[11:])]
  result=self.run_split([[{'index':0,'phrases':p}]])
  d=json.loads((self.proj/'draft_info.json').read_bytes());m={v['id']:v for v in d['materials']['texts']}
  segs=d['tracks'][0]['segments'];texts=[json.loads(m[s['material_id']]['content'])['text'] for s in segs]
  self.assertEqual(''.join(texts),self.text);self.assertEqual(len(texts[0].split()),11)
  self.assertEqual(sum(s['target_timerange']['duration'] for s in segs),6000000)
  self.assertEqual(segs[1]['target_timerange']['start'],segs[0]['target_timerange']['duration'])
  self.assertEqual((self.proj/'draft_info.json').read_bytes(),(self.proj.parent.parent/'draft_info.json').read_bytes())
  self.assertEqual(T.read_checkpoint(str(self.proj),result['backup_name'])['draft_info.json'],self.raw)
 def test_missing_index_or_changed_words_never_writes(self):
  for response in ([],[{'index':0,'phrases':['invented words']}],[{'index':999,'phrases':[self.text]}]):
   with self.subTest(response=response):
    with self.assertRaises(ValueError):self.run_split([response]*3)
    self.assertEqual((self.proj/'draft_info.json').read_bytes(),self.raw)
 def test_overlong_phrase_is_retried_and_not_silently_kept(self):
  with self.assertRaises(ValueError):self.run_split([[{'index':0,'phrases':[self.text]}]]*3)
  self.assertEqual((self.proj/'draft_info.json').read_bytes(),self.raw)
 def test_current_timeline_not_stale_original(self):
  (self.proj/'draft_info_original.json').write_text('{}')
  words=self.text.split();p=[' '.join(words[:10]),' '.join(words[10:])]
  self.assertEqual(self.run_split([[{'index':0,'phrases':p}]])['changed'],1)
 def test_concurrent_change_refuses_commit(self):
  def response(*a):
   (self.proj/'draft_info.json').write_bytes(b'{"edited":true}')
   return [{'index':0,'phrases':[' '.join(self.text.split()[:10]),' '.join(self.text.split()[10:])]}]
  with patch.object(T,'ensure_closed'),patch.object(R,'ask',side_effect=response):
   with self.assertRaises(ValueError):R.run(str(self.proj),{'max_words':10})
  self.assertEqual((self.proj/'draft_info.json').read_bytes(),b'{"edited":true}')
 def test_rollback_on_write_failure(self):
  original=T.replace_files;calls=[]
  def fail_once(proj,files):
   calls.append(1)
   if len(calls)==1:raise OSError('disk write failed')
   return original(proj,files)
  with patch.object(T,'ensure_closed'),patch.object(T,'replace_files',side_effect=fail_once),patch.object(R,'ask',return_value=[{'index':0,'phrases':[' '.join(self.text.split()[:10]),' '.join(self.text.split()[10:])]}]):
   with self.assertRaises(OSError):R.run(str(self.proj),{'max_words':10})
  self.assertEqual((self.proj/'draft_info.json').read_bytes(),self.raw)

 def test_token_boundaries_keep_eleven_words_without_rewriting(self):
  result=R.token_break_phrases(self.text,[11,20],10)
  self.assertEqual(''.join(result),self.text)
  self.assertEqual(len(result[0].split()),11)
  for ends in ([10],[0,20],[12,11,20],[21]):
   with self.assertRaises(ValueError):R.token_break_phrases(self.text,ends,10)
 def test_dangling_connector_rejected(self):
  with self.assertRaises(ValueError):R.exact_phrases('I want to show you',['I want to','show you'],4)
 def test_result_visible_outside_collapsed_persona(self):
  from ks import pages
  from html.parser import HTMLParser
  class Check(HTMLParser):
   depth=0;found=False
   def handle_starttag(self,tag,attrs):
    if tag=='details':self.depth+=1
    if dict(attrs).get('id')=='resegResult':
     self.found=True
     if self.depth:raise AssertionError('Result hidden inside collapsed details')
   def handle_endtag(self,tag):
    if tag=='details':self.depth-=1
  parser=Check();parser.feed(pages.build_editor_page((Path(__file__).resolve().parents[1]/'ks'/'editor_page.html').read_text()))
  self.assertTrue(parser.found)

 def test_repair_overlong_ai_tokens_preserves_every_word(self):
  result=R.token_break_phrases(self.text,[20],10)
  self.assertGreater(len(result),1)
  self.assertEqual(''.join(result),self.text)
  self.assertTrue(all(len(R.word_ranges(x,'word'))<=13 for x in result))
 def test_repair_moves_dangling_connector(self):
  text='I go to the store every morning'
  result=R.token_break_phrases(text,[3,7],4)
  self.assertEqual(''.join(result),text)
  for p in result[:-1]:self.assertNotIn(p.strip().split()[-1],('to','the'))

 def test_thai_repeat_and_compound_not_cut_in_middle(self):
  text='อยากจะทำตามมากมากอยากจะเดินรอยตามมากมากเลยค่ะ'
  result=R.repair_boundaries(text,[8,len(R.word_ranges(text,'word'))],10)
  self.assertEqual(''.join(result),text)
  offsets=[];offset=0
  for phrase in result[:-1]:offset+=len(phrase);offsets.append(offset)
  for offset in offsets:
   self.assertFalse(any(a<offset<b for a,b in R.protected_spans(text)))
