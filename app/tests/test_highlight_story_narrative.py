import unittest
from ks import cli_highlight_story as H


class StrictHighlightPlanTests(unittest.TestCase):
    def setUp(self):
        self.captions = [dict(id=i, start=i*20, end=(i+1)*20, text=t) for i,t in enumerate([
            'Campaigns fail when famous creators do not reach buyers.',
            'Compare creator audience with intended buyers first.',
            'Choose audience fit before fame to reach those buyers.'])]
        self.candidate = dict(axis='audience fit', hook='Audience first', cta='Check audience fit', reason='Fit solves reach',
                              cuts=[dict(first_id=i,last_id=i,role=r) for i,r in enumerate(['hook','body','conclusion'])])
        self.row = dict(candidate=1,coherent=True,evidence=['Campaigns fail','Compare creator audience','Choose audience fit'],
                        narrative=dict(opening=dict(passage=1,quote='Campaigns fail',claim='Why campaigns fail'),
                                       development=[dict(passage=2,quote='Compare creator audience',explains='Fit addresses reach')],
                                       payoff=dict(passage=3,quote='Choose audience fit',resolves='Fit solves failed reach'),
                                       starts_complete=True,ends_complete=True,no_missing_context=True,no_unanswered_promises=True))

    def run_plan(self, reviewer):
        return H.plan(instruction='Make one story',captions=self.captions,rows=self.captions,passages=[],allowed=None,
                      low=50,high=70,ask_plan=lambda *a:dict(candidates=[self.candidate]),ask_judge=reviewer,
                      progress=lambda _:None,require_narrative=True)

    def test_strict_plan_preserves_grounded_review_and_allows_output_budget(self):
        budgets=[]
        def review(prompt,tokens):
            budgets.append(tokens)
            return dict(verdicts=[self.row],best=1)
        result=self.run_plan(review)
        self.assertTrue(result['verified'])
        self.assertEqual(result['story'].get('narrative_review'),self.row['narrative'])
        self.assertEqual(budgets,[4096])

    def test_strict_plan_never_verifies_bare_coherent_response(self):
        row={k:v for k,v in self.row.items() if k!='narrative'}
        result=self.run_plan(lambda *a:dict(verdicts=[row],best=1))
        self.assertFalse(result['verified'])
        self.assertNotIn('narrative_review',result['story'])

    def test_repaired_candidate_also_requires_and_preserves_narrative(self):
        budgets=[]
        def review(prompt,tokens):
            budgets.append(tokens)
            if len(budgets)<3:
                return dict(verdicts=[dict(candidate=1,coherent=False,issue='choose another axis')])
            return dict(verdicts=[self.row],best=1)
        result=self.run_plan(review)
        self.assertTrue(result['verified'])
        self.assertEqual(result['story'].get('narrative_review'),self.row['narrative'])
        self.assertEqual(budgets,[4096,4096,4096])
        self.assertEqual(result['calls'],6)

    def test_strict_judge_timeout_returns_unverified_without_another_request(self):
        requests=[]
        def review(*args):
            requests.append(args)
            raise TimeoutError('provider may still be processing')
        result=self.run_plan(review)
        self.assertFalse(result['verified'])
        self.assertEqual(len(requests),1)
        self.assertEqual(result['calls'],2)

    def test_provider_failure_keeps_valid_candidate_unverified_for_manual_review(self):
        requests=[]
        def review(*args):
            requests.append(args)
            raise RuntimeError('private provider fixture')
        result=self.run_plan(review)
        self.assertFalse(result['verified'])
        self.assertNotIn('narrative_review',result['story'])
        self.assertEqual(len(requests),1)
        self.assertEqual(result['calls'],2)
        self.assertTrue(any('ยังไม่ผ่าน' in w for w in result['story']['warnings']))
        self.assertNotIn('private provider',str(result))

    def test_provider_failure_in_last_repair_keeps_unverified_candidate(self):
        attempts=[]
        def review(*args):
            attempts.append(1)
            if len(attempts)<3:return dict(verdicts=[dict(candidate=1,coherent=False,issue='Incomplete argument')])
            raise RuntimeError('service unavailable')
        result=self.run_plan(review)
        self.assertFalse(result['verified'])
        self.assertEqual(len(attempts),3)
        self.assertNotIn('narrative_review',result['story'])
