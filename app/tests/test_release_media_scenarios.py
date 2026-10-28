"""Real decoder/mixer acceptance checks with generated, non-private AV fixtures."""
import copy,os,sys,json,subprocess,tempfile,unittest,wave
from pathlib import Path
from unittest.mock import patch
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ks import cli_lab_alignment as A,cli_lab as L,cli_lab_story as S

class ReleaseMediaScenarios(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.temp=tempfile.TemporaryDirectory(prefix='ks-release-media-');cls.root=Path(cls.temp.name)
  cls.binary=os.environ.get('KS_ACCEPTANCE_FFMPEG') or L.CE.ac_ffmpeg_bin()
  cls.files=[]
  for i,hz in enumerate((440,880)):
   path=cls.root/f'speaker-{i}.mp4'
   subprocess.run([cls.binary,'-v','error','-f','lavfi','-i',f'color=c={"blue" if i==0 else "green"}:s=96x96:r=10','-f','lavfi','-i',f'sine=frequency={hz}:sample_rate=16000','-t','2','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac','-y',str(path)],check=True,capture_output=True,timeout=30)
   cls.files.append(str(path))
 @classmethod
 def tearDownClass(cls):cls.temp.cleanup()
 def segment(self,i,start=0,duration=2000000,speed=1,volume=1):
  return dict(id=f's{i}',material_id=f'v{i}',speed=speed,volume=volume,extra_material_refs=[],source_timerange=dict(start=0,duration=int(duration*speed)),target_timerange=dict(start=start,duration=duration))
 def draft(self,segments,seconds=2):
  return dict(duration=int(seconds*1e6),materials=dict(videos=[dict(id=f'v{i}',path=p,has_audio=True) for i,p in enumerate(self.files)],audios=[],texts=[]),tracks=[dict(type='video',segments=segments)])
 def render(self,d):
  before=copy.deepcopy(d);path=self.root/'mixed.wav'
  with patch.object(L.CE,'ac_ffmpeg_bin',return_value=self.binary):A.render_speech(d,path,respect_volume=True)
  self.assertEqual(d,before,'analysis must not modify project')
  with wave.open(str(path)) as f:
   self.assertEqual(f.getframerate(),16000);samples=np.frombuffer(f.readframes(f.getnframes()),dtype='<i2').astype(float)
  self.assertAlmostEqual(len(samples)/16000,d['duration']/1e6,places=2)
  return samples
 def tone(self,samples,start,end):
  values=samples[int(start*16000):int(end*16000)];spectrum=np.abs(np.fft.rfft(values));return np.argmax(spectrum)*16000/len(values)
 def test_single_clip_keeps_audio_and_duration(self):
  samples=self.render(self.draft([self.segment(0)]));self.assertAlmostEqual(self.tone(samples,.2,1.7),440,delta=3)
 def test_two_clips_follow_timeline_without_dropping_second_speaker(self):
  samples=self.render(self.draft([self.segment(0),self.segment(1,2000000)],4))
  self.assertAlmostEqual(self.tone(samples,.2,1.7),440,delta=3);self.assertAlmostEqual(self.tone(samples,2.2,3.7),880,delta=3)
 def test_detached_voice_survives_muted_video_and_music_is_excluded(self):
  d=self.draft([self.segment(0,volume=0)]);d['materials']['audios']=[dict(id='v1',path=self.files[1]),dict(id='music',path=self.files[0])]
  voice=self.segment(1);music=dict(self.segment(0),material_id='music')
  d['tracks'] += [dict(type='audio',name='Voice',segments=[voice]),dict(type='audio',name='Music',ks_role='music',segments=[music])]
  samples=self.render(d);self.assertAlmostEqual(self.tone(samples,.2,1.7),880,delta=3)
 def test_timeline_gap_stays_silent_and_speed_preserves_clock(self):
  d=self.draft([self.segment(0,duration=1000000,speed=2),self.segment(1,2000000,duration=1000000)],3)
  samples=self.render(d);self.assertLess(np.sqrt(np.mean(samples[18000:28000]**2)),5)
  self.assertAlmostEqual(self.tone(samples,2.1,2.8),880,delta=3)
 def test_all_muted_and_missing_media_fail_explicitly(self):
  with self.assertRaises(A.NoSpeechError):self.render(self.draft([self.segment(0,volume=0)]))
  d=self.draft([self.segment(0)]);d['materials']['videos'][0]['path']=str(self.root/'missing.mp4')
  with self.assertRaisesRegex(ValueError,'ไม่พบไฟล์เสียง'):self.render(d)
 def test_real_cli_reorders_both_media_and_keeps_source_untouched(self):
  d=self.draft([self.segment(0),self.segment(1,2000000)],4);before=copy.deepcopy(d)
  with tempfile.TemporaryDirectory(prefix='ks-release-cuts-') as work:
   cuts=[dict(start=2,end=3,role='hook'),dict(start=0,end=1,role='body')]
   result=S.build(d,cuts,Path(work),L.run_cli,lambda _:None)
   samples=self.render(result);self.assertAlmostEqual(self.tone(samples,.1,.8),880,delta=3);self.assertAlmostEqual(self.tone(samples,1.1,1.8),440,delta=3)
  self.assertEqual(d,before)
