import json,hashlib,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ks import caption_style as S,event_timeline as T,event_clip as E

class StyleTests(unittest.TestCase):
 def test_running_capcut_requires_explicit_home_confirmation(self):
  from ks import capcut_session
  with patch.object(capcut_session,'status',return_value={'ok':True,'state':'unknown','trusted':True,'processes':[]}):
   with self.assertRaises(ValueError):T.ensure_closed()
   T.ensure_closed(home_confirmed=True)
   with self.assertRaises(ValueError):T.ensure_closed(home_confirmed='true')
 def test_bulk_style_keeps_caption_ranges_colors_timing_and_backup(self):
  with tempfile.TemporaryDirectory() as root:
   p=Path(root)/'Timelines'/'main';p.mkdir(parents=True)
   styles=[{'size':12,'range':[0,8],'fill':{'content':{'solid':{'color':[1,1,1]}}}},{'size':16,'range':[8,2],'fill':{'content':{'solid':{'color':[1,1,0]}}} }]
   m={'id':'m','type':'subtitle','group_id':'Auto_test','content':json.dumps({'text':'abcdefghij','styles':styles})}
   seg={'id':'s','material_id':'m','target_timerange':{'start':100,'duration':200},'clip':{'transform':{'y':-.8}}}
   d={'id':'main','materials':{'texts':[m]},'tracks':[{'type':'text','segments':[seg]}]};raw=json.dumps(d).encode()
   (p/'draft_info.json').write_bytes(raw);(p.parent.parent/'draft_info.json').write_bytes(raw)
   with patch.object(T,'ensure_closed'):
    result=S.run(str(p),{'state_hash':hashlib.sha1(raw).hexdigest(),'normal_size':18,'highlight_size':22})
   saved=json.loads((p/'draft_info.json').read_bytes());sm=saved['materials']['texts'][0];ss=saved['tracks'][0]['segments'][0]
   self.assertEqual(sm['type'],'subtitle');self.assertEqual(sm['group_id'],'Auto_test')
   content=json.loads(sm['content']);self.assertEqual(content['text'],'abcdefghij');self.assertEqual([x['size'] for x in content['styles']],[18,22])
   for old,new in zip(styles,content['styles']):self.assertEqual(old['range'],new['range']);self.assertEqual(old['fill'],new['fill'])
   self.assertEqual(ss['target_timerange'],seg['target_timerange']);self.assertEqual(ss['clip'],seg['clip'])
   self.assertEqual(T.read_checkpoint(str(p),result['backup_name'])['draft_info.json'],raw)
   self.assertEqual((p/'draft_info.json').read_bytes(),(p.parent.parent/'draft_info.json').read_bytes())
