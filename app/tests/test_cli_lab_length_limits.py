import unittest
from ks.cli_lab_story import limits
from ks.cli_lab_limits import MAX_SECONDS,audio_timeout
from ks import cli_lab_ui
class LengthTests(unittest.TestCase):
 def test_longer_ranges(self):
  self.assertEqual(limits({'min_seconds':180,'max_seconds':300}),(180,300))
  self.assertEqual(limits({'min_seconds':600,'max_seconds':600}),(600,600))
 def test_invalid_ranges_and_values(self):
  for low,high in [(300,180),(5,601),(4,100),(True,300),(5,float('nan')),(5,float('inf'))]:
   with self.subTest(low=low,high=high):
    with self.assertRaises(ValueError):limits({'min_seconds':low,'max_seconds':high})
 def test_ui_agrees_and_render_budget_scales(self):
  self.assertIn(f'max="{MAX_SECONDS}"',cli_lab_ui.UI)
  self.assertIn(f'max>{MAX_SECONDS}',cli_lab_ui.JS)
  self.assertEqual(audio_timeout(90),120);self.assertEqual(audio_timeout(600),600)
