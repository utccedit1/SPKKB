import copy,json,unittest
from ks.cli_lab_social import motion
from ks.cli_lab_brand_style import apply_brand_text
from ks.cli_lab_presentation import emphasis
class BrandEditorial(unittest.TestCase):
 def test_zoom_continues_across_source_and_speech_parent_changes(self):
  a=dict(id='a',material_id='one',target_timerange=dict(start=0,duration=5000000),source_timerange=dict(start=10000000,duration=5000000),clip={'scale':{'x':.8,'y':.8}},_speech_motion={'parent':'a'})
  b=copy.deepcopy(a);b.update(id='b',material_id='two',target_timerange=dict(start=5000000,duration=5000000),source_timerange=dict(start=90000000,duration=5000000),_speech_motion={'parent':'b'})
  motion({'tracks':[{'type':'video','segments':[a,b]}],'fps':30})
  end=a['common_keyframes'][0]['keyframe_list'][-1]['values'][0];start=b['common_keyframes'][0]['keyframe_list'][0]['values'][0]
  self.assertAlmostEqual(end,start,delta=.0003);self.assertNotEqual(start,b['common_keyframes'][0]['keyframe_list'][-1]['values'][0])
 def test_brand_settings_and_existing_none_animation_are_respected(self):
  text='แบรนด์ต้องอยู่ในประสบการณ์จริง';d=dict(canvas_config={'width':1080,'height':1920},materials={'texts':[dict(id='t',content=json.dumps({'text':text,'styles':[]}))]},tracks=[dict(type='text',name='ช่วยด้วยจ้า · Super Text',segments=[dict(material_id='t',target_timerange={'start':0,'duration':3000000})])])
  apply_brand_text(d,config={'super_color':'#00b1eb','super_size':17,'super_anim_type':'none','super_bg':False})
  m=d['materials']['texts'][0];style=json.loads(m['content'])['styles'][0]
  self.assertEqual(m['font_size'],17);self.assertFalse(style.get('bold',False));self.assertEqual(d['tracks'][0]['segments'][0]['common_keyframes'],[])
 def test_complete_phrase_can_span_captions(self):
  texts=['แบรนด์ไม่ได้มีแค่โลโก้','แต่เป็นประสบการณ์ที่คนจดจำ'];m=[];s=[]
  for i,text in enumerate(texts):m.append(dict(id=str(i),content=json.dumps({'text':text})));s.append(dict(id=str(i),material_id=str(i),target_timerange=dict(start=(5+i*2)*1000000,duration=2000000)))
  d=dict(duration=30000000,materials={'texts':m},tracks=[dict(type='text',segments=s)])
  rows=emphasis(d,maximum=3,requested=[''.join(texts)]);self.assertEqual(rows[0][2],''.join(texts));self.assertEqual(rows[0][0],5)
 def test_cached_footage_excludes_already_used_source(self):
  import tempfile
  from pathlib import Path
  from unittest.mock import patch
  from ks.stock_accounts import cached_download
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);media=root/'media';media.mkdir();file=media/'shot.mp4';file.write_bytes(b'video')
   receipt=dict(provider='artlist',query='office desk',kind='broll',url='https://artlist.io/stock-footage/clip/desk/123',path=str(file),sha256='used')
   file.with_suffix('.mp4.stock.json').write_text(json.dumps(receipt))
   with patch('ks.stock_accounts.peer',return_value={'root':root}),patch('ks.stock_browser.safe_item',return_value=True),patch('ks.stock_browser.verify_file',return_value={'sha256':'used'}):
    self.assertIsNone(cached_download('owner','artlist',{'kind':'broll','query':'office desk','exclude_hashes':['used']}))
    self.assertIsNotNone(cached_download('owner','artlist',{'kind':'broll','query':'office desk'}))
