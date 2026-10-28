import unittest
from ks.cli_lab_planning import stock_tokens,duration_feedback
class PlanningRepairTests(unittest.TestCase):
 def test_exact_phrase_and_punctuation_repair_without_mutating_input(self):
  raw={'stock_requests':[{'query':'Office, paper-documents','required_terms':['paper documents'],'alternatives':[{'query':'office desk','required_terms':['OFFICE']}]}]}
  result=stock_tokens(raw)['stock_requests'][0]
  self.assertEqual(result['required_terms'],['paper','documents']);self.assertEqual(result['query'],'Office paper documents')
  self.assertEqual(result['alternatives'][0]['required_terms'],['office']);self.assertEqual(raw['stock_requests'][0]['query'],'Office, paper-documents')
 def test_mismatched_essential_concept_never_removed(self):
  raw={'stock_requests':[{'query':'office desk','required_terms':['university']}]}
  self.assertEqual(stock_tokens(raw),raw)
 def test_realistic_over_budget_feedback(self):
  captions=[dict(start=0,end=200),dict(start=200,end=392.72)]
  report=duration_feedback({'cuts':[dict(first_id=0,last_id=0),dict(first_id=1,last_id=1)]},captions,300,360)
  self.assertEqual(report['actual_total_seconds'],392.72);self.assertEqual(report['seconds_over_maximum'],32.72);self.assertEqual(report['target_seconds'],330)
