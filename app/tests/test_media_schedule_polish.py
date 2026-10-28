import unittest
from ks.media_schedule import bridge_window,merge_editorial_text

def seg(start,duration):return {'target_timerange':{'start':round(start*1e6),'duration':round(duration*1e6)}}
class PolishTests(unittest.TestCase):
 def test_covers_both_nearby_edits(self):
  d={'duration':81833333,'tracks':[{'type':'video','segments':[seg(0,18.2),seg(18.2,3.7),seg(21.9,7.6),seg(29.5,25)]}]}
  start,length=bridge_window(d,18.2,8.84)
  self.assertLess(start,18.2);self.assertGreater(start+length,22.2)
  start,length=bridge_window(d,30,8)
  self.assertLess(start,29.5);self.assertGreater(start+length,30)
 def test_short_source_never_stretched(self):
  d={'duration':40000000,'tracks':[{'type':'video','segments':[seg(0,20),seg(20,20)]}]}
  start,length=bridge_window(d,18,1.5)
  self.assertLessEqual(length,1.5)
 def test_text_lane_keeps_caption_and_timings(self):
  captions={'type':'text','name':'captions','segments':[seg(0,5)]}
  d={'tracks':[captions,{'type':'text','name':'ช่วยด้วยจ้า · CTA','segments':[seg(20,4)]},{'type':'text','name':'ช่วยด้วยจ้า · Hook','segments':[seg(0,3)]}]}
  merge_editorial_text(d)
  self.assertEqual(len(d['tracks']),2);self.assertIs(d['tracks'][0],captions)
  self.assertEqual([s['target_timerange']['start'] for s in d['tracks'][1]['segments']],[0,20000000])
 def test_overlap_does_not_silently_discard_text(self):
  d={'tracks':[{'type':'text','name':'ช่วยด้วยจ้า · Hook','segments':[seg(0,4)]},{'type':'text','name':'ช่วยด้วยจ้า · Super','segments':[seg(3,2)]}]}
  with self.assertRaises(ValueError):merge_editorial_text(d)
