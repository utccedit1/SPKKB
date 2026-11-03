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
