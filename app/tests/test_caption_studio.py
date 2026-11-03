import copy,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from ks import caption_studio as S
from test_caption_presets import draft


class StudioTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.project=self.root/'project';self.project.mkdir()
        self.video=self.root/'video.mp4';self.video.write_bytes(b'fixture')
        self.d=draft();self.d['materials']['videos']=[{'id':'v','path':str(self.video),'type':'video'}]
        self.d['tracks'].insert(0,{'type':'video','segments':[{'id':'v1','material_id':'v','speed':2,'source_timerange':{'start':8000000,'duration':8000000},'target_timerange':{'start':0,'duration':4000000}}]})
        self.path=self.project/'draft_info.json';self.path.write_text(json.dumps(self.d));self.raw=self.path.read_bytes()
        self.env=patch.dict(os.environ,{'KS_JOB_STATE_DIR':str(self.root/'receipts')});self.env.start();self.addCleanup(self.env.stop)
    def test_metadata_returns_speech_cues_and_fingerprint(self):
        m=S.handle('alice','window',self.project,{'action':'metadata'})
        self.assertEqual([c['id'] for c in m['cues']],['one','two'])
        self.assertEqual(len(m['source_hash']),64)
    def test_source_slice_uses_speed_and_rejects_unsupported_nested(self):
        src=S.source_at(self.d,1)
        self.assertEqual(src['offset'],10)
        self.assertEqual(src['speed'],2)
        self.d['materials']['drafts']=[{'id':'nested','draft':draft()}]
        self.d['tracks'][0]['segments'][0]['extra_material_refs']=['nested']
        with self.assertRaises(ValueError):S.source_at(self.d,1)
    def test_asset_token_cannot_cross_workspace_owner_project_or_media_changes(self):
        token=S.register_asset('alice','window',self.project,self.video,S.fingerprint(self.raw))
        self.assertEqual(S.asset('alice','window',self.project,token),self.video)
        for owner,window,project in [('bob','window',self.project),('alice','other',self.project),('alice','window',self.root)]:
            with self.assertRaises(ValueError):S.asset(owner,window,project,token)
        self.video.write_bytes(b'changed')
        with self.assertRaises(ValueError):S.asset('alice','window',self.project,token)
    def test_prepare_copy_keeps_source_and_remembers_result(self):
        with patch.object(S,'output_root',return_value=self.root/'outputs'),patch.object(S,'available_fonts',return_value=[]):
            result=S.handle('alice','window',self.project,{'action':'prepare','source_hash':S.fingerprint(self.raw),'media_hash':S.media_fingerprint(self.d,self.project),'ids':['one'],'settings':{'preset':'rise'}})
        self.assertEqual(self.path.read_bytes(),self.raw)
        out=json.loads((Path(result['destination'])/'draft_info.json').read_bytes())
        self.assertNotEqual(out['tracks'][1]['segments'][0]['material_id'],'m')
        self.assertEqual(out['tracks'][1]['segments'][1]['material_id'],'m')
        self.assertTrue(result['result_id'])
    def test_stale_source_is_rejected_before_creating_output(self):
        with patch.object(S,'output_root',return_value=self.root/'outputs'):
            with self.assertRaises(ValueError):S.handle('alice','window',self.project,{'action':'prepare','source_hash':'stale','ids':['one']})
        self.assertFalse((self.root/'outputs').exists())
    def test_changed_source_media_invalidates_request_even_with_same_draft(self):
        meta=S.handle('alice','window',self.project,{'action':'metadata'})
        self.video.write_bytes(b'changed file')
        with self.assertRaisesRegex(ValueError,'สื่อเปลี่ยน'):
            S.handle('alice','window',self.project,{'action':'prepare','source_hash':meta['source_hash'],'media_hash':meta['media_hash'],'ids':['one']})
    def test_active_preview_blocks_installer_admission(self):
        from ks import job_admission as A
        with patch.object(S,'_active',1):self.assertTrue(A.busy())
    def test_failed_proxy_render_removes_partial_files(self):
        import subprocess
        before=set(Path(S._preview_temp.name).rglob('preview-*'))
        with patch.object(S.subprocess,'run',return_value=subprocess.CompletedProcess([],1)):
            with self.assertRaises(ValueError):S.handle('alice','window',self.project,{'action':'preview','source_hash':S.fingerprint(self.raw),'media_hash':S.media_fingerprint(self.d,self.project),'cue_id':'one'})
        self.assertEqual(set(Path(S._preview_temp.name).rglob('preview-*')),before)
    def test_media_http_range_uses_only_scoped_registered_asset(self):
        from ks.server import Handler
        import io
        self.video.write_bytes(b'0123456789')
        token=S.register_asset('alice','window',self.project,self.video,S.fingerprint(self.raw))
        for requested,code,body in [('bytes=2-5',206,b'2345'),('bytes=-3',206,b'789'),('bytes=99-',416,b''),('bytes=0-1,3-4',416,b'')]:
            h=Handler.__new__(Handler);h.path='/api/caption_studio/media?token='+token
            h.headers={'Range':requested};h.wfile=io.BytesIO();h._studio_workspace='window';h._need_project=lambda:self.project;h._uid=lambda:'alice'
            statuses=[];headers={};h.send_response=statuses.append;h.send_header=lambda k,v:headers.update({k:v});h.end_headers=lambda:None
            h._route_get('/api/caption_studio/media')
            self.assertEqual(statuses,[code]);self.assertEqual(h.wfile.getvalue(),body)
            self.assertEqual(int(headers['Content-Length']),len(body))
    def test_all_scope_keeps_user_title_unchanged(self):
        self.d['materials']['texts'].append({'id':'title','type':'text','content':json.dumps({'text':'TITLE','styles':[]})})
        self.d['tracks'].append({'type':'text','name':'My title','segments':[{'id':'title-seg','material_id':'title','target_timerange':{'start':0,'duration':4000000}}]})
        self.path.write_text(json.dumps(self.d));self.raw=self.path.read_bytes()
        with patch.object(S,'output_root',return_value=self.root/'outputs'),patch.object(S,'available_fonts',return_value=[]):
            result=S.handle('alice','window',self.project,{'action':'prepare','scope':'all','source_hash':S.fingerprint(self.raw),'media_hash':S.media_fingerprint(self.d,self.project),'settings':{}})
        out=json.loads((Path(result['destination'])/'draft_info.json').read_bytes())
        self.assertEqual(result['count'],2);self.assertEqual(out['tracks'][-1],self.d['tracks'][-1])

    def multicam(self):
        child=copy.deepcopy(self.d);child['tracks'][0]['id']='camera-a'
        other=copy.deepcopy(child['tracks'][0]);other['id']='camera-b';other['segments'][0]['source_timerange']['start']=30000000
        child['tracks']=[child['tracks'][0],other];child['materials']['texts']=[]
        self.d['materials']['drafts']=[{'id':'nested','draft':child}]
        self.d['materials']['videos']=[{'id':'multi','multi_camera_info':{'cur_camera_track_id':'camera-b','audio_open_track_id_list':['camera-b']}}]
        seg=self.d['tracks'][0]['segments'][0];seg.update(material_id='multi',extra_material_refs=['nested'],speed=1,source_timerange={'start':0,'duration':4000000})
        return child

    def test_multicam_preview_uses_selected_camera_and_nested_time(self):
        self.multicam();src=S.source_at(self.d,1)
        self.assertEqual(src['offset'],32);self.assertEqual(src['speed'],2)
        self.assertEqual(src['remaining'],3)

    def test_prepare_root_captions_preserves_multicam(self):
        self.multicam();self.path.write_text(json.dumps(self.d));self.raw=self.path.read_bytes()
        with patch.object(S,'output_root',return_value=self.root/'outputs'),patch.object(S,'available_fonts',return_value=[]):
            r=S.handle('alice','window',self.project,{'action':'prepare','scope':'all','source_hash':S.fingerprint(self.raw),'media_hash':S.media_fingerprint(self.d,self.project),'settings':{}})
        out=json.loads((Path(r['destination'])/'draft_info.json').read_text())
        self.assertEqual(out['materials']['drafts'],self.d['materials']['drafts'])

    def test_multicam_parent_speed_and_inner_cut_limit(self):
        child=self.multicam()
        self.d['tracks'][0]['segments'][0]['speed']=2
        child['tracks'][1]['segments'][0]['target_timerange']['duration']=3000000
        src=S.source_at(self.d,1)
        self.assertEqual(src['offset'],34);self.assertEqual(src['speed'],4)
        self.assertEqual(src['remaining'],.5)

    def test_prepare_rejects_nested_speech_captions(self):
        child=self.multicam();speech=draft()
        child['tracks']+=speech['tracks'];child['materials']['texts']=speech['materials']['texts']
        self.path.write_text(json.dumps(self.d));self.raw=self.path.read_bytes()
        with self.assertRaisesRegex(ValueError,'ซับใน compound'):
            S.handle('alice','window',self.project,{'action':'prepare','scope':'all','source_hash':S.fingerprint(self.raw),'media_hash':S.media_fingerprint(self.d,self.project),'settings':{}})
