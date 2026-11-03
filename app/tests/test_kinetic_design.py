import unittest,copy
from ks import kinetic_full as F
class VocabularyTests(unittest.TestCase):
 def test_form_follows_source_meaning_instead_of_random_cycle(self):
  self.assertEqual(F.form('คุณเคยซื้อสินค้าผ่านแคมเปญไหมคะ'),'question')
  self.assertEqual(F.form('ที่ดูเหมือนธรรมดาแต่กลับไม่ธรรมดา'),'contrast')
  self.assertEqual(F.form('รอบที่หนึ่ง รอบที่สอง รอบที่สาม'),'list')
  self.assertEqual(F.form('เพื่อทำภารกิจให้สำเร็จ'),'matched')
  self.assertEqual(F.list_parts('รอบที่สอง'),['รอบที่สอง'])
  self.assertEqual(F.form('ความคุ้มค่าเงินดังนั้นสามสิบเปอร์เซ็นต์คุณ'),'stack')
 def test_revision_can_change_form_but_cannot_invent_source_words_or_time(self):
  from ks import kinetic_design as D
  p={'kind':'caption_full','blocks':[{'cue_id':'one','units':[dict(text='เพื่อทำ',row=0,start=1,end=4,weight='support',tone='base',motion='rise',timing='caption'),dict(text='ภารกิจให้สำเร็จ',row=1,start=1,end=4,weight='hero',tone='accent',motion='pop',timing='caption')]}]}
  edits=[dict(cue_id='one',form='matched',rows=['เพื่อทำ','ภารกิจให้สำเร็จ'],motion='slide',accent=0,enabled=True)]
  out=D.revise(p,edits,{'one':'เพื่อทำภารกิจให้สำเร็จ'})
  self.assertEqual(out['blocks'][0]['form'],'matched');self.assertEqual(out['blocks'][0]['units'][0]['tone'],'accent');self.assertEqual(out['blocks'][0]['units'][0]['motion'],'slide');self.assertEqual(p['blocks'][0]['units'][0]['tone'],'base')
  for bad in (dict(edits[0],rows=['ลดราคา','ทันที']),dict(edits[0],start=0),dict(edits[0],form='random'),dict(edits[0],accent=8)):
   with self.assertRaises(ValueError):D.revise(p,[bad],{'one':'เพื่อทำภารกิจให้สำเร็จ'})

class RevisionServiceTests(unittest.TestCase):
 from test_kinetic_text import KineticServiceTests as _Fixture
 setUp=_Fixture.setUp
 def test_saved_revision_survives_prepare_and_cannot_cross_owner_or_retime(self):
  from ks import kinetic_jobs as J,caption_studio as S,job_store
  from unittest.mock import patch
  import json
  meta=J.handle('alice',self.proj,{'action':'kinetic_meta'})
  initial=J.handle('alice',self.proj,dict(action='kinetic_full_plan',source_hash=meta['source_hash'],media_hash=meta['media_hash']))
  block=initial['plan']['blocks'][0];rows=[u['text'] for u in block['units']]
  edits=[dict(cue_id=block['cue_id'],form='contrast',rows=rows,motion='slide',accent=0,enabled=True)]
  for owner in ('bob',):
   with self.assertRaises(ValueError):J.handle(owner,self.proj,dict(action='kinetic_revise',plan_id=initial['plan_id'],edits=edits))
  revised=J.handle('alice',self.proj,dict(action='kinetic_revise',plan_id=initial['plan_id'],edits=edits))
  self.assertNotEqual(initial['plan_id'],revised['plan_id'])
  self.assertNotEqual(job_store.load('alice','plans',initial['plan_id'])['plan']['blocks'][0].get('form'),'contrast')
  with patch.object(S,'output_root',return_value=self.root/'outputs'):
   result=J.handle('alice',self.proj,dict(action='kinetic_prepare',plan_id=revised['plan_id']))
  report=json.loads((__import__('pathlib').Path(result['destination'])/'kinetic_text_report.json').read_text())
  self.assertTrue(all(e['form']=='contrast' and e['motion']=='slide' for e in report['entries']))
  self.assertEqual(report['entries'][0]['tone'],'accent')
  self.assertEqual(report['entries'][0]['start'],block['units'][0]['start'])
  self.assertEqual((self.proj/'draft_info.json').read_bytes(),self.raw)
 def test_cancelled_revision_keeps_old_plan_and_persists_no_new_plan(self):
  from ks import kinetic_jobs as J,job_store
  meta=J.handle('alice',self.proj,{'action':'kinetic_meta'})
  initial=J.handle('alice',self.proj,dict(action='kinetic_full_plan',source_hash=meta['source_hash'],media_hash=meta['media_hash']))
  b=initial['plan']['blocks'][0];edits=[dict(cue_id=b['cue_id'],form='punch',rows=[b['units'][0]['text']],motion='pop',accent=0,enabled=True)]
  before=list(job_store.records('alice','plans'))
  def progress(message):pass
  def cancelled(write):raise InterruptedError('cancelled')
  progress.commit_plan=cancelled
  with self.assertRaises(InterruptedError):J.handle('alice',self.proj,dict(action='kinetic_revise',plan_id=initial['plan_id'],edits=edits),progress)
  self.assertEqual(list(job_store.records('alice','plans')),before)

class NativeVocabularyTests(unittest.TestCase):
 def test_three_row_list_and_disabled_blocks_and_shared_motion_points(self):
  from test_caption_presets import draft
  from ks import kinetic_text as K,editing_skill as SK
  d=draft();u=lambda text,row:dict(text=text,row=row,start=0,end=2,weight='hero' if row==2 else 'support',tone='accent' if row==2 else 'base',motion='slide')
  p=dict(profile=SK.PROFILE['id'],profile_hash=SK.fingerprint(),blocks=[dict(cue_id='list',form='list',units=[u('หนึ่ง',0),u('สอง',1),u('สาม',2)]),dict(cue_id='skip',enabled=False,units=[u('ซ่อน',0)])])
  out,r=K.render(d,p,font='')
  self.assertEqual(len(r['entries']),3);self.assertEqual(len({e['y'] for e in r['entries']}),3)
  for track,e in zip([t for t in out['tracks'] if t.get('ks_role')=='kinetic_super'],r['entries']):
   segment=track['segments'][0]
   for prop,key,offset in [('KFTypeAlpha','alpha',0),('KFTypeScaleX','scale',0),('KFTypePositionX','dx',e['x'])]:
    points=next(k['keyframe_list'] for k in segment['common_keyframes'] if k['property_type']==prop)
    self.assertEqual([p['time_offset'] for p in points],[p['t'] for p in e['points']])
    self.assertEqual([p['values'][0] for p in points],[p[key]+offset for p in e['points']])
 def test_untouched_semantic_plan_roundtrip_matches_preview(self):
  from test_caption_presets import draft
  from ks import kinetic_text as K,kinetic_full as F,kinetic_design as D
  import json
  d=draft();d['materials']['texts'][0]['content']=json.dumps({'text':'ที่ดูเหมือนธรรมดาแต่กลับไม่ธรรมดา','styles':[]})
  initial=F.plan(d);checked=D.validate_saved(initial,d)
  _,a=K.render(d,initial,font='',zone='upper');_,b=K.render(d,checked,font='',zone='upper')
  self.assertEqual(a,b)
