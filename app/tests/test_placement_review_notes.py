import json,tempfile,unittest
from pathlib import Path
from ks.cli_lab_commit import review_notes

class PlacementReviewNotesTests(unittest.TestCase):
 def test_uncertain_placement_remains_visible_before_import(self):
  with tempfile.TemporaryDirectory() as root:
   p=Path(root)
   (p/'kinetic_text_report.json').write_text(json.dumps(dict(units=4,assistance=dict(uncertain=1,records=[dict(safe=False,interval=[13.18,29.26],reasons=['faces overlap text'])]))))
   notes=review_notes(p)
   self.assertTrue('13.18' in notes and '29.26' in notes and 'ใบหน้า' in notes,notes)
 def test_safe_placement_does_not_claim_full_clip_certification(self):
  with tempfile.TemporaryDirectory() as root:
   p=Path(root)
   (p/'kinetic_text_report.json').write_text(json.dumps(dict(units=2,assistance=dict(uncertain=0,records=[dict(safe=True,interval=[1,2],reasons=[])]))))
   notes=review_notes(p)
   self.assertFalse('ต้องตรวจช่วง' in notes)
