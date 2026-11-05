import copy,unittest
from ks import cli_highlight_story as H

class NarrowDurationTests(unittest.TestCase):
 def test_narrow_target_uses_existing_complete_caption_fitter(self):
  captions=[dict(id=i,start=i*30,end=(i+1)*30,text=t) for i,t in enumerate(['The campaign starts with a clear question.','A buyer comparison explains the question.','The comparison resolves that question.'])]
  candidate=dict(axis='buyer comparison',hook='Compare buyers',cta='Use the comparison',reason='Complete answer',cuts=[dict(first_id=0,last_id=0,role='hook'),dict(first_id=2,last_id=2,role='conclusion')])
  before=copy.deepcopy(candidate)
  result=H.prepare(candidate,captions,None,85,95)
  self.assertEqual(result['story']['duration'],90)
  self.assertEqual([(c['first_id'],c['last_id']) for c in result['story']['cuts']],[(0,1),(2,2)])
  self.assertEqual(candidate,before)
  self.assertNotIn('narrative_review',result['story'])
