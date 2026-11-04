import copy,json,unittest
from test_caption_presets import draft
from ks import caption_finish as F
class CaptionFinishTests(unittest.TestCase):
 def test_aliases_are_display_only_and_not_translation(self):
  self.assertEqual(F.display('แคมเปญสร้างเอ็นเกจเมนต์ให้แบรนด์'),'Campaign สร้าง Engagement ให้ Brand')
  self.assertEqual(F.display('การส่งเสริมการขาย'),'การส่งเสริมการขาย')
 def test_split_preserves_original_text_and_shared_unselected_material(self):
  d=draft();before=copy.deepcopy(d);rows={'one':[dict(text='😀 เข้าใจ',start=0,end=.5),dict(text='ผู้บริโภค',start=.5,end=1)]}
  ids=F.apply(d,rows,False);self.assertEqual(len(ids),3);self.assertEqual(d['materials']['texts'][0],before['materials']['texts'][0]);self.assertEqual(d['tracks'][0]['segments'][-1]['target_timerange'],before['tracks'][0]['segments'][-1]['target_timerange'])
  texts={m['id']:m for m in d['materials']['texts']};self.assertEqual([json.loads(texts[s['material_id']]['content'])['text'] for s in d['tracks'][0]['segments']],['😀 เข้าใจ','ผู้บริโภค','😀 เข้าใจผู้บริโภค'])
 def test_missing_words_gaps_and_invented_times_are_atomic_failures(self):
  for rows in [[dict(text='😀 เข้าใจ',start=0,end=1)],[dict(text='😀 เข้าใจ',start=0,end=.4),dict(text='ผู้บริโภค',start=.5,end=1)],[dict(text='😀 เข้าใจผู้บริโภค',start=0,end=2)]]:
   d=draft();before=copy.deepcopy(d)
   with self.assertRaises(ValueError):F.apply(d,{'one':rows},False)
   self.assertEqual(d,before)
 def test_unknown_caption_and_alias_utf16_range(self):
  d=draft()
  with self.assertRaises(ValueError):F.apply(d,{'wrong':[]},True)
  d['materials']['texts'][0]['content']=json.dumps(dict(text='😀 แบรนด์',styles=[dict(range=[0,9])]))
  F.apply(d,{},True);m=d['materials']['texts'][-1];c=json.loads(m['content']);self.assertEqual(c['text'],'😀 Brand');self.assertEqual(c['styles'][0]['range'],[0,8]);self.assertEqual(m['ks_source_text'],'😀 แบรนด์')

class CaptionFinishRendererTests(unittest.TestCase):
 def test_opt_in_renders_same_english_caption_and_super_with_source_trace(self):
  from ks import kinetic_full as B,kinetic_text as K
  d=draft();d['materials']['texts'][0]['content']=json.dumps(dict(text='แบรนด์',styles=[]));p=B.plan(d)
  out,r=K.render(d,p,font='',caption_one_line=True,english_loanwords=True,caption_phrases={})
  self.assertEqual(r['captions'][0]['text'],'Brand');self.assertTrue(all(e['text']=='Brand' and e['source_text']=='แบรนด์' for e in r['entries']));self.assertEqual(d['materials']['texts'][0]['content'],json.dumps(dict(text='แบรนด์',styles=[])))
 def test_long_caption_requires_measured_splits_not_automatic_char_times(self):
  from ks import kinetic_full as B,kinetic_text as K
  d=draft();d['materials']['texts'][0]['content']=json.dumps(dict(text='คำพูดต้นฉบับ'*30,styles=[]));p=B.plan(d)
  with self.assertRaisesRegex(ValueError,'หนึ่งบรรทัด'):K.render(d,p,font='',caption_one_line=True)

