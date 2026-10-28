import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ks import cli_lab_commit as C,event_timeline as T,unified_history as H


class CommitTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        env=patch.dict(os.environ,{'KS_JOB_STATE_DIR':str(Path(self.tmp.name)/'receipts')});env.start();self.addCleanup(env.stop)
        self.root=Path(self.tmp.name)/'project';self.target=self.root/'Timelines/main';self.target.mkdir(parents=True)
        self.result=Path(self.tmp.name)/'result';self.result.mkdir()
        self.media=Path(self.tmp.name)/'video.mp4';self.media.write_bytes(b'fixture')
        self.draft={'id':'main','name':'Original','duration':60000000,'materials':{'videos':[{'id':'v','path':str(self.media)}]},'tracks':[{'type':'video','segments':[{'id':'s','material_id':'v','target_timerange':{'start':0,'duration':60000000}}]}]}
        self.before=json.dumps(self.draft).encode()
        for p in (self.root,self.target):
            (p/'draft_info.json').write_bytes(self.before);(p/'template-2.tmp').write_bytes(self.before)
        (self.root/'draft_meta_info.json').write_text(json.dumps({'draft_id':'project-id','draft_name':'Original','tm_duration':60000000}))
        edited=json.loads(self.before);edited.update(id='new-copy',name='Copy',duration=31200000)
        edited['tracks'][0]['segments'][0]['target_timerange']['duration']=31200000
        (self.result/'draft_info.json').write_text(json.dumps(edited))
        self.closed=patch.object(T,'ensure_closed');self.closed.start();self.addCleanup(self.closed.stop)

    def preview(self):return C.preview('owner',self.target,self.result)

    def test_replaces_main_and_all_mirrors_preserving_identity_then_restores(self):
        preview=self.preview();result=C.commit('owner',self.target,preview['install_id'])
        for folder in (self.root,self.target):
            for name in ('draft_info.json','template-2.tmp'):
                edited=json.loads((folder/name).read_bytes());self.assertEqual(edited['id'],'main');self.assertEqual(edited['duration'],31200000)
        meta=json.loads((self.root/'draft_meta_info.json').read_bytes());self.assertEqual(meta['draft_id'],'project-id');self.assertEqual(meta['tm_duration'],31200000)
        H.restore(str(self.target),{'id':'checkpoint:'+result['backup_name'],'source_hash':H.digest((self.target/'draft_info.json').read_bytes())})
        for folder in (self.root,self.target):
            self.assertEqual((folder/'draft_info.json').read_bytes(),self.before)
            self.assertEqual((folder/'template-2.tmp').read_bytes(),self.before)

    def test_stale_source_output_or_owner_is_rejected(self):
        preview=self.preview()
        with self.assertRaises(ValueError):C.commit('other',self.target,preview['install_id'])
        (self.result/'draft_info.json').write_text('{}')
        with self.assertRaises(ValueError):C.commit('owner',self.target,preview['install_id'])
        self.assertEqual((self.target/'draft_info.json').read_bytes(),self.before)

    def test_review_remains_valid_after_days_and_process_restart(self):
        preview=self.preview()
        C._tickets.clear()
        with patch.object(C.time,'time',return_value=2000000000):
            result=C.commit('owner',self.target,preview['install_id'])
        self.assertTrue(result['ok'])
        with self.assertRaises(ValueError):C.commit('owner',self.target,preview['install_id'])

    def test_persisted_review_rejects_changed_media(self):
        preview=self.preview();C._tickets.clear();self.media.write_bytes(b'changed media')
        with self.assertRaisesRegex(ValueError,'ไฟล์สื่อเปลี่ยน'):C.commit('owner',self.target,preview['install_id'])
        self.assertEqual((self.target/'draft_info.json').read_bytes(),self.before)

    def test_persisted_review_rejects_other_project(self):
        preview=self.preview();C._tickets.clear()
        with self.assertRaisesRegex(ValueError,'โปรเจกต์อื่น'):C.commit('owner',self.root,preview['install_id'])
        self.assertEqual((self.target/'draft_info.json').read_bytes(),self.before)

    def test_editor_open_prevents_any_change(self):
        preview=self.preview()
        with patch.object(T,'ensure_closed',side_effect=ValueError('editor open')),self.assertRaises(ValueError):
            C.commit('owner',self.target,preview['install_id'])
        self.assertFalse((self.target/T.BACKUPS).exists())

    def test_partial_io_failure_rolls_back_every_timeline(self):
        preview=self.preview();real=T.replace_files;calls=[]
        def fail_once(project,updates):
            calls.append(True)
            if len(calls)==1:
                (self.target/'draft_info.json').write_bytes(b'{}');raise OSError('disk full')
            return real(project,updates)
        with patch.object(T,'replace_files',side_effect=fail_once),self.assertRaises(OSError):C.commit('owner',self.target,preview['install_id'])
        for folder in (self.root,self.target):
            self.assertEqual((folder/'draft_info.json').read_bytes(),self.before)
            self.assertEqual((folder/'template-2.tmp').read_bytes(),self.before)

    def test_result_assets_copied_inside_project(self):
        asset=self.result/'asset.mp4';asset.write_bytes(b'new media')
        draft=json.loads((self.result/'draft_info.json').read_bytes());draft['materials']['videos'][0]['path']=str(asset)
        (self.result/'draft_info.json').write_text(json.dumps(draft))
        result=C.commit('owner',self.target,self.preview()['install_id'])
        material=json.loads((self.target/'draft_info.json').read_bytes())['materials']['videos'][0]
        path=Path(material['path']);self.assertTrue(path.is_relative_to(self.target.resolve()));self.assertEqual(path.read_bytes(),b'new media')

    def test_old_checkpoints_without_optional_mirrors_still_load(self):
        backup=T.checkpoint(str(self.target),'legacy')
        manifest=json.loads((backup/'manifest.json').read_bytes())
        for name in T.EXTRA_MIRRORS:manifest['files'].pop(name)
        (backup/'manifest.json').write_text(json.dumps(manifest))
        old=T.read_checkpoint(str(self.target),backup.name)
        self.assertEqual(old['draft_info.json'],self.before)


if __name__=='__main__':unittest.main()
