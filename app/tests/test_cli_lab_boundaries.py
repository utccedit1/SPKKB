import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from ks import cli_lab as L


class BoundaryReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        texts = ['First point', 'Second point', 'Third point', 'Final point']
        draft = {'duration': 12000000, 'materials': {'texts': []}, 'tracks': [{'id':'caption', 'type':'text', 'segments':[]}]}
        for i, text in enumerate(texts):
            draft['materials']['texts'].append({'id':str(i), 'type':'subtitle', 'content':json.dumps({'text':text,'styles':[]})})
            draft['tracks'][0]['segments'].append({'id':'s'+str(i),'material_id':str(i),'target_timerange':{'start':i*3000000,'duration':3000000}})
        self.file=self.root/'draft_info.json'; self.file.write_text(json.dumps(draft))
        path,digest,_=L.snapshot(self.root)
        self.token='boundarytest'
        self.plan={'owner':'owner','project':str(path),'digest':digest,'created':time.time(),'mode':'story',
                   'editorial_goal':'highlight','min_seconds':6,'max_seconds':12,
                   'cuts':[{'first_id':0,'last_id':0,'role':'hook','start':0,'end':3,'text':texts[0]},
                           {'first_id':2,'last_id':2,'role':'conclusion','start':6,'end':9,'text':texts[2]}],
                   'duration':6,'hook':'Headline','cta':'Follow','reason':'test','supers':['Third point'],
                   'stock_requests':[{'kind':'broll','query':'office desk','start':3.5,'caption_text':'Third point'}]}
        L._plans[self.token]=self.plan
        self.addCleanup(lambda:L._plans.pop(self.token,None))
        self.save=patch.object(L.job_store,'save');self.save.start();self.addCleanup(self.save.stop)

    def call(self,action,**kwargs):
        return L.handle('owner',self.root,dict(action=action,plan_id=self.token,**kwargs))

    def test_review_and_update_new_plan_without_writing_draft(self):
        before=self.file.read_bytes()
        review=self.call('review_boundaries')
        self.assertEqual([c['id'] for c in review['cuts'][0]['captions']],[0,1,2,3])
        result=self.call('update_boundaries',cuts=[{'first_id':0,'last_id':1},{'first_id':3,'last_id':3}])
        self.assertNotEqual(result['plan_id'],self.token)
        self.assertEqual(result['duration'],9)
        self.assertEqual(result['cuts'][1]['text'],'Final point')
        self.assertEqual(result['supers'],[])
        self.assertEqual(result['stock_requests'],[])
        self.assertTrue(result['boundary_reviewed'])
        self.assertTrue(any('ข้อความเปิด' in warning for warning in result['warnings']))
        self.assertEqual(self.file.read_bytes(),before)
        self.assertEqual(L._plans[self.token]['duration'],6)
        L._plans.pop(result['plan_id'],None)

    def test_changed_boundaries_discard_old_ai_narrative_evidence(self):
        evidence={'payoff':{'passage':2,'quote':'Third point','resolves':'test'}}
        self.plan['narrative_review']=evidence
        result=self.call('update_boundaries',cuts=[{'first_id':0,'last_id':1},{'first_id':3,'last_id':3}])
        self.addCleanup(lambda:L._plans.pop(result['plan_id'],None))
        self.assertNotIn('narrative_review',result)
        self.assertNotIn('narrative_review',L._plans[result['plan_id']])
        self.assertTrue(result['boundary_reviewed'])
        self.assertEqual(self.plan['narrative_review'],evidence)

    def test_unchanged_boundaries_retain_grounded_narrative_evidence(self):
        self.plan['narrative_review']={'payoff':{'passage':2,'quote':'Third point','resolves':'test'}}
        result=self.call('update_boundaries',cuts=[{'first_id':0,'last_id':0},{'first_id':2,'last_id':2}])
        self.addCleanup(lambda:L._plans.pop(result['plan_id'],None))
        self.assertEqual(result['narrative_review'],self.plan['narrative_review'])

    def test_wrong_owner_expired_and_changed_source_are_rejected(self):
        with self.assertRaises(ValueError): L.handle('other',self.root,dict(action='review_boundaries',plan_id=self.token))
        self.plan['created']=time.time()-3601
        with self.assertRaises(ValueError): self.call('review_boundaries')
        self.plan['created']=time.time();self.file.write_text('{}')
        with self.assertRaises(ValueError): self.call('review_boundaries')

    def test_non_highlight_unsorted_or_overlapping_captions_cannot_be_reviewed(self):
        self.plan['editorial_goal']='story'
        draft=json.loads(self.file.read_text());draft['tracks'][0]['segments'].reverse()
        self.file.write_text(json.dumps(draft));self.plan['digest']=L.snapshot(self.root)[1]
        with self.assertRaisesRegex(ValueError,'ลำดับ|ซ้อน'):self.call('review_boundaries')

    def test_invalid_ids_overlap_and_duration_are_rejected(self):
        for cuts in ([{'first_id':True,'last_id':0},{'first_id':2,'last_id':2}],
                     [{'first_id':0,'last_id':2},{'first_id':2,'last_id':3}],
                     [{'first_id':0,'last_id':0},{'first_id':1,'last_id':1}]):
            if cuts[-1]['first_id']==1: self.plan['min_seconds']=7
            with self.subTest(cuts=cuts),self.assertRaises(ValueError): self.call('update_boundaries',cuts=cuts)

    def test_manual_edit_rejects_boundaries_outside_presented_neighborhood(self):
        draft=json.loads(self.file.read_text())
        draft['duration']=33000000
        for i in range(4,11):
            draft['materials']['texts'].append({'id':str(i),'type':'subtitle','content':json.dumps({'text':'Point '+str(i),'styles':[]})})
            draft['tracks'][0]['segments'].append({'id':'s'+str(i),'material_id':str(i),'target_timerange':{'start':i*3000000,'duration':3000000}})
        self.file.write_text(json.dumps(draft));self.plan['digest']=L.snapshot(self.root)[1]
        with self.assertRaisesRegex(ValueError,'ขอบ|รอยต่อ'):
            self.call('update_boundaries',cuts=[{'first_id':0,'last_id':0},{'first_id':8,'last_id':8}])

    def test_rejects_source_changed_before_commit(self):
        original=L.snapshot; calls=[0]
        def snapshot(project):
            calls[0]+=1
            if calls[0]==2: self.file.write_text('{}')
            return original(project)
        with patch.object(L, 'snapshot', side_effect=snapshot), self.assertRaisesRegex(ValueError, 'เปลี่ยน'):
            self.call('update_boundaries', cuts=[{'first_id':0,'last_id':1}, {'first_id':3,'last_id':3}])

    def test_unchanged_boundaries_keep_existing_stock(self):
        self.plan['warnings']=['กรุณาตรวจและบันทึกรอยต่อทุกช่วงก่อนสร้างคลิป AI อาจเลือกช่วงที่ขาดบริบท']
        result=self.call('update_boundaries',cuts=[{'first_id':0,'last_id':0},{'first_id':2,'last_id':2}])
        self.assertEqual(result['stock_requests'],self.plan['stock_requests'])
        self.assertFalse(result.get('warnings'))
        L._plans.pop(result['plan_id'],None)

    def test_older_highlight_plan_without_review_cannot_be_applied(self):
        self.plan.pop('requires_boundary_review',None)
        with self.assertRaisesRegex(ValueError,'ตรวจ|รอยต่อ'):
            self.call('apply')

    def test_update_does_not_extend_original_expiry(self):
        self.plan['created']=time.time()-300
        result=self.call('update_boundaries',cuts=[{'first_id':0,'last_id':1},{'first_id':3,'last_id':3}])
        self.assertEqual(L._plans[result['plan_id']]['created'],self.plan['created'])
        L._plans.pop(result['plan_id'],None)

    def test_rejects_legacy_plan_without_original_bounds(self):
        del self.plan['min_seconds']
        with self.assertRaises(ValueError): self.call('update_boundaries',cuts=[{'first_id':0,'last_id':0},{'first_id':2,'last_id':2}])

    def test_ai_review_reuses_saved_cuts_without_replanning_or_extending_expiry(self):
        reply={'verdicts':[{'candidate':1,'coherent':True,'evidence':['First point','Third point'],'narrative':{'opening':{'passage':1,'quote':'First point','claim':'Opening claim'},'development':[],'payoff':{'passage':2,'quote':'Third point','resolves':'Resolved claim'},'starts_complete':True,'ends_complete':True,'no_missing_context':True,'no_unanswered_promises':True}}],'best':1}
        self.plan.update(editing_finish='story',editing_backend='gemini',requires_boundary_review=True)
        before=self.file.read_bytes()
        with patch.object(L.E,'provider_config',return_value=({'ai_backend':'gemini','gemini_api_key':'fixture'},'Gemini')),patch('ks.cli_lab_webhook.request',return_value=json.dumps(reply)) as ask:
            result=self.call('review_story')
        self.addCleanup(lambda:L._plans.pop(result['plan_id'],None))
        self.assertFalse(result['requires_boundary_review']);self.assertTrue(result['boundary_reviewed'])
        self.assertNotEqual(result['plan_id'],self.token)
        self.assertEqual(result['cuts'],self.plan['cuts'])
        self.assertEqual(L._plans[result['plan_id']]['created'],self.plan['created'])
        self.assertTrue(self.plan['requires_boundary_review'])
        self.assertEqual(self.file.read_bytes(),before)
        self.assertEqual(ask.call_count,1)
        self.assertTrue(ask.call_args.kwargs.get('retry_unavailable'))
        self.assertIn('narrative_review',result)

    def test_failed_ai_review_preserves_original_plan_and_guard(self):
        self.plan.update(editing_finish='story',requires_boundary_review=True)
        with patch.object(L.E,'provider_config',return_value=({'ai_backend':'gemini','gemini_api_key':'fixture'},'Gemini')),patch('ks.cli_lab_webhook.request',side_effect=RuntimeError('service unavailable')):
            with self.assertRaises(RuntimeError):self.call('review_story')
        self.assertTrue(L._plans[self.token]['requires_boundary_review'])

    def test_ai_review_rejects_other_owner_and_expired_plan_before_network(self):
        with patch('ks.cli_lab_webhook.request') as ask:
            with self.assertRaisesRegex(ValueError,'แผน|โปรเจกต์'):L.handle('other',self.root,dict(action='review_story',plan_id=self.token))
            self.plan['created']=time.time()-3601
            with self.assertRaisesRegex(ValueError,'แผน'):self.call('review_story')
        ask.assert_not_called()