class CaptionFinishServiceTests(unittest.TestCase):
 from test_kinetic_text import KineticServiceTests as _Fixture
 setUp=_Fixture.setUp
 def test_options_persist_to_prepare_and_do_not_change_project(self):
  from ks import kinetic_jobs as J,caption_studio as S
  from unittest.mock import patch
  from pathlib import Path
  meta=J.handle('alice',self.proj,dict(action='kinetic_meta'))
  result=J.handle('alice',self.proj,dict(action='kinetic_full_plan',source_hash=meta['source_hash'],media_hash=meta['media_hash'],caption_one_line=True,english_loanwords=True))
  self.assertTrue(result['settings']['caption_one_line']);self.assertGreater(len(result['preview']['captions']),0)
  with patch.object(S,'output_root',return_value=self.root/'outputs'):
   ready=J.handle('alice',self.proj,dict(action='kinetic_prepare',plan_id=result['plan_id']))
  report=json.loads((Path(ready['destination'])/'kinetic_text_report.json').read_text());self.assertEqual(report['captions'],result['preview']['captions']);self.assertEqual((self.proj/'draft_info.json').read_bytes(),self.raw)
 def test_scope_and_bad_booleans_reject_before_ai(self):
  from ks import kinetic_jobs as J,cli_lab_webhook as W
  from unittest.mock import patch
  meta=J.handle('alice',self.proj,dict(action='kinetic_meta'));base=dict(source_hash=meta['source_hash'],media_hash=meta['media_hash'])
  with self.assertRaises(ValueError):J.handle('alice',self.proj,dict(base,action='kinetic_full_plan',caption_one_line='yes'))
  with patch.object(W,'request',side_effect=AssertionError('not called')),self.assertRaisesRegex(ValueError,'ทั้งคลิป'):
   J.handle('alice',self.proj,dict(base,action='kinetic_plan',ids=['one'],english_loanwords=True))

 def test_paragraph_source_uses_measured_short_phrase_for_initial_super_preview(self):
  from ks import kinetic_jobs as J
  words=('alpha beta gamma '*12).split();text=' '.join(words);m=self.d['materials']['texts'][0];m['content']=json.dumps(dict(text=text,styles=[]));m['words']=dict(text=[w+' ' if i<len(words)-1 else w for i,w in enumerate(words)],start_time=[i*100 for i in range(len(words))],end_time=[(i+1)*100 for i in range(len(words))]);self.d['canvas_config']=dict(width=1920,height=1080);self.d['tracks'][0]['segments'][0]['target_timerange']['duration']=4000000;(self.proj/'draft_info.json').write_text(json.dumps(self.d))
  meta=J.handle('alice',self.proj,dict(action='kinetic_meta'));result=J.handle('alice',self.proj,dict(action='kinetic_full_plan',source_hash=meta['source_hash'],media_hash=meta['media_hash'],caption_one_line=True))
  self.assertGreater(len(result['preview']['captions']),2)
  self.assertTrue(all(e['source_text'] in text and len(e['source_text'])<60 for e in result['preview']['entries']))

class RecipeAfterCompactionTests(unittest.TestCase):
 from test_kinetic_text import KineticServiceTests as _Fixture
 setUp=_Fixture.setUp
 def test_impact_uses_final_matched_phrase_form_and_prepare_keeps_scene(self):
  from ks import kinetic_jobs as J,caption_studio as S
  from test_kinetic_scene import SceneTests
  from unittest.mock import patch
  from pathlib import Path
  words=('alpha beta gamma '*12).split();text=' '.join(words)
  self.d['canvas_config']=dict(width=1920,height=1080)
  m=self.d['materials']['texts'][0];m['content']=json.dumps(dict(text=text,styles=[]));m['words']=dict(text=[w+' ' if i<len(words)-1 else w for i,w in enumerate(words)],start_time=[i*100 for i in range(len(words))],end_time=[(i+1)*100 for i in range(len(words))])
  self.d['tracks'][0]['segments'][0]['target_timerange']['duration']=4000000
  video=SceneTests().fixture();self.d['tracks']+=video['tracks'];self.d['duration']=6000000
  (self.proj/'draft_info.json').write_text(json.dumps(self.d));raw=(self.proj/'draft_info.json').read_bytes()
  meta=J.handle('alice',self.proj,dict(action='kinetic_meta'))
  result=J.handle('alice',self.proj,dict(action='kinetic_full_plan',source_hash=meta['source_hash'],media_hash=meta['media_hash'],caption_one_line=True,style='impact'))
  self.assertEqual(result['plan']['blocks'][0]['form'],'matched')
  self.assertEqual(result['plan']['blocks'][0]['camera_move'],'snap_to_cut')
  self.assertEqual(result['preview']['scenes'][0]['end'],6)
  with patch.object(S,'output_root',return_value=self.root/'outputs'):
   ready=J.handle('alice',self.proj,dict(action='kinetic_prepare',plan_id=result['plan_id']))
  report=json.loads((Path(ready['destination'])/'kinetic_text_report.json').read_text())
  self.assertEqual(report['scenes'],result['preview']['scenes'])
  self.assertEqual((self.proj/'draft_info.json').read_bytes(),raw)

