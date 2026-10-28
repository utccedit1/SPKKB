import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from ks import broll_auto as B, core_engine as CE, cli_lab_commit as C, cli_results as R, event_timeline as T


class BrollOnlyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.media_tmp=tempfile.TemporaryDirectory();cls.video=Path(cls.media_tmp.name)/'stock.mp4'
        binary=CE.ac_ffmpeg_bin()
        if not binary:raise unittest.SkipTest('ffmpeg unavailable')
        subprocess.run([binary,'-nostdin','-v','error','-f','lavfi','-i','color=blue:s=160x90:r=10','-f','lavfi','-i','sine=frequency=440:sample_rate=16000','-t','3','-c:v','libx264','-c:a','aac','-pix_fmt','yuv420p',str(cls.video)],check=True,capture_output=True,timeout=30)
    @classmethod
    def tearDownClass(cls):cls.media_tmp.cleanup()
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.proj=self.root/'project';self.proj.mkdir()
        self.draft={'id':'original','name':'Original','duration':20000000,'fps':30,'canvas_config':{'width':160,'height':90},'render_index_track_mode_on':True,
            'materials':{'videos':[{'id':'v','path':str(self.video),'width':160,'height':90}],'audios':[{'id':'music','path':str(self.video)}],'texts':[{'id':'text','content':json.dumps({'text':'original captions','styles':[]})}],'speeds':[]},
            'tracks':[{'id':'vtrack','type':'video','segments':[{'id':'vseg','material_id':'v','volume':.6,'speed':1,'render_index':0,'target_timerange':{'start':0,'duration':20000000},'source_timerange':{'start':0,'duration':20000000},'common_keyframes':[{'id':'key','property_type':'KFTypeScaleX','keyframe_list':[{'time_offset':0,'values':[1.2]}]}]}]},
                      {'id':'mtrack','type':'audio','name':'Music','segments':[{'id':'mseg','material_id':'music','volume':.12,'target_timerange':{'start':0,'duration':20000000}}]},
                      {'id':'ttrack','type':'text','segments':[{'id':'tseg','material_id':'text','render_index':14000,'target_timerange':{'start':0,'duration':20000000}}]}]}
        self.raw=json.dumps(self.draft).encode();(self.proj/'draft_info.json').write_bytes(self.raw)
        self.record=dict(path=str(self.video),duration=3,title='blue clip',url='https://artlist.io/stock-footage/clip/fixture',sha256=hashlib.sha256(self.video.read_bytes()).hexdigest())
        self.ideas=dict(ok=True,items=[dict(start=1,end=3,query='blue sky',keywords=['blue clouds'])])
        patches=[patch.object(B.A,'ensure_ready'),patch.object(B.P,'settings',return_value={'destination':str(self.root/'media')}),patch.object(B.broll,'api_broll',return_value=self.ideas),patch.object(B.A,'wait_download',return_value=self.record),patch.object(CE,'CONFIG_DIR',str(self.root/'private')),patch.dict(os.environ,{'KS_JOB_STATE_DIR':str(self.root/'receipts')}),patch.object(T,'ensure_closed')]
        for mock in patches:mock.start();self.addCleanup(mock.stop)
    def build(self):return B.build('alice',self.proj,dict(media_kind='footage',max_shots=8),lambda message:None)
    def test_real_cli_add_only_and_guarded_commit(self):
        result=self.build();self.assertEqual(result['inserted'],1)
        self.assertEqual((self.proj/'draft_info.json').read_bytes(),self.raw)
        edited=json.loads((Path(result['destination'])/'draft_info.json').read_bytes())
        B.validate_additions(self.draft,edited)
        self.assertEqual(edited['tracks'][:3],self.draft['tracks'])
        self.assertEqual(edited['tracks'][-1]['segments'][0]['volume'],0)
        preview=R.review('alice',self.proj,result['result_id'])
        applied=C.commit('alice',self.proj,preview['install_id'])
        self.assertTrue(applied['ok']);B.validate_additions(self.draft,json.loads((self.proj/'draft_info.json').read_bytes()))
    def test_preservation_rejects_every_other_edit(self):
        result=self.build();edited=json.loads((Path(result['destination'])/'draft_info.json').read_bytes())
        for name,mutate in [('cut',lambda d:d['tracks'][0]['segments'][0]['target_timerange'].update(duration=1000000)),('music',lambda d:d['tracks'][1]['segments'][0].update(volume=1)),('caption',lambda d:d['materials']['texts'][0].update(content='changed')),('settings',lambda d:d.update(duration=30000000)),('material_deleted',lambda d:d['materials'].pop('audios'))]:
            d=copy.deepcopy(edited);mutate(d)
            with self.subTest(name=name),self.assertRaises(ValueError):B.validate_additions(self.draft,d)
    def test_no_downloads_never_changes_project(self):
        with patch.object(B.A,'wait_download',return_value=None),self.assertRaisesRegex(ValueError,'ยังไม่มี B-roll'):self.build()
        self.assertEqual((self.proj/'draft_info.json').read_bytes(),self.raw)
    def test_source_change_during_download_blocks_output(self):
        def download(*args):(self.proj/'draft_info.json').write_bytes(self.raw+b' ');return self.record
        with patch.object(B.A,'wait_download',side_effect=download),self.assertRaisesRegex(ValueError,'โปรเจกต์เปลี่ยน'):self.build()
        self.assertEqual((self.proj/'draft_info.json').read_bytes(),self.raw+b' ')
    def test_cancel_never_publishes_or_writes_project(self):
        def cancel(message):raise InterruptedError('cancelled')
        with self.assertRaises(InterruptedError):B.build('alice',self.proj,{},cancel)
        self.assertEqual((self.proj/'draft_info.json').read_bytes(),self.raw)
    def test_memes_and_other_providers_not_silently_downloaded(self):
        for cfg in ({'media_kind':'meme'},{'provider':'envato'},{'max_shots':31}):
            with self.assertRaises(ValueError):B.build('alice',self.proj,cfg,lambda message:None)
    def test_old_overlay_is_not_replaced(self):
        overlay=copy.deepcopy(self.draft['tracks'][0]);overlay.update(id='old-overlay',name='Existing B-roll');overlay['segments'][0].update(id='old-shot',target_timerange={'start':1000000,'duration':2000000})
        d=copy.deepcopy(self.draft);d['tracks'].append(overlay);raw=json.dumps(d).encode();(self.proj/'draft_info.json').write_bytes(raw)
        with patch.object(B.A,'wait_download') as fetch,self.assertRaisesRegex(ValueError,'ยังไม่มี B-roll'):self.build()
        fetch.assert_not_called();self.assertEqual((self.proj/'draft_info.json').read_bytes(),raw)
    def test_partial_import_failure_restores_original_edit(self):
        result=self.build();preview=R.review('alice',self.proj,result['result_id'])
        # Simulate a partial write and verify the existing transaction rollback.
        real=T.replace_files
        def interrupted(proj,updates):
            if not getattr(interrupted,'failed',False):
                interrupted.failed=True;(self.proj/'draft_info.json').write_bytes(b'{}');raise OSError('fixture disk full')
            return real(proj,updates)
        with patch.object(T,'replace_files',side_effect=interrupted),self.assertRaises(OSError):C.commit('alice',self.proj,preview['install_id'])
        self.assertEqual((self.proj/'draft_info.json').read_bytes(),self.raw)

    def test_tampered_result_is_rejected_before_import(self):
        result=self.build();file=Path(result['destination'])/'draft_info.json';d=json.loads(file.read_bytes());d['tracks'][1]['segments'][0]['volume']=1;file.write_text(json.dumps(d))
        with self.assertRaises(ValueError):R.review('alice',self.proj,result['result_id'])
        # The manual-folder path must enforce the same add-only invariant.
        with self.assertRaises(ValueError):C.preview('alice',self.proj,result['destination'])
        self.assertEqual((self.proj/'draft_info.json').read_bytes(),self.raw)

    def saved_paths(self, nested=False):
        import shutil
        root=self.proj
        if nested:
            self.proj=root/'Timelines'/'main';self.proj.mkdir(parents=True)
        media=root/'materials/video/C6418.MP4';media.parent.mkdir(parents=True);shutil.copyfile(self.video,media)
        placeholder='##_draftpath_placeholder_0E685133-18CE-45ED-8CB8-2904A212EC80_##/materials/video/C6418.MP4'
        self.draft['materials']['videos'][0]['path']=placeholder
        self.draft['materials']['audios'][0]['path']=placeholder
        self.raw=json.dumps(self.draft).encode();(self.proj/'draft_info.json').write_bytes(self.raw)
        return media,placeholder

    def test_placeholder_survives_build_review_and_commit_unchanged(self):
        for nested in (False,True):
            with self.subTest(nested=nested):
                if nested: self.proj=self.root/'nested';self.proj.mkdir()
                media,placeholder=self.saved_paths(nested)
                result=self.build()
                output=json.loads((Path(result['destination'])/'draft_info.json').read_bytes())
                self.assertEqual(output['materials']['videos'][0]['path'],placeholder)
                self.assertEqual((self.proj/'draft_info.json').read_bytes(),self.raw)
                preview=R.review('alice',self.proj,result['result_id'])
                self.assertTrue(C.commit('alice',self.proj,preview['install_id'])['ok'])
                final=json.loads((self.proj/'draft_info.json').read_bytes());B.validate_additions(self.draft,final)
                self.assertEqual(final['materials']['videos'][0]['path'],placeholder)

    def test_missing_placeholder_fails_before_ai_or_stock(self):
        media,_=self.saved_paths();media.unlink()
        with patch.object(B.broll,'api_broll') as ai,patch.object(B.A,'wait_download') as fetch,self.assertRaisesRegex(ValueError,'ไม่พบสื่อ'):
            self.build()
        ai.assert_not_called();fetch.assert_not_called()
        self.assertEqual((self.proj/'draft_info.json').read_bytes(),self.raw)

    def test_placeholder_media_change_after_build_blocks_review_and_commit(self):
        media,_=self.saved_paths();result=self.build()
        preview=R.review('alice',self.proj,result['result_id'])
        media.write_bytes(b'changed media')
        with self.assertRaises(ValueError):R.review('alice',self.proj,result['result_id'])
        with self.assertRaises(ValueError):C.commit('alice',self.proj,preview['install_id'])
        self.assertEqual((self.proj/'draft_info.json').read_bytes(),self.raw)
