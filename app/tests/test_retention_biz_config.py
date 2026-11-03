import json,tempfile,unittest
from pathlib import Path
from ks import storage_manager as M

class RetentionBizConfigTests(unittest.TestCase):
    def test_empty_biz_config_allows_scan_but_keeps_real_references(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);build=root/'dist-1.5.1';build.mkdir();project=root/'project';project.mkdir()
            (project/'draft_biz_config.json').write_bytes(b'')
            (project/'draft_info.json').write_text(json.dumps({'media':str(build/'footage.mp4')}))
            self.assertEqual(M._referenced([build],[project]),{str(build.resolve())})
    def test_corrupt_nonempty_biz_and_empty_other_draft_still_block(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);build=root/'dist-1.5.1';build.mkdir();project=root/'project';project.mkdir()
            biz=project/'draft_biz_config.json';biz.write_bytes(b'{broken')
            with self.assertRaises(ValueError):M._referenced([build],[project])
            biz.unlink();(project/'draft_info.json').write_bytes(b'')
            with self.assertRaises(ValueError):M._referenced([build],[project])
    def test_valid_biz_config_references_are_still_protected(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);build=root/'dist-1.5.1';build.mkdir();project=root/'project';project.mkdir()
            (project/'draft_biz_config.json').write_text(json.dumps({'file':str(build/'media.mp4')}))
            self.assertEqual(M._referenced([build],[project]),{str(build.resolve())})
