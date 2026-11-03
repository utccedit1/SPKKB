import unittest
from ks.caption_phrase_anchors import phrases
class PhraseAnchorTests(unittest.TestCase):
 def test_weak_word_is_preserved_between_measured_anchors_not_interpolated(self):
  raw=[dict(word='one ',start=0,end=.7,probability=.9),dict(word='weak ',start=.7,end=1.1,probability=.1),dict(word='two ',start=1.1,end=2.4,probability=.9),dict(word='tail',start=2.4,end=4,probability=.9)]
  result=phrases(raw,'one weak two tail',4,limit=10)
  self.assertEqual([p['text'] for p in result],['one','weak two','tail'])
  self.assertEqual([p['end'] for p in result],[.7,2.4,4])
  self.assertTrue(all(p['mode']=='measured_phrase_anchors' for p in result))
 def test_no_safe_short_boundary_fails_instead_of_inventing_time(self):
  raw=[dict(word='abcdefghijklmnopqrstuvwxyz',start=0,end=3,probability=.1)]
  with self.assertRaises(ValueError):phrases(raw,'abcdefghijklmnopqrstuvwxyz',3,limit=8)
 def test_mismatch_and_out_of_order_are_rejected(self):
  raw=[dict(word='one',start=1,end=.2,probability=.9)]
  with self.assertRaises(ValueError):phrases(raw,'one',2)
  with self.assertRaises(ValueError):phrases([dict(word='other',start=0,end=1,probability=.9)],'one',2)
 def test_short_tail_uses_an_earlier_valid_boundary(self):
  raw=[dict(word='a ',start=0,end=.5,probability=.9),dict(word='b ',start=.5,end=1,probability=.9),dict(word='c',start=1,end=1.2,probability=.9)]
  rows=phrases(raw,'a b c',1.2,limit=4)
  self.assertEqual([(r['text'],r['start'],r['end']) for r in rows],[('a',0,.5),('b c',.5,1.2)])
