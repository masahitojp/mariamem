from pathlib import Path
import unittest,json,copy
from analyze import reduce,validate
class Tests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  p=Path(__file__).parent;cls.records=json.loads((p/'records.json').read_text());cls.obs=json.loads((p/'observations.json').read_text())
 def test_finite_campaign(self):
  summary,_=reduce(self.records,self.obs.__getitem__);self.assertTrue(summary['prototype_threshold_met'])
 def test_bad_evidence(self):
  rec=next(x for x in self.records if x['kind']=='primary' and x['arm']=='prepared')
  for key,value in [('lp_hits',0),('lp_copies',0),('lp_fallback',1),('active_mappings',1),('lp_verified',1)]:
   r=copy.deepcopy(self.obs[rec['report']]);r['cleanup_stats'][key]=value
   with self.subTest(key=key),self.assertRaises(AssertionError):validate(r,rec)
  r=copy.deepcopy(self.obs[rec['report']]);r['samples'][0]['oracle']=False
  with self.assertRaises(AssertionError):validate(r,rec)
  with self.assertRaises(AssertionError):reduce(self.records[:-1],self.obs.__getitem__)
if __name__=='__main__':unittest.main()
