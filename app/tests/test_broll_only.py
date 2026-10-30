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

    def test_receipt_failure_after_commit_is_reported_and_recovered(self):
        result=self.build();preview=R.review('alice',self.proj,result['result_id'])
        with patch.object(R,'imported',side_effect=OSError('disk unavailable')):
            applied=C.commit('alice',self.proj,preview['install_id'])
            self.assertTrue(applied['ok']);self.assertIn('บันทึกโปรเจกต์แล้ว',applied['warning'])
            self.assertEqual(R.listing('alice',self.proj)['results'],[])
        C._tickets.clear()
        self.assertEqual(C.check('alice',self.proj,preview['install_id'])['state'],'committed')
        self.assertEqual(C.check('bob',self.proj,preview['install_id'])['state'],'unknown')
        self.assertEqual(R.listing('alice',self.proj)['results'],[])
        with self.assertRaises(ValueError):C.commit('alice',self.proj,preview['install_id'])
        (self.proj/T.JOURNAL).write_text('{}')
        self.assertEqual(C.check('alice',self.proj,preview['install_id'])['state'],'unknown')

    def test_receipt_write_fails_before_transaction_leaves_source_unchanged(self):
        result=self.build();preview=R.review('alice',self.proj,result['result_id'])
        with patch.object(C.job_store,'save',side_effect=OSError('disk unavailable')):
            with self.assertRaises(OSError):C.commit('alice',self.proj,preview['install_id'])
        self.assertEqual((self.proj/'draft_info.json').read_bytes(),self.raw)
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

    def test_import_registers_added_media_and_survives_output_and_library_removal(self):
        import shutil
        old={'id':'old-entry','file_Path':str(self.video),'custom':'preserve'}
        meta={'draft_id':'original','custom':{'keep':True},'draft_materials':[{'type':0,'value':[old]},{'type':7,'value':[]}]}
        (self.proj/'draft_meta_info.json').write_text(json.dumps(meta))
        result=self.build();review=R.review('alice',self.proj,result['result_id'])
        C.commit('alice',self.proj,review['install_id'])
        shutil.rmtree(result['destination']);shutil.rmtree(self.root/'media')
        edited=json.loads((self.proj/'draft_info.json').read_bytes());B.validate_additions(self.draft,edited)
        metadata=json.loads((self.proj/'draft_meta_info.json').read_bytes())
        self.assertEqual(metadata['custom'],meta['custom']);self.assertEqual(metadata['draft_materials'][0]['value'][0],old)
        new=edited['materials']['videos'][1];self.assertTrue(Path(new['path']).is_relative_to(self.proj.resolve()))
        self.assertTrue(Path(new['path']).is_file())
        entries=[e for g in metadata['draft_materials'] for e in g['value']]
        entry=next(e for e in entries if e['id']==new['local_material_id'])
        self.assertEqual(entry['file_Path'],new['path'])

    def test_download_error_does_not_repeat_on_alternative_queries(self):
        with patch.object(B.A,'wait_download',side_effect=B.A.StockDownloadError('Chrome unavailable','timeout')) as fetch,self.assertRaises(B.A.StockDownloadError):
            self.build()
        self.assertEqual(fetch.call_count,1)
        self.assertEqual((self.proj/'draft_info.json').read_bytes(),self.raw)

    def test_progress_includes_real_counts_and_stages(self):
        rows=[];B.build('alice',self.proj,{'max_shots':10},rows.append)
        self.assertEqual(rows[-1]['prepared'],1);self.assertEqual(rows[-1]['downloaded'],1)
        self.assertEqual(rows[-1]['requested'],10);self.assertEqual(rows[-1]['attempted'],1)
        self.assertTrue(any(r['stage']=='framing' for r in rows))

    def test_registered_metadata_rolls_back_after_partial_failure(self):
        meta={'draft_id':'original','draft_materials':[{'type':0,'value':[]}]}
        raw=json.dumps(meta).encode();(self.proj/'draft_meta_info.json').write_bytes(raw)
        result=self.build();review=R.review('alice',self.proj,result['result_id'])
        real=T.replace_files
        def fail(proj,updates):
            if not getattr(fail,'once',False):
                fail.once=True;(self.proj/'draft_meta_info.json').write_bytes(updates['draft_meta_info.json']);raise OSError('fixture disk failure')
            return real(proj,updates)
        with patch.object(T,'replace_files',side_effect=fail),self.assertRaises(OSError):C.commit('alice',self.proj,review['install_id'])
        self.assertEqual((self.proj/'draft_meta_info.json').read_bytes(),raw)
        self.assertEqual((self.proj/'draft_info.json').read_bytes(),self.raw)

    def test_reveal_folder_scoped_to_current_project(self):
        from ks import cli_lab as L
        with patch.object(L.subprocess,'run') as launch,self.assertRaises(ValueError):
            L.handle('alice',self.proj,{'action':'broll_media_folder','path':'/untrusted'})
        launch.assert_not_called()
        assets=self.proj/'cli_lab_assets';assets.mkdir()
        with patch.object(L.subprocess,'run') as launch:
            L.handle('alice',self.proj,{'action':'broll_media_folder','path':'/untrusted'})
        self.assertEqual(launch.call_args.args[0][-1],str(assets.resolve()))

    def test_existing_import_can_repair_registry_without_adding_duplicate_shots(self):
        from ks import broll_assets as A
        result=self.build();review=R.review('alice',self.proj,result['result_id']);C.commit('alice',self.proj,review['install_id'])
        d=json.loads((self.proj/'draft_info.json').read_bytes())
        for m in A.repair_materials(d):m['local_material_id']=''
        before=copy.deepcopy(d);(self.proj/'draft_info.json').write_text(json.dumps(d))
        (self.proj/'draft_meta_info.json').write_text(json.dumps({'draft_id':d['id'],'draft_materials':[]}))
        preview=A.prepare_repair('alice',self.proj)
        C.commit('alice',self.proj,preview['install_id'])
        final=json.loads((self.proj/'draft_info.json').read_bytes());A.validate_repair(before,final)
        self.assertEqual(final['tracks'],before['tracks'])
        meta=json.loads((self.proj/'draft_meta_info.json').read_bytes())
        for m in A.repair_materials(final):
            self.assertTrue(Path(m['path']).is_file());self.assertTrue(m['local_material_id'])
            self.assertTrue(any(e['id']==m['local_material_id'] and e['file_Path']==m['path'] for g in meta['draft_materials'] for e in g['value']))
        changed=copy.deepcopy(final);changed['tracks'][0]['segments'][0]['volume']=1
        with self.assertRaises(ValueError):A.validate_repair(before,changed)

    def test_nested_project_registers_broll_in_root_and_timeline_metadata(self):
        root=self.proj;self.saved_paths(nested=True)
        (root/'draft_info.json').write_bytes(self.raw)
        (root/'draft_meta_info.json').write_text(json.dumps({'draft_id':'original','keep':'root','draft_materials':[]}))
        result=self.build();review=R.review('alice',self.proj,result['result_id']);C.commit('alice',self.proj,review['install_id'])
        final=json.loads((self.proj/'draft_info.json').read_bytes());new=final['materials']['videos'][1]
        for folder in (root,self.proj):
            meta=json.loads((folder/'draft_meta_info.json').read_bytes())
            self.assertTrue(any(e['id']==new['local_material_id'] and e['file_Path']==new['path'] for g in meta['draft_materials'] for e in g['value']))
        self.assertEqual(json.loads((root/'draft_meta_info.json').read_bytes())['keep'],'root')

    def test_repair_with_existing_registry_id_preserves_old_entries(self):
        from ks import broll_assets as A
        result=self.build();preview=R.review('alice',self.proj,result['result_id']);C.commit('alice',self.proj,preview['install_id'])
        old=json.loads((self.proj/'draft_meta_info.json').read_bytes())['draft_materials'][0]['value'][0]
        preview=A.prepare_repair('alice',self.proj);C.commit('alice',self.proj,preview['install_id'])
        entries=json.loads((self.proj/'draft_meta_info.json').read_bytes())['draft_materials'][0]['value']
        self.assertEqual(entries[0],old);self.assertNotEqual(entries[-1]['id'],old['id'])

    def test_repair_after_capcut_strips_custom_role_uses_exact_muted_track_name(self):
        from ks import broll_assets as A
        result=self.build();review=R.review('alice',self.proj,result['result_id']);C.commit('alice',self.proj,review['install_id'])
        d=json.loads((self.proj/'draft_info.json').read_bytes())
        for track in d['tracks']:track.pop('ks_role',None)
        before=copy.deepcopy(d);(self.proj/'draft_info.json').write_text(json.dumps(d))
        preview=A.prepare_repair('alice',self.proj);C.commit('alice',self.proj,preview['install_id'])
        A.validate_repair(before,json.loads((self.proj/'draft_info.json').read_bytes()))
        for track in d['tracks']:
            if track.get('name')==B.NAME:track['segments'][0]['volume']=1
        with self.assertRaises(ValueError):A.repair_materials(d)

    def test_hidden_overlay_does_not_block_and_is_preserved(self):
        overlay=copy.deepcopy(self.draft['tracks'][0]);overlay.update(id='hidden-overlay',attribute=1,name='Existing hidden image')
        d=copy.deepcopy(self.draft);d['tracks'].append(overlay);raw=json.dumps(d).encode();(self.proj/'draft_info.json').write_bytes(raw)
        result=self.build();self.assertEqual(result['inserted'],1)
        edited=json.loads((Path(result['destination'])/'draft_info.json').read_bytes())
        B.validate_additions(d,edited);self.assertEqual(edited['tracks'][:len(d['tracks'])],d['tracks'])
        self.assertEqual((self.proj/'draft_info.json').read_bytes(),raw)

    def test_full_visible_overlay_stops_before_ai_or_stock_with_reason(self):
        overlay=copy.deepcopy(self.draft['tracks'][0]);overlay.update(id='full-overlay');overlay['segments'][0]['id']='other-shot'
        d=copy.deepcopy(self.draft);d['tracks'].append(overlay);raw=json.dumps(d).encode();(self.proj/'draft_info.json').write_bytes(raw)
        with patch.object(B.broll,'api_broll') as ai,patch.object(B.A,'wait_download') as fetch,self.assertRaises(B.PreparationError) as caught:self.build()
        ai.assert_not_called();fetch.assert_not_called();self.assertIn('ยังไม่เริ่มค้น Artlist',str(caught.exception))
        self.assertEqual(caught.exception.summary['attempted'],0);self.assertIn('existing_visuals_cover_timeline',caught.exception.summary['skip_reasons'])
        self.assertEqual((self.proj/'draft_info.json').read_bytes(),raw)

    def test_blocked_candidate_logs_real_reason_and_skip_count(self):
        overlay=copy.deepcopy(self.draft['tracks'][0]);overlay.update(id='overlay');overlay['segments'][0].update(id='other-shot',target_timerange={'start':1000000,'duration':2000000})
        d=copy.deepcopy(self.draft);d['tracks'].append(overlay);(self.proj/'draft_info.json').write_text(json.dumps(d));messages=[]
        with patch.object(B.A,'wait_download') as fetch,self.assertRaises(B.PreparationError) as caught:
            B.build('alice',self.proj,{},messages.append)
        fetch.assert_not_called();self.assertEqual(caught.exception.summary['skipped'],1)
        self.assertEqual(caught.exception.summary['skip_reasons'],{'occupied':1})
        self.assertTrue(any('ทับแทร็กภาพเดิม' in m['message'] for m in messages))
        self.assertEqual(messages[-1]['skip_reasons'],{'occupied':1})

    def test_invalid_time_or_query_is_not_reported_as_stock_search_failure(self):
        cases=[(dict(start=30,end=31,query='blue sky',keywords=[]),'invalid_timing'),(dict(start=1,end=1.2,query='blue sky',keywords=[]),'short_window'),(dict(start=1,end=3,query='ภาษาไทย',keywords=[]),'invalid_query')]
        for idea,reason in cases:
            with self.subTest(reason=reason),patch.object(B.broll,'api_broll',return_value={'ok':True,'items':[idea]}),patch.object(B.A,'wait_download') as fetch,self.assertRaises(B.PreparationError) as caught:self.build()
            fetch.assert_not_called();self.assertEqual(caught.exception.summary['skip_reasons'],{reason:1});self.assertEqual(caught.exception.summary['attempted'],0)

    def test_no_match_is_distinct_from_skipping_before_search(self):
        with patch.object(B.A,'wait_download',return_value=None),self.assertRaises(B.PreparationError) as caught:self.build()
        self.assertGreater(caught.exception.summary['attempted'],0);self.assertEqual(caught.exception.summary['skip_reasons'],{'no_match':1})
        self.assertIn('ค้น Artlist แล้ว',str(caught.exception))

    def test_eighteen_blocked_ideas_report_zero_searches_and_eighteen_skips(self):
        overlay=copy.deepcopy(self.draft['tracks'][0]);overlay.update(id='overlay')
        overlay['segments'][0].update(id='other-shot',target_timerange={'start':1000000,'duration':18000000})
        draft=copy.deepcopy(self.draft);draft['tracks'].append(overlay);raw=json.dumps(draft).encode();(self.proj/'draft_info.json').write_bytes(raw)
        ideas={'ok':True,'items':[dict(start=1,end=3,query='phone screen '+str(i),keywords=[]) for i in range(18)]};messages=[]
        with patch.object(B.broll,'api_broll',return_value=ideas),patch.object(B.A,'wait_download') as fetch,self.assertRaises(B.PreparationError) as caught:
            B.build('alice',self.proj,{'max_shots':18},messages.append)
        fetch.assert_not_called();summary=caught.exception.summary
        self.assertEqual((summary['prepared'],summary['attempted'],summary['skipped']),(0,0,18))
        self.assertEqual(summary['skip_reasons'],{'occupied':18});self.assertIn('ทับภาพเดิม 18 ช่วง',str(caught.exception))
        self.assertEqual(sum('ข้ามแล้ว' in row['message'] for row in messages),18)
        self.assertEqual((self.proj/'draft_info.json').read_bytes(),raw)

    def test_very_short_empty_timeline_is_not_blame_on_existing_overlay(self):
        d=copy.deepcopy(self.draft);d['duration']=200000;(self.proj/'draft_info.json').write_text(json.dumps(d))
        with patch.object(B.broll,'api_broll',return_value={'ok':True,'items':[dict(start=0,end=.2,query='blue sky',keywords=[])]}),self.assertRaises(B.PreparationError) as caught:self.build()
        self.assertNotIn('existing_visuals_cover_timeline',caught.exception.summary['skip_reasons'])
        self.assertEqual(caught.exception.summary['skip_reasons'],{'short_window':1})
