"""Explicit caption-only plans preserve closed source and identity validation."""
import copy,unittest
from ks import kinetic_design as D,kinetic_full as F
from test_caption_presets import draft

class CaptionOnlyDesignTests(unittest.TestCase):
 def setUp(self):
  self.d=draft();self.d['duration']=6000000
  self.p=F.plan(self.d)
  from ks.caption_presets import caption_rows
  self.sources={s['id']:t for _,s,m,t in caption_rows(self.d)}
 def edits(self,enabled=False):
  return [dict(cue_id=b['cue_id'],form=b.get('form','stack'),rows=[u['text'] for u in b['units']],motion=b['units'][-1]['motion'],accent=len(b['units'])-1,enabled=enabled) for b in self.p['blocks']]
 def test_caption_only_requires_explicit_opt_in(self):
  with self.assertRaises(ValueError):D.revise(self.p,self.edits(),self.sources)
  out=D.revise(self.p,self.edits(),self.sources,allow_empty=True)
  self.assertTrue(out['caption_only']);self.assertFalse(any(b['enabled'] for b in out['blocks']))
  self.assertNotIn('caption_only',self.p)
 def test_saved_caption_only_revalidates_source_identity_and_rebuilds_time(self):
  p=copy.deepcopy(self.p)
  for b in p['blocks']:
   b['enabled']=False
   for u in b['units']:u.update(start=100,end=200)
  with self.assertRaises(ValueError):D.validate_saved(p,self.d)
  p['caption_only']=True
  checked=D.validate_saved(p,self.d)
  self.assertTrue(checked['caption_only']);self.assertEqual(checked['blocks'][0]['units'][0]['start'],self.p['blocks'][0]['units'][0]['start'])
  p['blocks'][0]['cue_id']='unknown'
  with self.assertRaises(ValueError):D.validate_saved(p,self.d)
 def test_opt_in_does_not_allow_unspoken_text(self):
  edits=self.edits();edits[0]['rows']=['invented statement']
  with self.assertRaises(ValueError):D.revise(self.p,edits,self.sources,allow_empty=True)
 def test_enabled_super_clears_stale_caption_only_flag(self):
  self.p['caption_only']=True
  out=D.revise(self.p,self.edits(True),self.sources,allow_empty=True)
  self.assertNotIn('caption_only',out)
  self.assertNotIn('caption_only',D.validate_saved(self.p,self.d))
