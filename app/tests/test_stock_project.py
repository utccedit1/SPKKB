import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from ks import stock_project as P,stock_accounts as A


class ProjectStorageTests(unittest.TestCase):
    def test_storage_is_scoped_by_user_and_project_and_survives_reload(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);base=root/'Footage';base.mkdir()
            with patch.object(A,'user_root',side_effect=lambda owner:root/owner):
                one=P.settings('one',root/'Project/Timelines/main',str(base))
                self.assertEqual(one,P.settings('one',root/'Project'))
                self.assertNotEqual(one['destination'],P.settings('one',root/'Other',str(base))['destination'])
                self.assertEqual(P.settings('two',root/'Project')['folder'],'')
                self.assertEqual(Path(P.settings('one',root/'Project','')['destination']),root.resolve()/'Project/ช่วยด้วยจ้า สื่อ')

    def test_selection_rejects_missing_or_relative_folder(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(A,'user_root',return_value=Path(folder)/'prefs'):
            for path in ('relative','/missing-fixture-stock-folder'):
                with self.assertRaises(ValueError):P.settings('one',folder,path)

    def test_reuse_does_not_overwrite_user_edits_and_distinct_media_do_not_collide(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'input.mp4';source.write_bytes(b'first media')
            target=Path(P.store(source,root/'project','B-roll','../desk'))
            self.assertEqual(target.parent,root/'project/B-roll')
            self.assertEqual(P.store(source,root/'project','B-roll','../desk'),str(target))
            source.write_bytes(b'second media')
            self.assertNotEqual(P.store(source,root/'project','B-roll','../desk'),str(target))
            source.write_bytes(b'first media');target.write_bytes(b'user edit')
            with self.assertRaises(ValueError):P.store(source,root/'project','B-roll','../desk')

    def test_removable_drive_without_hardlinks(self):
        import errno
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'clip.mp4';source.write_bytes(b'footage')
            with patch.object(P.os,'link',side_effect=OSError(errno.EOPNOTSUPP,'unsupported')):
                target=P.store(source,root/'drive','B-roll')
            self.assertEqual(Path(target).read_bytes(),b'footage')
