import copy,json,math,tempfile,unittest,wave
from pathlib import Path
from ks.cli_lab_social import motion
from ks.cli_lab_presentation import emphasis,append_supers
from ks import stock_polish as P
class LongForm(unittest.TestCase):
 def test_sparse_motion_stays_continuous_and_within_source_frames(self):
  def seg(at,source,length):return dict(id=str(at),material_id='v',volume=.7,speed=1,target_timerange=dict(start=int(at*1e6),duration=int(length*1e6)),source_timerange=dict(start=int(source*1e6),duration=int(length*1e6)),clip={'scale':{'x':1,'y':1}})
  a,b=seg(0,10,150),seg(150,160,150);d={'fps':30,'tracks':[{'type':'video','segments':[a,b]}]}
  motion(d);self.assertLess(sum(len(g['keyframe_list']) for s in (a,b) for g in s['common_keyframes']),240)
  for s in (a,b):
   self.assertEqual(s['volume'],.7)
   for g in s['common_keyframes']:
    self.assertTrue(all(s['source_timerange']['start']<=k['time_offset']<s['source_timerange']['start']+s['source_timerange']['duration'] for k in g['keyframe_list']))
  self.assertAlmostEqual(a['common_keyframes'][0]['keyframe_list'][-1]['values'][0],b['common_keyframes'][0]['keyframe_list'][0]['values'][0],delta=.002)
 def test_generated_text_is_native_grounded_and_spread(self):
  materials=[];segments=[]
  for i in range(25):
   text='การตลาดแนวคิด'+str(i);materials.append(dict(id=str(i),content=json.dumps(dict(text=text,styles=[dict(range=[0,len(text)],size=10)]))))
   segments.append(dict(id='s'+str(i),material_id=str(i),target_timerange=dict(start=(i*12+5)*1000000,duration=3000000),clip={'scale':{'x':1,'y':1}}))
  draft=dict(duration=310000000,materials={'texts':materials},tracks=[dict(type='text',name='captions',segments=segments)])
  rows=emphasis(draft,maximum=22,requested=['การตลาดแนวคิด'+str(i) for i in range(25)])
  self.assertGreaterEqual(len(rows),15);self.assertGreater(rows[-1][0]-rows[0][0],240)
  before=copy.deepcopy(segments);self.assertEqual(append_supers(draft,rows),len(rows));self.assertEqual(segments,before)
 def test_short_music_is_audible_until_requested_end(self):
  import numpy as np
  from ks import core_engine as CE
  if not CE.ac_ffmpeg_bin():self.skipTest('ffmpeg unavailable')
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);rate=16000;t=np.arange(rate*2)/rate
   with wave.open(str(root/'song.wav'),'wb') as out:out.setparams((1,2,rate,0,'NONE','not compressed'));out.writeframes((.2*np.sin(2*np.pi*440*t)*32767).astype('<i2').tobytes())
   output,_=P.music_bed(root/'song.wav',root,dict(duration=8000000,tracks=[],materials={}),8)
   decoded=root/'decoded.wav';P._run(['-i',output,'-ac','1','-ar',rate,'-c:a','pcm_s16le',decoded])
   with wave.open(str(decoded),'rb') as stream:samples=np.frombuffer(stream.readframes(stream.getnframes()),dtype='<i2').astype(float)
   self.assertGreater(len(samples)/rate,7.9);self.assertGreater(float(np.sqrt(np.mean(samples[-rate:]**2))),100)
