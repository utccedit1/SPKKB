import json
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from ks import event_clip as E, event_review as R


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.proj = self.tmp.name
        self.file = pathlib.Path(self.proj)/'draft_info.json'
        self.draft = {'materials': {'texts': [{'id':str(i),'content':json.dumps({'text':f'เนื้อหา {i}'})} for i in range(6)]},
            'tracks': [{'type':'text','segments':[{'material_id':str(i),'target_timerange':{'start':i*3000000,'duration':3000000}} for i in range(6)]}]}
        self.file.write_text(json.dumps(self.draft))
        self.source = R.source(self.proj)
    def cfg(self, cuts):
        return {**self.source,'target_sec':180,'cuts':cuts}
    def test_review_rebuilds_text_and_timing_from_caption_ids(self):
        result=R.review(self.proj,self.cfg([{'first_id':1,'last_id':3,'text':'invented','start':900}]))
        self.assertEqual(result['segments'],[[3,12]])
        self.assertEqual(result['duration'],9)
        self.assertEqual(result['excerpts'][0]['text'],'เนื้อหา 1 เนื้อหา 2 เนื้อหา 3')
    def test_review_rejects_empty_reverse_overlap_and_out_of_range(self):
        for cuts in ([],[{'first_id':3,'last_id':1}],[{'first_id':0,'last_id':9}],
                     [{'first_id':0,'last_id':2},{'first_id':2,'last_id':3}]):
            with self.assertRaises(ValueError):R.review(self.proj,self.cfg(cuts))
    def test_stale_source_prevents_plan_without_ai_call(self):
        self.file.write_text(self.file.read_text()+' ')
        with patch.object(E,'ask') as ask:
            with self.assertRaises(ValueError):E.make_plan(self.proj,{'source_hash':self.source['source_hash']})
            ask.assert_not_called()
        with self.assertRaises(ValueError):R.review(self.proj,self.cfg([{'first_id':0,'last_id':1}]))
    def test_overlapping_speaker_names_are_not_guessed(self):
        with self.assertRaises(ValueError):E.transcript(self.proj,[{'name':'A','start':0,'end':9},{'name':'B','start':6,'end':12}])
    def test_analysis_cache_does_not_call_ai_again_but_invalidates_on_edit(self):
        with patch.object(E,'ask',return_value=[{'summary':'ภาพรวม','keywords':[] }]) as ask:
            E.analyze(self.proj,{})
            result=E.analyze(self.proj,{})
            self.assertTrue(result['cached']);self.assertEqual(ask.call_count,1)
            self.file.write_text(self.file.read_text()+' ')
            E.analyze(self.proj,{})
            self.assertEqual(ask.call_count,2)
    def test_changing_target_reuses_reading_all_source_captions(self):
        proposals=[{'summary':'ภาพรวม','spans':[{'first_id':0,'last_id':5,'role':'ending'}]}]
        outline=[{'clip_ids':[0]}]
        cuts=[{'summary':'ครบ','cuts':[{'clip_id':0,'first_id':0,'last_id':5}]}]
        with patch.object(E,'ask',side_effect=[proposals,outline,cuts,outline,cuts]) as ask:
            first=E.make_plan(self.proj,{'mode':'narrative','target_sec':18})
            second=E.make_plan(self.proj,{'mode':'narrative','target_sec':20})
        self.assertEqual(first['duration'],18)
        self.assertEqual(second['duration'],18)
        self.assertEqual(ask.call_count,5)
