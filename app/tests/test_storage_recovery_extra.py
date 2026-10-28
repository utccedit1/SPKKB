import sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ks import storage_manager as M

class StorageRecoveryExtraTests(unittest.TestCase):
    def test_partial_restore_rolls_back_and_ticket_can_retry(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(M,'_trash_root',side_effect=lambda root:root/'.test-trash'):
            root=Path(folder).resolve()
            for version in ('1.0.0','1.0.1','1.0.2','1.0.3','1.0.4','1.0.5','1.0.6'):
                (root/('dist-'+version)).mkdir()
            ticket=M.preview('alice',root,[]);M.move('alice',ticket['cleanup_id'])
            rows=ticket['files'];self.assertEqual(len(rows),2)
            rename=Path.rename;failed=[False]
            def interrupted(path,target):
                if path.name==rows[1]['name'] and Path(target).parent==root and not failed[0]:
                    failed[0]=True;raise OSError('temporary disk failure')
                return rename(path,target)
            with patch.object(Path,'rename',interrupted):
                with self.assertRaises(OSError):M.restore('alice',ticket['cleanup_id'],root)
            self.assertTrue(all(not (root/r['name']).exists() for r in rows))
            M.restore('alice',ticket['cleanup_id'],root)
            self.assertTrue(all((root/r['name']).exists() for r in rows))

    def test_corrupt_draft_error_identifies_blocking_file(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(M,'_trash_root',side_effect=lambda root:root/'.test-trash'):
            root=Path(folder).resolve();draft=root/'draft_info.json';draft.write_text('broken')
            with self.assertRaisesRegex(ValueError,'draft_info.json'):
                M._referenced([root/'old'],[root])
