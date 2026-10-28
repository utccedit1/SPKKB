import json
from pathlib import Path
import tempfile
import unittest
import wave
from ks import stock_polish as P, stock_media as M

class PolishTests(unittest.TestCase):
    def test_abstract_claim_can_omit_stock_and_required_words_are_validated(self):
        self.assertEqual(M.requests({'stock_requests':[]},{'duration':20},[],True),[])
        story={'duration':20,'cuts':[{'first_id':0,'last_id':0,'start':0,'end':10}]}
        captions=[{'start':0,'end':10,'text':'เงื่อนไขการเทียบโอน'}]
        row={'kind':'broll','query':'academic transcript documents','first_id':0,'required_terms':['transcript','documents']}
        result=M.requests({'stock_requests':[row]},story,captions,True)
        self.assertEqual(result[0]['caption_text'],captions[0]['text'])
        row['required_terms']=['unrelated']
        with self.assertRaises(ValueError):M.requests({'stock_requests':[row]},story,captions,True)

    def test_music_peak_is_minus_18_and_not_ducked_below_target(self):
        import numpy as np
        from ks import audio_levels as A
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);rate=16000;t=np.arange(rate*4)/rate
            source=root/'music.wav'
            with wave.open(str(source),'wb') as stream:
                stream.setparams((1,2,rate,0,'NONE','not compressed'));stream.writeframes((.2*np.sin(2*np.pi*880*t)*32767).astype('<i2').tobytes())
            output,report=P.music_bed(source,root,{'duration':4000000},4)
            self.assertEqual(report['mode'],'fixed_peak')
            self.assertAlmostEqual(A.peak_dbfs(output),-18,delta=.15)

    def test_wide_footage_gets_full_image_and_blurred_canvas(self):
        from ks import core_engine as CE
        if not CE.ac_ffmpeg_bin():self.skipTest('ffmpeg unavailable')
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'source.mp4'
            P._run(['-f','lavfi','-i','testsrc2=size=320x180:rate=12','-t',1,'-c:v','libx264',source])
            output,mode=P.frame_video(source,root,{'width':180,'height':320},1)
            self.assertEqual(mode,'preserve_subjects_blurred_background');self.assertEqual(P.dimensions(output),(180,320))
