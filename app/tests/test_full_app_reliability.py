import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ks import ce_config as C, cli_lab as L, ce_features as F, stock_accounts as S, updater as U
from ks.caption_roles import generated_ids
from ks.cli_lab_alignment import speech_segments

class ReliabilityTests(unittest.TestCase):
    def test_sessions_and_worker_snapshot_do_not_follow_another_request(self):
        state=C.SessionState(); state.bind('session-a','alice');state['project']='A'
        seen=[];worker=state.capture(lambda:seen.append((state.get('_current_uid'),state.get('project'))))
        state.bind('session-b','bob');self.assertIsNone(state.get('project'));state['project']='B'
        thread=threading.Thread(target=worker);thread.start();thread.join()
        self.assertEqual(seen,[('alice','A')]);self.assertEqual(state['project'],'B')
        state.bind('session-a','alice');self.assertEqual(state['project'],'A')

    def test_feature_key_is_resolved_after_own_default(self):
        state=C.SessionState();state.bind('a','alice')
        config={'ai_routes':{'suggest':{'backend':'gemini','key_name':'route','model':'chosen-model'}}}
        own={'gemini_keys':[{'name':'default','key':'default-value'},{'name':'route','key':'route-value'}],'gemini_key_name':'default'}
        with tempfile.TemporaryDirectory() as folder,patch.object(C,'CONFIG_FILE',str(Path(folder)/'config.json')),patch.object(C,'STATE',state),patch.object(C,'load_user_keys',return_value=own):
            Path(C.CONFIG_FILE).write_text(json.dumps(config))
            with C.ai_feature('suggest'):result=C.load_config()
        self.assertEqual(result['gemini_api_key'],'route-value');self.assertEqual(result['gemini_model'],'chosen-model')

    def test_route_status_never_returns_authorization(self):
        conf={'ai_routes':{'suggest':{'backend':'webhook','webhook_headers':{'Authorization':'dummy-secret'}}}}
        with patch.object(F,'load_config',return_value=conf):
            self.assertNotIn('dummy-secret',json.dumps(F.api_get_ai_routes()))

    def test_personal_route_save_does_not_write_shared(self):
        state=C.SessionState();state.bind('a','alice')
        with patch.object(C,'STATE',state),patch.object(C,'load_user_keys',return_value={}),patch.object(C,'save_user_keys') as own,patch.object(C,'save_config') as shared:
            C.save_route_config({'ai_routes':{'suggest':{'backend':'gemini'}}})
            shared.assert_not_called();self.assertEqual(own.call_args.args[0],'alice')

    def test_atomic_config_failure_preserves_original(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'config.json';path.write_text('{"old":true}')
            with patch.object(C.os,'replace',side_effect=OSError('disk failure')):
                with self.assertRaises(OSError):C._atomic_json(str(path),{'new':True})
            self.assertEqual(json.loads(path.read_text()),{'old':True});self.assertEqual(list(Path(folder).iterdir()),[path])

    def test_stale_stock_job_no_longer_blocks(self):
        jobs={'stale':{'owner':'alice','created':0,'state':'queued'}}
        with patch.object(S,'_jobs',jobs),patch.object(S,'peer',return_value={'state':'connected','seen':S.time.time()}):
            token=S.submit('alice','artlist',{'kind':'music'})
        self.assertNotEqual(token,'stale');self.assertTrue('stale' not in jobs or jobs['stale']['state']=='failed')

    def test_cli_work_blocks_update(self):
        manager=U.UpdateManager();manager.state='update_available'
        with patch.object(L,'_jobs',{'active':{'state':'running'}}):
            self.assertFalse(manager.download_and_apply_async())
        self.assertEqual(manager.state,'update_available')

    def test_generated_caption_roles_cover_legacy_and_cli(self):
        draft={'tracks':[{'name':n,'segments':[{'id':n}]} for n in ('Super Text','ช่วยด้วยจ้า Box','ช่วยด้วยจ้า · Hook','Captions')]}
        self.assertEqual(generated_ids(draft),{'Super Text','ช่วยด้วยจ้า Box','ช่วยด้วยจ้า · Hook'})

    def test_detached_speech_and_muted_video(self):
        seg=lambda key,vol=1:{'id':key,'material_id':key,'volume':vol,'target_timerange':{'duration':1000000}}
        draft={'materials':{'videos':[{'id':'silent','has_audio':False}],'audios':[{'id':'voice'},{'id':'bgm'}]},'tracks':[{'type':'video','segments':[seg('silent')]},{'type':'audio','name':'Voice','segments':[seg('voice')]},{'type':'audio','name':'Music','segments':[seg('bgm')]}]}
        self.assertEqual([s['id'] for s in speech_segments(draft)],['voice'])


class RecoveryTests(unittest.TestCase):
    def test_legacy_and_package_share_context(self):
        from ks import core_engine as CE
        import ce_config
        self.assertIs(C,ce_config)
        self.assertIs(CE.STATE,C.STATE)

    def test_interrupted_mirror_commit_recovers_old_files(self):
        from ks import event_timeline as T
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for name in ('draft_info.json','draft_content.json'):(root/name).write_bytes(b'{"id":"old"}')
            write=T.atomic_write
            def crash(path,data):
                if path.name=='draft_content.json':raise KeyboardInterrupt('simulated power loss')
                write(path,data)
            with patch.object(T,'atomic_write',side_effect=crash):
                with self.assertRaises(KeyboardInterrupt):T.replace_files(root,{'draft_info.json':b'{"id":"new"}','draft_content.json':b'{"id":"new"}'})
            self.assertTrue((root/T.JOURNAL).is_file())
            self.assertTrue(T.recover_pending(root))
            self.assertFalse((root/T.JOURNAL).exists())
            self.assertEqual((root/'draft_info.json').read_bytes(),b'{"id":"old"}')
            self.assertEqual((root/'draft_content.json').read_bytes(),b'{"id":"old"}')

    def test_restart_receipt_is_owner_scoped_and_marks_interrupted(self):
        import os
        from ks import job_store as J
        with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{'KS_JOB_STATE_DIR':folder}):
            J.save('cli','abc123',{'owner':'alice','state':'running','project':'A'})
            with patch.object(J,'INSTANCE','another-process'):
                result=J.load('alice','cli','abc123')
                self.assertEqual(result['state'],'failed')
                self.assertIsNone(J.load('bob','cli','abc123'))

    def test_overlay_scheduler_and_single_bgm_keep_detached_voice(self):
        from ks.media_schedule import next_slot,remove_background_music
        draft={'tracks':[{'type':'video','segments':[]},{'type':'video','segments':[{'target_timerange':{'start':4000000,'duration':2500000}}]},{'type':'audio','name':'Music','segments':[]},{'type':'audio','name':'Voice','segments':[]}]}
        self.assertEqual(next_slot(draft,4,2.5),9.5)
        remove_background_music(draft)
        self.assertEqual([t['name'] for t in draft['tracks'] if t['type']=='audio'],['Voice'])

    def test_workspace_survives_legacy_page_navigation_and_fetch(self):
        from ks.pages import workspace_page
        ws='a'*32
        html=workspace_page("<head></head><script>location.href='/editor'</script>",ws)
        self.assertIn('/editor?workspace='+ws,html)
        self.assertIn('X-Studio-Workspace',html)

    def test_storage_preview_preserves_five_latest_and_restore_is_owned(self):
        from ks import storage_manager as M
        with tempfile.TemporaryDirectory() as folder, patch.object(M,'_trash_root',side_effect=lambda root:root/'.test-trash'):
            root=Path(folder)
            for v in ('1.5.0','1.5.19','1.5.20','1.5.21','1.5.22','1.5.23'):
                d=root/('dist-'+v);d.mkdir();(d/'fixture.txt').write_text('fixture')
            plan=M.preview('alice',root,reference_roots=[])
            self.assertEqual([r['name'] for r in plan['files']],['dist-1.5.0'])
            M.move('alice',plan['cleanup_id']);self.assertFalse((root/'dist-1.5.0').exists())
            with self.assertRaises(ValueError):M.restore('bob',plan['cleanup_id'],root)
            M.restore('alice',plan['cleanup_id'],root);self.assertTrue((root/'dist-1.5.0').exists())

    def test_packaged_storage_checks_builds_beside_release_not_inside_bundle(self):
        from ks import storage_manager as M
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();bundle=root/'dist-1.5.24-final'/'ช่วยด้วยจ้า.app'
            with patch.object(U,'_get_app_bundle_path',return_value=bundle):self.assertEqual(M.build_root(),root)
            with patch.object(U,'_get_app_bundle_path',return_value=root/'Applications'/'ช่วยด้วยจ้า.app'):self.assertEqual(M.build_root(),root/'Applications')

    def test_storage_protects_referenced_build_and_rechecks_before_move(self):
        from ks import storage_manager as M
        with tempfile.TemporaryDirectory() as folder, patch.object(M,'_trash_root',side_effect=lambda root:root/'.test-trash'):
            root=Path(folder);projects=root/'projects';projects.mkdir()
            for v in ('1.5.0','1.5.19','1.5.20','1.5.21','1.5.22','1.5.23'):(root/('dist-'+v)).mkdir()
            draft=projects/'draft_info.json';draft.write_text('{}')
            plan=M.preview('alice',root,[projects])
            draft.write_text(json.dumps({'media':str(root/'dist-1.5.0/video.mp4')}))
            with self.assertRaisesRegex(ValueError,'อ้างอิง'):M.move('alice',plan['cleanup_id'])
            self.assertTrue((root/'dist-1.5.0').is_dir())
            plan=M.preview('alice',root,[projects])
            self.assertEqual(plan['files'],[]);self.assertEqual(plan['protected'],['dist-1.5.0'])