class NativeCaptionContractTests(unittest.TestCase):
 def test_one_line_clears_inherited_native_wrapping_constraints(self):
  d=draft();d['materials']['texts'][0].update(force_apply_line_max_width=True,line_max_width=.1,fixed_width=100,line_feed=1)
  ids=F.apply(d,{},one_line=True);used={s['material_id'] for t in d['tracks'] for s in t['segments'] if s['id'] in ids}
  for m in d['materials']['texts']:
   if m['id'] in used:self.assertFalse(m['force_apply_line_max_width']);self.assertEqual(m['fixed_width'],-1);self.assertEqual(m['line_feed'],0)
 def test_aliases_do_not_leave_partial_common_terms(self):
  self.assertEqual(F.display('เกมมิฟิเคชั่น แบรนด์ดิ้ง'),'Gamification Branding')
  self.assertEqual(F.display('เกมเมอร์'),'เกมเมอร์')

 def test_unchanged_short_caption_preserves_trusted_native_word_metadata(self):
  d=draft();words=dict(text=['😀 ','เข้าใจ','ผู้บริโภค'],start_time=[0,100,500],end_time=[100,500,1000]);d['materials']['texts'][0]['words']=words
  F.apply(d,{},one_line=True)
  self.assertEqual(d['materials']['texts'][-1]['words'],words)

class PhraseSuperDesignTests(unittest.TestCase):
 def test_compact_design_keeps_two_measured_rows_instead_of_single_word(self):
  from ks import kinetic_jobs as J,kinetic_full as B
  d=draft();d['canvas_config']=dict(width=1920,height=1080);text='แคมเปญแปะสติ๊กเกอร์รับส่วนลดไหมคะ';d['materials']['texts'][0]['content']=json.dumps(dict(text=text,styles=[]));p=B.plan(d)
  parts=[dict(text='แคมเปญแปะสติ๊กเกอร์',start=0,end=.5),dict(text='รับส่วนลดไหมคะ',start=.5,end=1)]
  result=J._compact_caption_plan(p,d,dict(caption_phrases={'one':parts}))
  self.assertEqual([u['text'] for u in result['blocks'][0]['units']],['แคมเปญแปะสติ๊กเกอร์','รับส่วนลดไหมคะ'])
 def test_rendered_rows_reveal_at_measured_phrase_starts_and_share_group_end(self):
  from ks import kinetic_jobs as J,kinetic_full as B,kinetic_text as K
  d=draft();d['canvas_config']=dict(width=1920,height=1080);text='แคมเปญแปะสติ๊กเกอร์รับส่วนลดไหมคะ';d['materials']['texts'][0]['content']=json.dumps(dict(text=text,styles=[]));parts=[dict(text='แคมเปญแปะสติ๊กเกอร์',start=0,end=.5),dict(text='รับส่วนลดไหมคะ',start=.5,end=1)];p=J._compact_caption_plan(B.plan(d),d,dict(caption_phrases={'one':parts}))
  out,r=K.render(d,p,font='',caption_one_line=True,caption_phrases={'one':parts},english_loanwords=True)
  entries=[e for e in r['entries'] if e['cue_id']=='one'];self.assertEqual([(e['start'],e['end']) for e in entries],[(0,1),(.5,1)])

class CaptionFontChoiceTests(unittest.TestCase):
 def test_default_prefers_editorial_blk_and_explicit_selection_still_wins(self):
  from ks import kinetic_jobs as J,caption_studio as S,core_engine as CE,cli_lab_typography as T
  from unittest.mock import patch
  with patch.object(S,'available_fonts',return_value=[dict(path='/fonts/Blk.ttf'),dict(path='/fonts/Rounded.ttf')]),patch.object(CE,'load_config',return_value=dict(font='/fonts/Rounded.ttf')),patch.object(T,'editorial_font',return_value='/fonts/Blk.ttf'):
   self.assertEqual(J._settings({})['font'],'/fonts/Blk.ttf')
   self.assertEqual(J._settings(dict(font='/fonts/Rounded.ttf'))['font'],'/fonts/Rounded.ttf')

class NumericDisplayReuseTests(unittest.TestCase):
 def test_existing_supported_percentages_use_numbers_without_inventing_units(self):
  self.assertEqual(F.display('ส่วนลดสามสิบเปอร์เซ็นต์'),'ส่วนลด 30%')
  self.assertEqual(F.display('สิบสองจุดห้าเปอร์เซ็นต์'),'สิบสองจุดห้าเปอร์เซ็นต์')
