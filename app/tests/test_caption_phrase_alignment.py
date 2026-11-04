import unittest
from ks import cli_lab_alignment as A
class PhraseAlignmentTests(unittest.TestCase):
 def test_caption_window_uses_weak_internal_word_without_lowering_strict_word_gate(self):
  self.assertTrue(hasattr(A,'align_caption_window'))
  class Features:
   shape=(80,1000)
  class Model:
   def feature_extractor(self,s):return Features()
   def encode(self,f):return f
   def find_alignment(self,*args):return [[dict(word='one ',start=0,end=.7,probability=.9),dict(word='weak ',start=.7,end=1.1,probability=.1),dict(word='two ',start=1.1,end=2.4,probability=.9),dict(word='tail',start=2.4,end=4,probability=.9)]]
  class Tokens:
   def encode(self,t):return [1,2,3,4]
  result=A.align_caption_window(Model(),Tokens(),[], 'one weak two tail',4,lambda f:f)
  self.assertEqual(''.join(p['text'] for p in result).replace(' ',''),'oneweaktwotail');self.assertEqual(result[-1]['end'],4)
  with self.assertRaises(ValueError):A.align_windows(Model(),Tokens(),[],'one weak two tail',4,lambda f:f)
 def test_caption_window_refuses_long_or_token_truncated_text(self):
  self.assertTrue(hasattr(A,'align_caption_window'))
  class Tokens:
   def encode(self,t):return list(range(401))
  with self.assertRaises(ValueError):A.align_caption_window(None,Tokens(),[],'one',30,None)
  with self.assertRaises(ValueError):A.align_caption_window(None,Tokens(),[],'one',10,None)
