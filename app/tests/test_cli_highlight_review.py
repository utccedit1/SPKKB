import json
import unittest

from ks.cli_highlight_review import review, parse_review


class HighlightReviewTests(unittest.TestCase):
    def setUp(self):
        self.captions = [dict(id=i, start=i*3, end=(i+1)*3, text='คำพูด '+str(i), sources=['one']) for i in range(9)]
        self.raw = {'cuts':[{'first_id':1,'last_id':2,'role':'hook'}, {'first_id':5,'last_id':6,'role':'conclusion'}],
                    'hook':'Headline', 'cta':'Follow', 'reason':'Example'}

    def test_reviewer_can_extend_nearby_complete_context(self):
        seen=[]
        def ask(prompt):
            seen.append(prompt)
            return {'spans':[{'first_id':0,'last_id':2}, {'first_id':5,'last_id':7}]}
        result=review(self.raw,self.captions,12,20,ask)
        self.assertEqual([(c['first_id'],c['last_id']) for c in result['cuts']],[(0,2),(5,7)])
        self.assertEqual(result['cuts'][0]['role'],'hook')
        self.assertIn('คำพูด 0',seen[0]);self.assertIn('คำพูด 7',seen[0])

    def test_rejects_far_away_or_overlapping_changes(self):
        for cuts in ([{'first_id':1,'last_id':8},{'first_id':5,'last_id':6}],
                     [{'first_id':1,'last_id':5},{'first_id':5,'last_id':6}]):
            with self.subTest(cuts=cuts), self.assertRaises(ValueError):
                review(self.raw,self.captions,12,25,lambda _: {'spans':cuts},margin=2)

    def test_cancellation_propagates(self):
        def ask(_): raise InterruptedError('cancelled')
        with self.assertRaises(InterruptedError):review(self.raw,self.captions,12,20,ask)

    def test_reviewer_cannot_replace_a_passage_with_an_unrelated_nearby_one(self):
        cuts=[{'first_id':3,'last_id':4},{'first_id':5,'last_id':6}]
        with self.assertRaises(ValueError):review(self.raw,self.captions,12,20,lambda _: {'spans':cuts})

    def test_reviewer_cannot_discard_most_of_the_opening_under_cover_of_overlap(self):
        raw={'cuts':[{'first_id':0,'last_id':3,'role':'hook'},{'first_id':6,'last_id':6,'role':'conclusion'}],
             'hook':'Headline','cta':'Follow','reason':'Story'}
        spans=[{'first_id':3,'last_id':3},{'first_id':6,'last_id':6}]
        with self.assertRaises(ValueError):review(raw,self.captions,6,16,lambda _: {'spans':spans})

    def test_parse_skips_explanatory_numeric_arrays_and_finds_review_object(self):
        raw='Current cut [2,3] and nearby [0,6].\n```json\n{"spans":[{"first_id":2,"last_id":3}]}\n```'
        self.assertEqual(parse_review(raw),{'spans':[{'first_id':2,'last_id':3}]})

    def test_parse_wrapped_review_and_rejects_arrays_without_object(self):
        self.assertEqual(parse_review({'output':'{"spans": []}'}),{'spans':[]})
        with self.assertRaises(ValueError):parse_review('current [2,3], no review')

    def test_invalid_boundary_can_be_corrected_once_without_retrying_timeout(self):
        answers=[{'spans':[{'first_id':0,'last_id':8},{'first_id':5,'last_id':6}]},
                 {'spans':[{'first_id':0,'last_id':2},{'first_id':5,'last_id':7}]}]
        prompts=[]
        def ask(prompt):prompts.append(prompt);return answers.pop(0)
        result=review(self.raw,self.captions,12,20,ask)
        self.assertEqual(result['cuts'][0]['first_id'],0)
        self.assertEqual(len(prompts),2)
        self.assertIn('Validation error:',prompts[1])
        self.assertIn('AUTHORITATIVE TIMING CHECK:',prompts[1])
        self.assertIn('leave a safety margin',prompts[0])

    def test_malformed_response_can_be_corrected_once(self):
        answers=['not json', '{"spans":[{"first_id":1,"last_id":2},{"first_id":5,"last_id":6}]}']
        result=review(self.raw,self.captions,12,20,lambda _:answers.pop(0))
        self.assertEqual(result['cuts'][0]['first_id'],1)
        self.assertFalse(answers)

    def test_review_may_remove_unrelated_middle_passage_but_preserves_open_and_close(self):
        raw={'cuts':[{'first_id':0,'last_id':0,'role':'hook'}, {'first_id':3,'last_id':3,'role':'body'}, {'first_id':7,'last_id':7,'role':'conclusion'}],
             'hook':'Headline','cta':'Follow','reason':'A coherent story'}
        response={'spans':[{'cut_index':0,'first_id':0,'last_id':0},{'cut_index':2,'first_id':7,'last_id':7}]}
        result=review(raw,self.captions,6,10,lambda _:response)
        self.assertEqual([c['role'] for c in result['cuts']],['hook','conclusion'])
        self.assertEqual([c['first_id'] for c in result['cuts']],[0,7])

    def test_review_cannot_drop_opening_or_reorder_existing_passages(self):
        raw={'cuts':[{'first_id':0,'last_id':0,'role':'hook'}, {'first_id':3,'last_id':3,'role':'body'}, {'first_id':7,'last_id':7,'role':'conclusion'}],
             'hook':'Headline','cta':'Follow','reason':'A coherent story'}
        for indices in ([1,2],[2,0],[0,0,2],[0,99]):
            spans=[{'cut_index':i,'first_id':raw['cuts'][i]['first_id'] if i<len(raw['cuts']) else 0,'last_id':raw['cuts'][i]['last_id'] if i<len(raw['cuts']) else 0} for i in indices]
            with self.subTest(indices=indices),self.assertRaises(ValueError):review(raw,self.captions,6,10,lambda _:{'spans':spans})

    def test_correction_feedback_keeps_original_indices_when_middle_cut_removed(self):
        raw={'cuts':[{'first_id':0,'last_id':0,'role':'hook'}, {'first_id':3,'last_id':3,'role':'body'}, {'first_id':7,'last_id':7,'role':'conclusion'}],
             'hook':'Headline','cta':'Follow','reason':'A coherent story'}
        responses=[{'spans':[{'cut_index':0,'first_id':0,'last_id':0},{'cut_index':2,'first_id':7,'last_id':7}]},
                   {'spans':[{'cut_index':0,'first_id':0,'last_id':0},{'cut_index':1,'first_id':3,'last_id':3},{'cut_index':2,'first_id':7,'last_id':7}]}]
        prompts=[]
        def ask(prompt):prompts.append(prompt);return responses.pop(0)
        review(raw,self.captions,8,10,ask)
        feedback=json.loads(prompts[1].split('AUTHORITATIVE TIMING CHECK: ')[1].split('\nCorrect')[0])
        self.assertEqual([r['role'] for r in feedback['selected_spans']],['hook','conclusion'])
        self.assertEqual([r['cut_index'] for r in feedback['selected_spans']],[0,2])
