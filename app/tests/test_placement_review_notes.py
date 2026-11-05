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
 def test_whole_clip_findings_are_visible_before_import(self):
  with tempfile.TemporaryDirectory() as root:
   p=Path(root)
   (p/'editorial_quality_report.json').write_text(json.dumps(dict(issues=[dict(start=1,end=2,reason='ซับอ่านเร็ว',severity='warning',evidence_kind='heuristic')],missing_evidence=['audio'],unsupported_checks=['audio_listening'])))
   notes=review_notes(p)
   self.assertIn('1.00',notes);self.assertIn('2.00',notes);self.assertIn('ซับอ่านเร็ว',notes)

 def test_camera_review_shows_when_and_why_original_was_kept(self):
  with tempfile.TemporaryDirectory() as root:
   p=Path(root)
   (p/'editorial_camera_report.json').write_text(json.dumps(dict(changed=0,records=[dict(interval=[10,12.5],reason='uncertain_camera_evidence',cameras=[dict(reason='source_coverage_unverified')]) ,dict(interval=[float('nan'),12],reason='original_equal_or_better')])))
   notes=review_notes(p)
   self.assertIn('10.00–12.50',notes);self.assertIn('ภาพต้นทางไม่ครบ',notes)
   self.assertNotIn('nan',notes)
