import copy,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ks import core_engine as C,ce_features as F
from text_layout import detach_caption,font_pixels

class LayoutTests(unittest.TestCase):
 def test_long_text_and_animation_peak_fit_safe_rect(self):
  safe={'left':.1,'right':.1,'top':.12,'bottom':.22}
  for w,h in [(1920,1080),(1080,1920)]:
   x,y,s=C.clamp_super_transform(100,w,h,30,4*1.28,.99,-.99,safe)
   tw=100*font_pixels(30,h)*.62*s;th=font_pixels(30,h)*1.25*s
   self.assertLessEqual(tw,w*.8+1e-7);self.assertLessEqual(th,h*.66+1e-7)
   self.assertGreaterEqual(x*w/2-tw/2,-w*.4-1e-7)
   self.assertLessEqual(-y*h/2+th/2,h*(.5-.22)+1e-7)
 def test_detached_text_no_longer_shares_auto_caption_group(self):
  m={'type':'subtitle','group_id':'Auto_shared','recognize_task_id':'task','content':json.dumps({'text':'hello','styles':[{'size':16}]}),'words':{'text':['old']}}
  s={'group_id':'shared','caption_info':{'x':1},'source_timerange':{'duration':999},'clip':{'scale':{'x':1}}}
  clip=copy.deepcopy(s['clip']);detach_caption(m,s)
  self.assertEqual(m['type'],'text');self.assertEqual(m['group_id'],'');self.assertEqual(m['font_size'],16)
  self.assertEqual(m['words']['text'],[]);self.assertIsNone(s['source_timerange']);self.assertEqual(s['clip'],clip)
 def test_ai_uses_audited_description_not_filename_and_refuses_unknown_event(self):
  with patch.object(F,'_gemini_with_fallback',return_value=('[{"i":0,"f":0},{"i":99,"f":0}]','test')) as call:
   result=F.ai_pick_sfx([{'i':0,'text':'ฝึกทีละนิด'}],['opaque.wav'],'x','model','persona',catalog={'opaque.wav':'ติ๊งสั้นเบา โทนจริงจัง'})
  self.assertEqual(result,{0:'opaque.wav'});self.assertIn('ติ๊งสั้นเบา',call.call_args[0][2]);self.assertNotIn('opaque.wav',call.call_args[0][2])
 def test_unaudited_catalog_never_calls_ai(self):
  with patch.object(F,'_gemini_with_fallback') as call:
   self.assertEqual(F.ai_pick_sfx([{'i':0,'text':'hi'}],['x.wav'],'','',''),{})
   call.assert_not_called()
 def test_apply_detaches_all_generated_karaoke_and_does_not_randomize_ai_failure(self):
  with tempfile.TemporaryDirectory() as root:
   d={'canvas_config':{'width':1920,'height':1080},'materials':{'texts':[{'id':'m','group_id':'Auto_shared','type':'subtitle','content':json.dumps({'text':'one two three','styles':[{'size':7}]})}]},'tracks':[{'id':'t','type':'text','segments':[{'id':'s','material_id':'m','group_id':'shared','target_timerange':{'start':0,'duration':3000000},'clip':{'scale':{'x':1,'y':1}}}]}]}
   Path(root,'draft_info.json').write_text(json.dumps(d))
   with patch('ks.event_timeline.ensure_closed'),patch.object(C,'list_sfx_files',return_value=['x.wav']),patch.object(C,'load_config',return_value={'gemini_api_key':'key'}),patch.object(C,'ai_pick_sfx',return_value={}),patch.object(C,'build_sfx_track') as build:
    result=C.api_apply(root,{**C.api_captions(root),'min_words':1,'karaoke_on':True,'super_on':True,'super_keyword_map':{'0':'Practice matters'},'sfx_on':True,'sfx_dir':root,'sfx_mode':'ai','sfx_catalog':{'x.wav':'soft ding'}})
   self.assertTrue(result['ok']);build.assert_not_called()
   saved=json.loads(Path(root,'draft_info.json').read_text());used={s['material_id'] for t in saved['tracks'] for s in t['segments']}
   for m in saved['materials']['texts']:
    if m['id'] in used:
     track=next(t for t in saved['tracks'] if any(s['material_id']==m['id'] for s in t['segments']))
     if track.get('name')=='Super Text':self.assertEqual(m['type'],'text');self.assertEqual(m['group_id'],'')
     else:self.assertEqual(m['type'],'subtitle');self.assertTrue(m['group_id'].startswith('Auto_'));self.assertEqual(m['font_size'],12)
