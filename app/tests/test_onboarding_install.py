import sys,tempfile,json,plistlib
from pathlib import Path
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ks import onboarding as O,app_instance as I,updater as U
class SetupTests(unittest.TestCase):
 def test_owner_progress_is_separate_and_defer_is_not_completion(self):
  with tempfile.TemporaryDirectory() as d,patch.object(O.C,'CONFIG_DIR',d):
   O.handle('alice',{'action':'defer'});self.assertTrue(O.preferences('alice')['seen']);self.assertFalse(O.preferences('alice')['completed']);self.assertEqual(O.preferences('bob'),{})
 def test_incomplete_machine_cannot_claim_ready(self):
  with patch.object(O,'status',return_value={'tools_ready':False,'project_ready':True,'capcut_installed':True}),patch.object(O.C,'_atomic_json') as save:
   with self.assertRaises(ValueError):O.handle('alice',{'action':'finish'})
   save.assert_not_called()
 def test_finish_persists_after_restart(self):
  with tempfile.TemporaryDirectory() as d,patch.object(O.C,'CONFIG_DIR',d),patch.object(O,'status',return_value={'tools_ready':True,'project_ready':True,'capcut_installed':True}):
   O.handle('alice',{'action':'finish'});self.assertTrue(O.preferences('alice')['completed'])
 def test_lock_blocks_second_release_and_releases_on_close(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'instance.lock';one=I.InstanceLock(path);two=I.InstanceLock(path)
   try:
    self.assertTrue(one.acquire('/first.app')[0]);ok,owner=two.acquire('/second.app');self.assertFalse(ok);self.assertEqual(owner['app'],'/first.app');one.release();self.assertTrue(two.acquire('/second.app')[0])
   finally:one.release();two.release()
 def test_update_installed_app_keeps_exact_location_and_name(self):
  with tempfile.TemporaryDirectory() as d,patch.object(U.Path,'home',return_value=Path(d)):
   app=Path(d)/'Applications/CustomName.app';(app/'Contents').mkdir(parents=True);(app/'Contents/Info.plist').write_bytes(plistlib.dumps({'CFBundleIdentifier':U.BUNDLE_ID}))
   self.assertEqual(U._installation_target(app),app)
 def test_protected_installed_location_does_not_make_another_copy(self):
  with patch.object(U,'_probe_install_directory',return_value=False):
   with self.assertRaisesRegex(ValueError,'ไม่สร้างแอปอีกตัว'):U._installation_target(Path('/Applications/NoSuchStudio.app'))