class LiveBoundaryTests(unittest.TestCase):
    def test_two_workspaces_using_one_cookie_keep_distinct_projects(self):
        import urllib.request
        from http.server import ThreadingHTTPServer
        from ks import server as V
        from ks import core_engine as CE
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);a=root/'A';b=root/'B';a.mkdir();b.mkdir()
            for project in (a,b):(project/'draft_info.json').write_text(json.dumps({'id':project.name,'duration':1000000,'tracks':[],'materials':{}}))
            state=C.SessionState()
            with patch.object(CE,'STATE',state),patch.object(C,'STATE',state),patch.object(V.auth,'session_valid',return_value=True),patch.object(V.auth,'session_user',return_value={'uid':'fixture-user','email':'fixture@example.invalid'}),patch.object(V.Handler,'_is_admin',return_value=False),patch.object(C,'CONFIG_DIR',str(root/'private')),patch.object(C,'CONFIG_FILE',str(root/'config.json')),patch.object(C,'USER_KEYS_DIR',str(root/'keys')):
                server=ThreadingHTTPServer(('127.0.0.1',0),V.Handler)
                worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
                try:
                    base='http://127.0.0.1:'+str(server.server_port)
                    for ws,project in (('a'*32,a),('b'*32,b)):
                        headers={'Cookie':'ks_session=fixture','Content-Type':'application/json','X-Studio-Workspace':ws}
                        request=urllib.request.Request(base+'/api/select_project',data=json.dumps({'path':str(project)}).encode(),headers=headers)
                        with urllib.request.urlopen(request) as response:self.assertTrue(json.load(response)['ok'])
                    for ws,project,other in (('a'*32,a,b),('b'*32,b,a)):
                        with urllib.request.urlopen(urllib.request.Request(base+'/api/project_info?workspace='+ws,headers={'Cookie':'ks_session=fixture'})) as response:info=json.load(response)
                        self.assertEqual(info['path'],str(project.resolve()));self.assertTrue(info['valid'])
                    request=urllib.request.Request(base+'/api/ai_routes/save',data=b'{"scope":"shared","routes":{}}',headers={'Cookie':'ks_session=fixture','Content-Type':'application/json','X-Studio-Workspace':'a'*32})
                    import urllib.error
                    with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(request)
                    self.assertEqual(error.exception.code,403)
                finally:server.shutdown();server.server_close();worker.join(2)

    def test_real_audio_reference_uses_detached_track(self):
        import wave
        import numpy as np
        from ks.cli_lab_alignment import render_speech
        from ks import core_engine as CE
        if not CE.ac_ffmpeg_bin():self.skipTest('ffmpeg unavailable')
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);voice=root/'voice.wav';rate=16000;samples=.2*np.sin(2*np.pi*440*np.arange(rate)/rate)
            with wave.open(str(voice),'wb') as stream:
                stream.setparams((1,2,rate,0,'NONE','not compressed'));stream.writeframes((samples*32767).astype('<i2').tobytes())
            draft={'duration':1000000,'materials':{'videos':[{'id':'silent','has_audio':False}],'audios':[{'id':'voice','path':str(voice)}]},'tracks':[{'type':'video','segments':[{'material_id':'silent','target_timerange':{'start':0,'duration':1000000}}]},{'type':'audio','name':'Voice','segments':[{'material_id':'voice','source_timerange':{'start':0,'duration':1000000},'target_timerange':{'start':0,'duration':1000000},'speed':1,'volume':.5}]}]}
            output=root/'reference.wav';render_speech(draft,output,respect_volume=True)
            with wave.open(str(output),'rb') as stream:decoded=np.frombuffer(stream.readframes(stream.getnframes()),dtype='<i2').astype(float)/32768
            self.assertGreater(np.sqrt(np.mean(decoded**2)),.06);self.assertLess(np.sqrt(np.mean(decoded**2)),.08)

