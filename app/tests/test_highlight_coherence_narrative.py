import copy
import unittest

from ks.cli_highlight_coherence import check, judge


class NarrativeContractTests(unittest.TestCase):
    def setUp(self):
        self.story = {'axis': 'choose audience before creator', 'cuts': [
            {'role': 'hook', 'text': 'Why does a campaign fail despite a famous creator?'},
            {'role': 'body', 'text': 'First compare the creator audience with the buyers.'},
            {'role': 'conclusion', 'text': 'Choose audience fit before fame to reach buyers.'}]}
        self.row = {'candidate': 1, 'coherent': True,
                    'evidence': ['campaign fail', 'compare the creator audience', 'audience fit before fame'],
                    'narrative': {
                        'opening': {'passage': 1, 'quote': 'campaign fail', 'claim': 'Why fame alone fails'},
                        'development': [{'passage': 2, 'quote': 'compare the creator audience',
                                         'explains': 'Audience mismatch explains the failure'}],
                        'payoff': {'passage': 3, 'quote': 'audience fit before fame',
                                   'resolves': 'Select for fit to solve the opening failure'},
                        'starts_complete': True, 'ends_complete': True,
                        'no_missing_context': True, 'no_unanswered_promises': True}}

    def run_review(self, row):
        return judge([self.story], lambda prompt: {'verdicts': [row], 'best': 1},
                     require_narrative=True)

    def test_bare_grounded_quotes_cannot_approve_complete_story_contract(self):
        row = copy.deepcopy(self.row)
        del row['narrative']
        results, best = self.run_review(row)
        self.assertFalse(results[0]['coherent'])
        self.assertIsNone(best)

    def test_rejects_fabricated_payoff_even_with_valid_general_evidence(self):
        row = copy.deepcopy(self.row)
        row['narrative']['payoff']['quote'] = 'invented resolution'
        self.assertFalse(self.run_review(row)[0][0]['coherent'])

    def test_every_middle_passage_must_explain_opening(self):
        row = copy.deepcopy(self.row)
        row['narrative']['development'] = []
        self.assertFalse(self.run_review(row)[0][0]['coherent'])

    def test_incomplete_context_or_unanswered_promise_is_not_approved(self):
        for field in ('starts_complete', 'ends_complete', 'no_missing_context', 'no_unanswered_promises'):
            with self.subTest(field=field):
                row = copy.deepcopy(self.row)
                row['narrative'][field] = False
                self.assertFalse(self.run_review(row)[0][0]['coherent'])

    def test_complete_grounded_review_accepts_without_additional_request(self):
        calls = []
        def ask(prompt):
            calls.append(prompt)
            return {'verdicts': [self.row], 'best': 1}
        result, best = judge([self.story], ask, require_narrative=True)
        self.assertTrue(result[0]['coherent'])
        self.assertEqual(best, 0)
        self.assertEqual(len(calls), 1)
        self.assertEqual(result[0]['narrative'], self.row['narrative'])

    def test_strict_single_story_check_cannot_use_legacy_bare_true(self):
        with self.assertRaises(ValueError):
            check(self.story, lambda prompt: {'coherent': True}, require_narrative=True)
