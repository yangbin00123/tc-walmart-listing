import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from keyword_groups import apply,check
class GroupsTest(unittest.TestCase):
 def setUp(self):
  self.profile={'facts':[{'fact_id':'f1','status':'confirmed'},{'fact_id':'f2','status':'unknown'}]}
  self.ledger={'decisions':[{'keyword':'storage bag'},{'keyword':'storage bags'}]}
  self.spec={'groups':{'identity':{'keywords':['storage bag','storage bags'],'decision':'eligible','role':'identity','relevance':'relevant','fact_ids':['f1'],'evidence':'confirmed identity','query_intent':'storage bag'}}}
 def test_group_application(self):
  check(self.profile,apply(self.ledger,self.spec)['decisions'])
 def test_missing_or_duplicate(self):
  self.spec['groups']['identity']['keywords'].pop()
  with self.assertRaises(ValueError):apply(self.ledger,self.spec)
 def test_generic_high(self):
  self.spec['groups']['identity']['relevance']='high'
  with self.assertRaises(ValueError):check(self.profile,apply(self.ledger,self.spec)['decisions'])
 def test_unknown_fact(self):
  self.spec['groups']['identity']['fact_ids']=['f2']
  with self.assertRaises(ValueError):check(self.profile,apply(self.ledger,self.spec)['decisions'])
 def test_group_conflict(self):
  rows=apply(self.ledger,self.spec)['decisions'];rows[1]['decision']='deferred'
  with self.assertRaises(ValueError):check(self.profile,rows)
 def test_override_needs_basis(self):
  self.spec['overrides']={'storage bags':{'decision':'deferred'}}
  with self.assertRaises(ValueError):apply(self.ledger,self.spec)