class ExtraRegressionTests(unittest.TestCase):
    def test_blank_webhook_header_preserves_secret(self):
        from ks import ai_router as R
        with patch.object(R.CE,'load_config',return_value={'utcc_webhook_headers':{'Authorization':'dummy-original'}}),patch.object(C,'save_route_config') as save:
            R.set_utcc({'utcc_webhook_url':'https://example.invalid/webhook','utcc_webhook_headers':''})
            self.assertNotIn('utcc_webhook_headers',save.call_args.kwargs['fields'])

    def test_chat_reset_with_empty_message_clears_backend_context(self):
        from ks import chatbot as B
        B._HISTORY['fixture-chat']=[{'role':'user','text':'old context'}]
        with patch.object(B.CE,'call_webhook') as call:
            result=B.api_chatbot({'message':' ','reset':True},session_token='fixture-chat')
            self.assertTrue(result['ok']);self.assertNotIn('fixture-chat',B._HISTORY);call.assert_not_called()

    def test_long_alignment_uses_successive_measured_windows(self):
        import numpy as np
        from ks.cli_lab_alignment import align_windows
        class Tokenizer:
            def encode(self,text):return [1,2]
        class Model:
            count=0
            def feature_extractor(self,audio):return np.zeros((80,len(audio)//160))
            def encode(self,value):return value
            def find_alignment(self,*args):
                self.count+=1
                if self.count==1:return [[{'word':'alpha','start':0,'end':10,'probability':.9},{'word':' beta','start':29,'end':30,'probability':.9}]]
                return [[{'word':' beta','start':10,'end':20,'probability':.9}]]
        result=align_windows(Model(),Tokenizer(),np.zeros(40*16000),'alpha beta',40,lambda x:x)
        self.assertEqual(''.join(x['word'] for x in result),'alpha beta')
        self.assertAlmostEqual(result[1]['start'],19.9)

    def test_legacy_motion_can_be_cut_again_without_duplicate_key_ids(self):
        from ks import cli_lab_story as S
        with tempfile.TemporaryDirectory() as folder:
            draft={'id':'source','duration':6000000,'materials':{'videos':[{'id':'v','path':'/unused.mp4'}]},'tracks':[{'id':'video','type':'video','segments':[{'id':'seg','material_id':'v','speed':1,'extra_material_refs':[],'target_timerange':{'start':0,'duration':6000000},'source_timerange':{'start':0,'duration':6000000},'common_keyframes':[{'id':'same-group','property_type':'KFTypeScaleX','keyframe_list':[{'id':'same-key','time_offset':0,'values':[1]}]}]}]}]}
            result=S.build(draft,[{'start':0,'end':2,'role':'hook'},{'start':3,'end':5,'role':'conclusion'}],folder,L.run_cli,lambda x:None)
            segments=result['tracks'][0]['segments'];ids=[s['common_keyframes'][0]['id'] for s in segments]
            self.assertEqual(len(set(ids)),2);self.assertEqual(segments[1]['source_timerange']['start'],3000000)

class OwnershipAndSettingsTests(unittest.TestCase):
    def test_user_key_filenames_cannot_collide_and_safe_legacy_migrates(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(C,'USER_KEYS_DIR',folder):
            self.assertNotEqual(C._user_key_path('a/b'),C._user_key_path('a_b'))
            legacy=Path(folder)/'legacy-user.json';legacy.write_text(json.dumps({'gemini_keys':[{'name':'own','key':'dummy-own-key'}]}))
            own=C.load_user_keys('legacy-user');C.save_user_keys('legacy-user',own)
            self.assertFalse(legacy.exists());self.assertEqual(C.load_user_keys('legacy-user'),own)
            C.save_user_keys('a_b',{'marker':'other-user'})
            self.assertEqual(C.load_user_keys('a/b'),{})

    def test_delete_keys_preserves_webhook_routes_and_recent_projects(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(C,'USER_KEYS_DIR',folder):
            C.save_user_keys('alice',{'gemini_keys':[{'name':'own','key':'dummy-key'}],'ai_routes':{'caption':{'backend':'webhook_utcc'}},'recent_projects':['A']})
            C.api_user_key_save('alice',{'action':'delete_all'})
            record=C.load_user_keys('alice')
            self.assertEqual(record['gemini_keys'],[]);self.assertEqual(record['recent_projects'],['A']);self.assertIn('caption',record['ai_routes'])

    def test_legacy_status_does_not_expose_any_webhook_header(self):
        conf={'webhook_headers':{'Authorization':'dummy-main-secret'},'audio_webhook_headers':{'X-Secret':'dummy-audio-secret'},'ai_routes':{'caption':{'backend':'webhook','webhook_headers':{'Authorization':'dummy-route-secret'}}}}
        with patch.object(F,'load_config',return_value=conf):result=json.dumps(F.api_gemini_status())
        for secret in ('dummy-main-secret','dummy-audio-secret','dummy-route-secret'):self.assertNotIn(secret,result)

    def test_concurrent_personal_feature_changes_merge_without_lost_updates(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(C,'USER_KEYS_DIR',folder):
            state=C.SessionState();state.bind('session','alice');barrier=threading.Barrier(2)
            def update(feature):
                barrier.wait()
                C.save_route_config({'ai_routes':{feature:{'backend':'gemini'}}},features=[feature],fields=[])
            with patch.object(C,'STATE',state):
                threads=[threading.Thread(target=state.capture(lambda feature=feature:update(feature))) for feature in ('caption','suggest')]
                for thread in threads:thread.start()
                for thread in threads:thread.join(2)
                self.assertEqual(set(C.load_user_keys('alice')['ai_routes']),{'caption','suggest'})

    def test_project_restores_by_owner_and_workspace_after_new_session(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(C,'CONFIG_DIR',folder):
            state=C.SessionState();state.bind('old-session','alice','a'*32)
            with patch.object(C,'STATE',state):C.save_workspace_project('project-a')
            after=C.SessionState();after.bind('new-session','alice','a'*32);self.assertEqual(after['project'],'project-a')
            after.bind('other-session','bob','a'*32);self.assertIsNone(after['project'])

    def test_empty_caption_materials_are_valid_empty_captions(self):
        from ks import core_engine as CE
        self.assertEqual(CE.text_segments({'materials':{},'tracks':[]}),[])

    def test_cancel_does_not_accept_another_owner_or_project(self):
        with tempfile.TemporaryDirectory() as folder:
            job={'owner':'alice','project':str(Path(folder).resolve()),'state':'running'}
            with patch.object(L,'_jobs',{'fixture':job}):
                with self.assertRaises(ValueError):L.handle('bob',folder,{'action':'cancel','job_id':'fixture'})
                self.assertNotIn('cancel',job)
                self.assertTrue(L.handle('alice',folder,{'action':'cancel','job_id':'fixture'})['ok']);self.assertTrue(job['cancel'])

    def test_recovery_refuses_to_overwrite_newer_external_edit(self):
        from ks import event_timeline as T
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'draft_info.json').write_bytes(b'{"id":"old"}')
            original=T.atomic_write
            def crash(path,data):
                original(path,data)
                if path.name=='draft_info.json':raise KeyboardInterrupt('interrupted')
            with patch.object(T,'atomic_write',side_effect=crash):
                with self.assertRaises(KeyboardInterrupt):T.replace_files(root,{'draft_info.json':b'{"id":"new"}'})
            (root/'draft_info.json').write_bytes(b'{"id":"external"}')
            with self.assertRaises(ValueError):T.recover_pending(root)
            self.assertEqual((root/'draft_info.json').read_bytes(),b'{"id":"external"}')

class TimelinePreflightTests(unittest.TestCase):
    def test_install_review_keeps_alignment_and_skipped_stock_visible(self):
        from ks.cli_lab_commit import review_notes
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder);(p/'alignment_report.json').write_text(json.dumps({'warnings':[{'reason':'uncertain'}]}))
            (p/'draft_info.json').write_text(json.dumps({'duration':10000000,'tracks':[]}))
            (p/'stock_report.json').write_text(json.dumps([{'kind':'broll','state':'skipped'},{'kind':'music','state':'skipped'}]))
            notes=review_notes(p)
            self.assertIn('ไม่ตัดคำ',notes);self.assertIn('ข้าม 1 ช่วง',notes);self.assertIn('ยังไม่มีเพลง',notes)

    def test_project_root_resolves_active_timeline_and_install_refuses_mirror(self):
        from ks.ce_project import active_project_path
        from ks.cli_lab_commit import preview
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);active=root/'Timelines'/'active';active.mkdir(parents=True)
            for p in (root/'draft_info.json',active/'draft_info.json'):p.write_text(json.dumps({'id':'active'}))
            self.assertEqual(active_project_path(root),str(active.resolve()))
            with self.assertRaisesRegex(ValueError,'CapCut ใช้จริง'):preview('alice',root,root/'result')
            (active/'draft_info.json').write_text(json.dumps({'id':'different'}))
            with self.assertRaisesRegex(ValueError,'ไม่ตรง'):active_project_path(root)

    def test_native_background_requires_enable_flag_and_shared_style(self):
        from ks.cli_lab_story import native_text_style
        draft={'materials':{'texts':[{'id':'caption','check_flag':7,'content':json.dumps({'text':'คำพูด','styles':[{'size':10}]})},{'id':'super','check_flag':7,'content':json.dumps({'text':'เน้น','styles':[{'size':10}]})}]},'tracks':[{'type':'text','segments':[{'material_id':'caption'}]},{'type':'text','name':'ช่วยด้วยจ้า · Super','segments':[{'material_id':'super','target_timerange':{'start':0,'duration':3000000}}]}]}
        from unittest.mock import patch
        with patch('ks.core_engine.load_config',return_value={'bg':True,'bg_color':'#123456','super_bg':True,'super_bg_color':'#123456'}):native_text_style(draft)
        for m in draft['materials']['texts']:
            self.assertTrue(m['check_flag']&16);self.assertEqual(m['background_style'],1);self.assertEqual(m['background_fill'],'#123456')
            self.assertFalse(json.loads(m['content'])['styles'][0].get('bold',False))

    def test_sequential_sources_on_two_tracks_are_both_used_without_changing_input(self):
        from ks.cli_lab_story import normalize_sources,source_windows,preflight
        segment=lambda key,start:{'id':key,'material_id':key,'volume':1,'target_timerange':{'start':start,'duration':1000000}}
        draft={'materials':{'videos':[{'id':'a','path':'/first.mp4'},{'id':'b','path':'/second.mp4'}]},'tracks':[{'id':'first','type':'video','segments':[segment('a',0)]},{'id':'second','type':'video','segments':[segment('b',1000000)]}]}
        result=normalize_sources(draft);preflight(result)
        self.assertEqual(len(draft['tracks']),2);self.assertEqual(len(result['tracks']),1)
        self.assertEqual({w['source'] for w in source_windows(result)},{'/first.mp4','/second.mp4'})

    def test_overlapping_audible_source_layers_are_not_silently_ignored(self):
        from ks.cli_lab_story import preflight
        draft={'materials':{},'tracks':[{'type':'video','segments':[]},{'type':'video','segments':[{'volume':1,'target_timerange':{'start':0,'duration':1000000}}]}]}
        with self.assertRaisesRegex(ValueError,'หลายแทร็ก'):preflight(draft)
