import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ks import unified_history as H,event_timeline as T,feature_tasks as F
class HistoryClearTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.p=Path(self.tmp.name)/'Timelines'/'second';self.p.mkdir(parents=True)
  self.raw=json.dumps({'id':'second','tracks':[]}).encode();self.protected={'draft_info.json':self.raw,'draft_info_original.json':b'baseline','draft_info_backup.json':self.raw,'.spinworld_state.json':b'{}'}
  for name,raw in self.protected.items():(self.p/name).write_bytes(raw)
  self.other=self.p.parent.parent/'draft_info.json';self.other.write_bytes(b'{"id":"other"}')
  self.expected=[]
  for folder,name in [(T.BACKUPS,'checkpoint'),('.karaoke_snapshots','draft_0001_20260101_000000_manual.json'),('.autoclip_backups','old')]:
   root=self.p/folder;root.mkdir();entry=root/name
   if folder=='.karaoke_snapshots':entry.write_bytes(self.raw)
   else:
    entry.mkdir();(entry/'draft_info.json').write_bytes(self.raw)
    if folder==T.BACKUPS:(entry/'manifest.json').write_text(json.dumps({'created':1,'label':'manual'}))
   self.expected.append(entry)
 def cfg(self):return {'source_project':str(self.p.resolve()),'source_hash':H.digest(self.raw)}
 def assert_protected(self):
  for name,raw in self.protected.items():self.assertEqual((self.p/name).read_bytes(),raw)
  self.assertEqual(self.other.read_bytes(),b'{"id":"other"}')
 def test_clear_all_types_preserves_initial_and_can_undo_with_new_history(self):
  result=F.run(str(self.p),'history_clear',self.cfg());self.assertEqual(result['removed'],3);self.assertEqual([r['kind'] for r in H.listing(str(self.p))['items']],['initial']);self.assert_protected()
  new=self.p/T.BACKUPS/'new';new.mkdir(parents=True);(new/'draft_info.json').write_bytes(self.raw)
  H.undo_clear(str(self.p),dict(self.cfg(),archive_id=result['archive_id']))
  self.assertTrue(new.is_dir());self.assertTrue(all(p.exists() for p in self.expected));self.assertIsNone(H.latest_clear(str(self.p)));self.assert_protected()
 def test_clear_failure_rolls_back_every_moved_folder(self):
  real=H.os.replace
  def failing(a,b):
   if Path(a)==self.p/'.karaoke_snapshots':raise OSError('disk failure')
   return real(a,b)
  with patch.object(H.os,'replace',side_effect=failing):
   with self.assertRaises(OSError):H.clear(str(self.p),self.cfg())
  self.assertTrue(all(p.exists() for p in self.expected));self.assert_protected()
 def test_stale_or_other_project_and_symlink_block_before_mutation(self):
  for cfg in [dict(self.cfg(),source_hash='stale'),dict(self.cfg(),source_project='/other')]:
   with self.assertRaises(ValueError):H.clear(str(self.p),cfg)
  (self.p/H.ARCHIVE_DIR).symlink_to(self.p.parent,target_is_directory=True)
  with self.assertRaises(ValueError):H.clear(str(self.p),self.cfg())
  self.assertTrue(all(p.exists() for p in self.expected));self.assert_protected()
 def test_undo_collision_never_overwrites_new_history(self):
  result=H.clear(str(self.p),self.cfg());collision=self.expected[0];collision.mkdir(parents=True);(collision/'draft_info.json').write_bytes(b'new history')
  with self.assertRaises(ValueError):H.undo_clear(str(self.p),dict(self.cfg(),archive_id=result['archive_id']))
  self.assertEqual((collision/'draft_info.json').read_bytes(),b'new history');self.assert_protected()
 def test_undo_rejects_traversal_and_foreign_manifest(self):
  result=H.clear(str(self.p),self.cfg())
  with self.assertRaises(ValueError):H.undo_clear(str(self.p),dict(self.cfg(),archive_id='../other'))
  manifest=self.p/H.ARCHIVE_DIR/result['archive_id']/'manifest.json';d=json.loads(manifest.read_text());d['project']='/other';manifest.write_text(json.dumps(d))
  with self.assertRaises(ValueError):H.undo_clear(str(self.p),dict(self.cfg(),archive_id=result['archive_id']))
  self.assert_protected()

 def test_undo_failure_rolls_back_without_losing_archived_history(self):
  result=H.clear(str(self.p),self.cfg());real=H.os.replace
  def failing(a,b):
   if Path(b)==self.expected[1]:raise OSError('disk failure')
   return real(a,b)
  with patch.object(H.os,'replace',side_effect=failing):
   with self.assertRaises(OSError):H.undo_clear(str(self.p),dict(self.cfg(),archive_id=result['archive_id']))
  self.assertFalse(any(p.exists() for p in self.expected));self.assertIsNotNone(H.latest_clear(str(self.p)));self.assert_protected()
  H.undo_clear(str(self.p),dict(self.cfg(),archive_id=result['archive_id']));self.assertTrue(all(p.exists() for p in self.expected))
