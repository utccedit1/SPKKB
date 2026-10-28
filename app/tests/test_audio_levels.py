import json,tempfile,unittest,wave
from pathlib import Path
import numpy as np
from ks import audio_levels as A
from ks.cli_lab_alignment import render_speech

class AudioLevels(unittest.TestCase):
 def test_measured_speech_gain_preserves_mutes_music_and_reaches_target(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);source=root/'voice.wav';rate=48000;t=np.arange(rate*2)/rate
   with wave.open(str(source),'wb') as f:
    f.setparams((1,2,rate,0,'NONE','not compressed'));f.writeframes((.1*np.sin(2*np.pi*440*t)*32767).astype('<i2').tobytes())
   seg=dict(id='voice',material_id='m',volume=1,speed=1,source_timerange=dict(start=0,duration=2000000),target_timerange=dict(start=0,duration=2000000))
   draft=dict(duration=2000000,materials={'audios':[dict(id='m',path=str(source))]},tracks=[dict(type='audio',name='speech',segments=[seg]),dict(type='audio',name='muted',segments=[dict(seg,id='mute',volume=0)]),dict(type='audio',name='ช่วยด้วยจ้า · Music',segments=[dict(seg,id='music',volume=.1)])])
   (root/'draft_info.json').write_text(json.dumps(draft))
   result=A.normalize_speech(root);new=json.loads((root/'draft_info.json').read_bytes())
   self.assertAlmostEqual(result['after_peak_dbfs'],-4,delta=.15)
   self.assertEqual(new['tracks'][1]['segments'][0]['volume'],0)
   self.assertEqual(new['tracks'][2]['segments'][0]['volume'],.1)
   rendered=root/'verify.wav';render_speech(new,rendered,respect_volume=True,sample_rate=48000,channels=2,codec='pcm_f32le')
   self.assertAlmostEqual(A.peak_dbfs(rendered),-4,delta=.15)
 def test_no_speech_is_reported_without_unmuting(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);(root/'draft_info.json').write_text(json.dumps(dict(duration=1000000,materials={},tracks=[])))
   self.assertEqual(A.normalize_speech(root)['state'],'no_audible_speech')
