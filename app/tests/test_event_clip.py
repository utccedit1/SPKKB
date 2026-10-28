import json
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from ks import event_clip as E


class EventClipTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.proj = pathlib.Path(self.tmp.name) / 'source'
        self.proj.mkdir()
        self.draft = {'id': 'old', 'duration': 12000000, 'materials': {'texts': []}, 'tracks': []}
        subs = []
        for i in range(4):
            self.draft['materials']['texts'].append({'id': str(i), 'content': json.dumps({'text': 'ประเด็น ' + str(i)})})
            subs.append({'id': 's'+str(i), 'material_id': str(i), 'target_timerange': {'start': i*3000000, 'duration': 3000000}})
        self.draft['tracks'] = [{'type': 'video', 'segments': [{'id': 'v', 'source_timerange': {'start': 2000000, 'duration': 12000000}, 'target_timerange': {'start': 0, 'duration': 12000000}, 'speed': 1}]},
                                {'type': 'audio', 'segments': [{'id': 'a', 'source_timerange': {'start': 0, 'duration': 12000000}, 'target_timerange': {'start': 0, 'duration': 12000000}}]},
                                {'type': 'text', 'segments': subs}]
        self.write()
    def write(self):
        (self.proj/'draft_info.json').write_text(json.dumps(self.draft))
    def test_copy_cut_all_tracks_and_source_unchanged(self):
        before=(self.proj/'draft_info.json').read_bytes()
        digest=E.transcript(str(self.proj))[2]
        result=E.apply_plan(str(self.proj), {'source_hash':digest, 'segments':[[3,6],[9,12]]})
        out=json.loads((pathlib.Path(result['project'])/'draft_info.json').read_text())
        self.assertEqual(out['duration'],6000000)
        self.assertNotEqual(out['id'],'old')
        self.assertEqual([s['target_timerange']['start'] for s in out['tracks'][2]['segments']],[0,3000000])
        self.assertEqual(out['tracks'][0]['segments'][0]['source_timerange']['start'],5000000)
        self.assertEqual(len(out['tracks'][1]['segments']),2)
        self.assertEqual(before,(self.proj/'draft_info.json').read_bytes())
    def test_stale_plan(self):
        with self.assertRaises(ValueError): E.apply_plan(str(self.proj),{'source_hash':'stale','segments':[[0,3]]})
    def test_speaker_filter_and_budget(self):
        with patch.object(E,'ask',return_value=[{'ids':[0,1],'score':9,'reason':'hook'}]):
            result=E.make_plan(str(self.proj),{'speaker':'เอ','speaker_ranges':[{'name':'เอ','start':0,'end':6}], 'target_sec':6})
        self.assertEqual(result['segments'],[[0,6]])
        with patch.object(E,'ask',return_value=[{'ids':[2],'score':9}]):
            with self.assertRaises(ValueError): E.make_plan(str(self.proj),{'speaker':'เอ','speaker_ranges':[{'name':'เอ','start':0,'end':6}], 'target_sec':6})
    def test_narrative_reads_all_and_keeps_complete_spans(self):
        responses=[[{'summary':'ภาพรวม','spans':[{'first_id':0,'last_id':1,'reason':'เปิดเรื่อง','role':'hook'}, {'first_id':2,'last_id':3,'reason':'สรุป','role':'ending'}]}], [{'summary':'เรื่องเดียวกัน','clip_ids':[0,1],'join_review':'จบความคิด'}]]
        responses.insert(1,[{'summary':'แก่น','clip_ids':[0,1]}])
        with patch.object(E,'ask',side_effect=responses) as ask:
            result=E.make_plan(str(self.proj),{'mode':'narrative','target_sec':12,'min_sec':10})
        self.assertEqual(result['duration'],12)
        self.assertEqual(result['coverage']['captions'],4)
        self.assertEqual(result['segments'],[[0,6],[6,12]])
        self.assertEqual(ask.call_count,3)

    def test_narrative_rejects_short_or_overlapping_global_plan(self):
        response=[{'summary':'ภาพรวม','spans':[{'first_id':0,'last_id':1}, {'first_id':1,'last_id':3}]}]
        with patch.object(E,'ask',side_effect=[response,[{'clip_ids':[0,1]}]]+[[{'clip_ids':[0,1]}]]*3):
            with self.assertRaises(ValueError):
                E.make_plan(str(self.proj),{'mode':'narrative','target_sec':12,'min_sec':10})
        with patch.object(E,'ask',side_effect=[response,[{'clip_ids':[0]}]]+[[{'clip_ids':[0]}]]*3):
            with self.assertRaises(ValueError):
                E.make_plan(str(self.proj),{'mode':'narrative','target_sec':12,'min_sec':10})

    def test_narrative_trim_cannot_escape_candidate_or_budget(self):
        proposals=[{'summary':'ภาพรวม','spans':[{'first_id':0,'last_id':3}]}]
        with patch.object(E,'ask',side_effect=[proposals,[{'clip_ids':[0]}],[{'summary':'สรุป','cuts':[{'clip_id':0,'first_id':0,'last_id':3}]}]]):
            plan=E.make_plan(str(self.proj),{'mode':'narrative','target_sec':12,'min_sec':10})
        self.assertEqual(plan['duration'],12)
        with patch.object(E,'ask',side_effect=[proposals,[{'clip_ids':[0]}]]+[[{'cuts':[{'clip_id':0,'first_id':0,'last_id':4}]}]]*3):
            with self.assertRaises(ValueError):
                E.make_plan(str(self.proj),{'mode':'narrative','target_sec':12,'min_sec':10})

    def test_unknown_speaker_and_invalid_range(self):
        with self.assertRaises(ValueError): E.make_plan(str(self.proj),{'speaker':'unknown'})
        with self.assertRaises(ValueError): E.apply_plan(str(self.proj),{'source_hash':E.transcript(str(self.proj))[2],'segments':[[0,20]]})
    def test_analyze_ignores_model_times_and_ids(self):
        with patch.object(E,'ask',return_value=[{'first_id':999,'last_id':-4,'start':500,'summary':'ทักษะ','keywords':['อาชีพ']}]):
            result=E.analyze(str(self.proj),{})
        self.assertEqual((result['topics'][0]['start'],result['topics'][0]['end']),(0,12))
        self.assertEqual(result['topics'][0]['first_id'],0)

    def test_windows_respect_speaker_and_time(self):
        rows=[{'id':0,'start':0,'end':20,'text':'a','speaker':'เอ'},
              {'id':1,'start':20,'end':40,'text':'b','speaker':'บี'},
              {'id':2,'start':40,'end':110,'text':'c','speaker':'บี'}]
        batches=list(E.topic_windows(rows,max_seconds=90))
        self.assertEqual([[r['id'] for r in b] for b in batches],[[0],[1,2]])

    def test_analysis_retries_missing_summary(self):
        with patch.object(E,'ask',side_effect=[[{'first_id':0}], [{'summary':'สรุป','keywords':[]} ]]) as ask:
            result=E.analyze(str(self.proj),{})
        self.assertEqual(ask.call_count,2)
        self.assertEqual(result['topics'][0]['summary'],'สรุป')

    def test_analysis_missing_summary_fails(self):
        with patch.object(E,'ask',return_value=[{'first_id':0}]) as ask:
            with self.assertRaises(ValueError): E.analyze(str(self.proj),{})
        self.assertEqual(ask.call_count,3)

    def test_plan_accepts_numeric_strings(self):
        with patch.object(E,'ask',return_value=[{'ids':['0','1'],'score':8}]):
            result=E.make_plan(str(self.proj),{'target_sec':6})
        self.assertEqual(result['segments'],[[0,6]])

    def test_markdown_literal_newlines(self):
        raw = '```json\\n[{"summary":"สรุป","keywords":["ทักษะ"]}]\\n```'
        self.assertEqual(E.parse_event_response(raw)[0]['summary'],'สรุป')

    def test_nested_and_html_response(self):
        raw=json.dumps({'output': '<pre><code>[{&quot;summary&quot;:&quot;ok&quot;,&quot;keywords&quot;:[]}]</code></pre>'})
        self.assertEqual(E.parse_event_response(raw)[0]['summary'],'ok')
        raw=json.dumps(json.dumps([{'summary':'double encoded','keywords':[]}]))
        self.assertEqual(E.parse_event_response(raw)[0]['summary'],'double encoded')

    def test_non_json_response_does_not_fabricate_summary(self):
        self.assertIsNone(E.parse_event_response('ระบบไม่พร้อมใช้งาน กรุณาลองใหม่'))

    def test_analysis_retries_response_parse_error(self):
        with patch.object(E,'ask',side_effect=[E.AIResponseError('bad json'),[{'summary':'สรุป','keywords':[]} ]]) as ask:
            result=E.analyze(str(self.proj),{})
        self.assertEqual(ask.call_count,2)
        self.assertEqual(result['topics'][0]['summary'],'สรุป')

    def test_names_must_have_verbatim_evidence(self):
        mat=self.draft['materials']['texts'][0]
        mat['content']=json.dumps({'text':'ช่วงต่อไปขอเชิญคุณสมชายขึ้นเวที'})
        self.write()
        response=[{'summary':'เชิญผู้พูด','keywords':[], 'mentions':[
            {'name':'สมชาย','quote':'ขอเชิญคุณสมชายขึ้นเวที'},
            {'name':'สมศรี','quote':'ขอเชิญคุณสมศรีขึ้นเวที'}]}]
        with patch.object(E,'ask',return_value=response):
            result=E.analyze(str(self.proj),{})
        self.assertEqual([m['name'] for m in result['speaker_mentions']],['สมชาย'])
        self.assertEqual(result['speaker_mentions'][0]['start'],0)
        self.assertEqual(result['topics'][0]['speakers'],[])

    def test_plan_only_selected_time_window(self):
        with patch.object(E,'ask',return_value=[{'ids':[2],'score':8}]):
            plan=E.make_plan(str(self.proj),{'range_start':6,'range_end':12,'target_sec':6})
        self.assertEqual(plan['segments'],[[6,9]])
        with patch.object(E,'ask',return_value=[{'ids':[0],'score':8}]):
            with self.assertRaises(ValueError):
                E.make_plan(str(self.proj),{'range_start':6,'range_end':12,'target_sec':6})

    def test_capcut_registration_is_backed_up_and_idempotent(self):
        root=pathlib.Path(self.tmp.name)/'root_meta_info.json'
        source={'all_draft_store':[{'draft_id':'old','draft_fold_path':str(self.proj)}], 'draft_ids':['old']}
        root.write_text(json.dumps(source))
        dest=pathlib.Path(self.tmp.name)/'copy';dest.mkdir()
        meta={'draft_id':'new','draft_name':'copy','draft_fold_path':str(dest), 'draft_root_path':self.tmp.name,'tm_duration':6000000,'_event_source':str(self.proj)}
        (dest/'draft_meta_info.json').write_text(json.dumps(meta))
        with patch.object(E,'sys_platform_is_mac',return_value=False):
            self.assertTrue(E.register_project(str(dest))['registered'])
            E.register_project(str(dest))
        updated=json.loads(root.read_text())
        self.assertEqual(len(updated['all_draft_store']),2)
        self.assertEqual(updated['draft_ids'],['old','new'])
        backups=list(root.parent.glob('root_meta_info.json.event_backup_*'))
        self.assertEqual(len(backups),1)
        self.assertEqual(json.loads(backups[0].read_text()),source)

    def test_inplace_cut_and_restore_exact_bytes(self):
        from ks import event_timeline as T
        (self.proj/'draft_content.json').write_bytes((self.proj/'draft_info.json').read_bytes())
        (self.proj/'draft_meta_info.json').write_text(json.dumps({'draft_id':'old','tm_duration':12000000}))
        (self.proj/'draft_info_original.json').write_text('cached captions')
        before={name:(self.proj/name).read_bytes() if (self.proj/name).exists() else None for name in T.FILES}
        cfg={'source_hash':E.transcript(str(self.proj))[2],'segments':[[3,6],[9,12]]}
        with patch.object(T,'ensure_closed'):
            result=T.apply(str(self.proj),cfg)
            cut=json.loads((self.proj/'draft_info.json').read_text())
            self.assertEqual(cut['id'],'old')
            self.assertEqual(cut['duration'],6000000)
            self.assertEqual((self.proj/'draft_content.json').read_bytes(),(self.proj/'draft_info.json').read_bytes())
            self.assertFalse((self.proj/'draft_info_original.json').exists())
            T.restore(str(self.proj),{'backup_name':result['backup_name']})
        after={name:(self.proj/name).read_bytes() if (self.proj/name).exists() else None for name in T.FILES}
        self.assertEqual(after,before)
        self.assertEqual(len(T.list_backups(str(self.proj))['backups']),2)

    def test_inplace_write_failure_rolls_back(self):
        from ks import event_timeline as T
        before=(self.proj/'draft_info.json').read_bytes()
        cfg={'source_hash':E.transcript(str(self.proj))[2],'segments':[[3,6]]}
        original=T.replace_files
        calls=[]
        def fail_once(proj,files):
            calls.append(1)
            if len(calls)==1:
                T.atomic_write(pathlib.Path(proj)/'draft_info.json',files['draft_info.json'])
                raise OSError('simulated disk failure')
            original(proj,files)
        with patch.object(T,'ensure_closed'),patch.object(T,'replace_files',side_effect=fail_once):
            with self.assertRaises(OSError):T.apply(str(self.proj),cfg)
        self.assertEqual((self.proj/'draft_info.json').read_bytes(),before)
        self.assertEqual(len(T.list_backups(str(self.proj))['backups']),1)

    def test_corrupt_backup_does_not_restore(self):
        from ks import event_timeline as T
        backup=T.checkpoint(str(self.proj),'test')
        (backup/'draft_info.json').write_text('corrupted')
        before=(self.proj/'draft_info.json').read_bytes()
        with patch.object(T,'ensure_closed'):
            with self.assertRaises(ValueError):T.restore(str(self.proj),{'backup_name':backup.name})
        self.assertEqual((self.proj/'draft_info.json').read_bytes(),before)

    def test_running_capcut_and_stale_plan_are_blocked(self):
        from ks import event_timeline as T
        with patch.object(E,'sys_platform_is_mac',return_value=True),patch.object(T.subprocess,'run') as run:
            run.return_value.returncode=0
            with self.assertRaises(ValueError):T.apply(str(self.proj),{})
        with patch.object(T,'ensure_closed'):
            with self.assertRaises(ValueError):T.apply(str(self.proj),{'source_hash':'stale','segments':[[0,3]]})
        self.assertFalse((self.proj/T.BACKUPS).exists())

    def test_plan_cannot_apply_to_other_project(self):
        from ks import event_timeline as T
        cfg={'source_project':'/other/project','source_hash':E.transcript(str(self.proj))[2],'segments':[[0,3]]}
        with patch.object(T,'ensure_closed'):
            with self.assertRaises(ValueError):T.apply(str(self.proj),cfg)
        self.assertFalse((self.proj/T.BACKUPS).exists())

    def test_nested_timeline_updates_and_restores_project_main(self):
        from ks import event_timeline as T
        timeline=self.proj/'Timelines'/'old';timeline.mkdir(parents=True)
        original=(self.proj/'draft_info.json').read_bytes()
        (timeline/'draft_info.json').write_bytes(original)
        (self.proj/'draft_meta_info.json').write_text(json.dumps({'draft_id':'old','tm_duration':12000000}))
        before_meta=(self.proj/'draft_meta_info.json').read_bytes()
        with patch.object(T,'ensure_closed'):
            result=T.apply(str(timeline),{'source_hash':E.transcript(str(timeline))[2],'segments':[[3,6]]})
            self.assertEqual((timeline/'draft_info.json').read_bytes(),(self.proj/'draft_info.json').read_bytes())
            self.assertEqual(json.loads((self.proj/'draft_info.json').read_text())['duration'],3000000)
            T.restore(str(timeline),{'backup_name':result['backup_name']})
        self.assertEqual((self.proj/'draft_info.json').read_bytes(),original)
        self.assertEqual((self.proj/'draft_meta_info.json').read_bytes(),before_meta)

if __name__=='__main__': unittest.main()
