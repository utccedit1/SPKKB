import copy,json,tempfile,unittest,wave
from pathlib import Path
from ks.cli_lab_social import motion,editorial,accents

def segment(at,source,length):return dict(id=str(at),material_id='v',target_timerange=dict(start=round(at*1e6),duration=round(length*1e6)),source_timerange=dict(start=round(source*1e6),duration=round(length*1e6)),clip={'scale':{'x':1,'y':1}},volume=.7)
class SocialTests(unittest.TestCase):
 def test_micro_cut_motion_continues_and_source_offsets(self):
  a=segment(0,10,2);b=segment(2,12.1,3);d={'tracks':[{'type':'video','segments':[a,b]}]}
  original=[copy.deepcopy(s['source_timerange']) for s in (a,b)]
  self.assertEqual(motion(d),2)
  self.assertEqual(a['common_keyframes'][0]['keyframe_list'][0]['time_offset'],10000000)
  self.assertEqual(b['common_keyframes'][0]['keyframe_list'][0]['time_offset'],12100000)
  self.assertGreater(b['clip']['scale']['x'],a['clip']['scale']['x']);self.assertLess(b['clip']['scale']['x'],1.1)
  self.assertEqual([s['source_timerange'] for s in (a,b)],original);self.assertEqual(b['volume'],.7)
 def test_user_animation_preserved(self):
  s=segment(0,0,4);s['common_keyframes']=[{'property_type':'KFTypeScaleX','keyframe_list':[{'values':[2]}]}];before=copy.deepcopy(s)
  self.assertEqual(motion({'tracks':[{'type':'video','segments':[s]}]}),0);self.assertEqual(s,before)
 def test_utf16_styles_keep_text_and_caption(self):
  text='ลอง AI กับงานเทียบโอน';material={'id':'m','content':json.dumps({'text':text,'styles':[{'range':[0,len(text)],'size':10}]})}
  s=segment(0,0,3);s['material_id']='m';caption={'type':'text','name':'captions','segments':[]}
  d={'materials':{'texts':[material]},'tracks':[caption,{'type':'text','name':'ช่วยด้วยจ้า · Hook','segments':[s]}]}
  editorial(d);c=json.loads(material['content']);self.assertEqual(c['text'],text);self.assertEqual(len(c['styles']),1);self.assertEqual(len(s['common_keyframes']),3);self.assertEqual(d['tracks'][0],caption)
 def test_quiet_accents_are_real_audio_and_idempotent(self):
  with tempfile.TemporaryDirectory() as folder:
   d={'duration':2000000,'tracks':[{'type':'text','name':'ช่วยด้วยจ้า · Super Text','segments':[segment(0,0,1)]},{'type':'audio','name':'ช่วยด้วยจ้า · เสียงเน้น','segments':[]}]};calls=[]
   accents(folder,d,lambda *a:calls.append(a));self.assertEqual(len(calls),1)
   with wave.open(str(Path(folder)/'assets/social/soft_accents.wav')) as w:self.assertEqual(w.getnframes(),32000);self.assertNotEqual(w.readframes(2000),b'\0'*4000)
   self.assertEqual(len(json.loads((Path(folder)/'draft_info.json').read_text())['tracks']),1)
