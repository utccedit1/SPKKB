"""Behavioral regressions for the whole-system readiness audit."""
import copy
import hashlib
import json
import os
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch
from ks import core_engine as CE, event_timeline as T, apply_guard as G
from ks import ce_ai as AI, cli_lab as L, cli_lab_commit as C, cli_results as R, job_store as J
from ks import storage_manager as M, proofread as P, caption_resegment as S


class ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.project=self.root/'Project';self.target=self.project/'Timelines/main'
        self.target.mkdir(parents=True);self.output=self.root/'output';self.output.mkdir()
        self.media=self.root/'media.wav';self.media.write_bytes(b'fixture')
        self.draft={'id':'main','duration':4000000,'materials':{'texts':[{'id':'text','type':'subtitle','content':json.dumps({'text':'จริงจริง','styles':[]})}],'audios':[{'id':'audio','path':str(self.media)}]},'tracks':[{'type':'text','segments':[{'id':'seg','material_id':'text','target_timerange':{'start':0,'duration':4000000}}]}]}
        self.raw=json.dumps(self.draft).encode()
        for base in (self.target,self.project):
            for name in ('draft_info.json','draft_content.json','draft_info.json.bak','template-2.tmp'):(base/name).write_bytes(self.raw)
        edited=copy.deepcopy(self.draft);edited['duration']=2000000;edited['tracks'][0]['segments'][0]['target_timerange']['duration']=2000000
        (self.output/'draft_info.json').write_text(json.dumps(edited))
        for mock in (patch.dict(os.environ,{'KS_JOB_STATE_DIR':str(self.root/'receipts')}),patch.object(T,'ensure_closed'),patch.object(M,'_trash_root',side_effect=lambda root:root/'.test-trash')):
            mock.start();self.addCleanup(mock.stop)

    def assert_mirrors(self):
        live=(self.target/'draft_info.json').read_bytes()
        for base in (self.target,self.project):
            for name in ('draft_info.json','draft_content.json','draft_info.json.bak','template-2.tmp'):
                self.assertEqual((base/name).read_bytes(),live,(str(base),name))
        self.assertNotEqual(live,self.raw)

    def test_caption_commit_updates_all_mirrors_and_preserves_baseline(self):
        prepared=G.prepare(str(self.target),dict(source_hash=hashlib.sha1(self.raw).hexdigest(),state_hash=hashlib.sha1(self.raw).hexdigest()))
        edited=copy.deepcopy(self.draft);edited['test_marker']='new'
        backup=G.commit(str(self.target),prepared,edited)
        self.assert_mirrors()
        self.assertEqual((self.target/'draft_info_original.json').read_bytes(),self.raw)
        T.replace_files(str(self.target),T.read_checkpoint(str(self.target),backup))
        self.assertEqual((self.project/'template-2.tmp').read_bytes(),self.raw)

    def test_caption_partial_mirror_write_rolls_back_every_file(self):
        prepared=G.prepare(str(self.target),dict(source_hash=hashlib.sha1(self.raw).hexdigest(),state_hash=hashlib.sha1(self.raw).hexdigest()))
        edited=copy.deepcopy(self.draft);edited['test_marker']='new'
        write=T.atomic_write;failed=False
        def fail(path,data):
            nonlocal failed
            if path == self.target/'template-2.tmp' and not failed:
                failed=True;raise OSError('fixture disk failure')
            return write(path,data)
        with patch.object(T,'atomic_write',side_effect=fail),self.assertRaises(OSError):
            G.commit(str(self.target),prepared,edited)
        for base in (self.project,self.target):
            for name in ('draft_info.json','draft_content.json','draft_info.json.bak','template-2.tmp'):
                self.assertEqual((base/name).read_bytes(),self.raw)
        self.assertFalse((self.target/T.JOURNAL).exists())

    def test_event_cut_updates_all_mirrors(self):
        T.apply(str(self.target),dict(source_hash=hashlib.sha256(self.raw).hexdigest(),segments=[[0,2]]))
        self.assert_mirrors()
        self.assertEqual(json.loads((self.project/'template-2.tmp').read_bytes())['duration'],2000000)

    def test_proofread_updates_all_mirrors(self):
        source=P.source(str(self.target))
        P.apply(str(self.target),dict(source,edits=[dict(index=0,original='จริงจริง',suggested='จริง ๆ')]))
        self.assert_mirrors()

    def test_resegment_updates_all_mirrors_without_ai(self):
        with patch.object(S,'ask') as ask:S.run(str(self.target),dict(max_words=20))
        ask.assert_not_called();self.assert_mirrors()

    def test_bad_mirror_rejected_before_any_timeline_write(self):
        old={n:(T.target_path(str(self.target),n).read_bytes() if T.target_path(str(self.target),n) and T.target_path(str(self.target),n).is_file() else None) for n in T.FILES}
        old['template-2.tmp']=b'{"id":"other","tracks":[]}'
        with self.assertRaises(ValueError):T.mirror_updates(old,self.raw)
        self.assertEqual((self.target/'draft_info.json').read_bytes(),self.raw)

    def test_audio_auto_timeout_never_resends(self):
        with patch.object(AI.urllib.request,'urlopen',side_effect=socket.timeout('fixture')) as call:
            with self.assertRaises(RuntimeError):AI.call_webhook('fixture',conf={'webhook_url':'https://example.invalid/hook'},audio_b64='AA==',send_mode='auto',max_retries=1)
        self.assertEqual(call.call_count,1)

    def test_audio_auto_ack_never_resends(self):
        from io import BytesIO
        with patch.object(AI.urllib.request,'urlopen',return_value=BytesIO(b'{"accepted":true}')) as call:
            with self.assertRaises(AI.WebhookAckError):AI.call_webhook('fixture',conf={'webhook_url':'https://example.invalid/hook'},audio_b64='AA==',send_mode='auto',max_retries=1)
        self.assertEqual(call.call_count,1)

    def remember(self):
        return R.remember('alice',self.target,self.output,hashlib.sha256(self.raw).hexdigest(),'apply')

    def test_completed_result_survives_restart_and_is_owner_project_scoped(self):
        token=self.remember();C._tickets.clear()
        with patch.object(J,'INSTANCE','new-process'):
            self.assertEqual(R.listing('alice',self.target)['results'][0]['result_id'],token)
            self.assertEqual(R.listing('bob',self.target)['results'],[])
            self.assertEqual(R.listing('alice',self.project)['results'],[])
            preview=R.review('alice',self.target,token)
        result=C.commit('alice',self.target,preview['install_id'])
        self.assertTrue(result['ok']);self.assertEqual(R.listing('alice',self.target)['results'],[])

    def test_completed_result_rejects_source_output_and_media_changes(self):
        for what in ('source','output','media'):
            with self.subTest(what=what):
                token=self.remember()
                path={'source':self.target/'draft_info.json','output':self.output/'draft_info.json','media':self.media}[what]
                old=path.read_bytes();path.write_bytes(old+b' ')
                with self.assertRaises(ValueError):R.review('alice',self.target,token)
                path.write_bytes(old)

    def test_old_install_receipt_is_adopted_without_refreshing_hash(self):
        preview=C.preview('alice',self.target,self.output)
        (self.target/'draft_info.json').write_bytes(self.raw+b' ')
        row=R.listing('alice',self.target)['results'][0]
        self.assertEqual(row['result_id'],'legacy'+preview['install_id'])
        with self.assertRaises(ValueError):R.review('alice',self.target,row['result_id'])

    def test_missing_and_corrupt_job_are_definitive(self):
        for token in ('gone','broken'):
            if token=='broken':
                path=J._path('alice','cli',token);path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'not json')
            result=L.handle('alice',self.target,dict(action='job_status',job_id=token))
            self.assertEqual(result['code'],'job_not_found');self.assertFalse(result['ok'])

    def test_retention_final_suffix_running_recheck_and_restore(self):
        root=self.root/'builds';root.mkdir()
        for v in range(40,47):(root/f'dist-1.5.{v}-final').mkdir()
        with patch.object(M,'_running_bundles',return_value=set()):
            preview=M.preview('alice',root,[])
        self.assertEqual({r['name'] for r in preview['files']},{'dist-1.5.40-final','dist-1.5.41-final'})
        with patch.object(M,'_running_bundles',return_value={(root/'dist-1.5.40-final/app.app').resolve()}):
            with self.assertRaises(ValueError):M.move('alice',preview['cleanup_id'])
            self.assertTrue((root/'dist-1.5.40-final').exists())
        with patch.object(M,'_running_bundles',return_value=set()):
            M.move('alice',preview['cleanup_id'])
        M.restore('alice',preview['cleanup_id'],root)
        self.assertEqual(len(list(root.glob('dist-*'))),7)
