import copy,unittest
from analyze import validate
class Oracles(unittest.TestCase):
 def fixture(self):
  names=['start_or_fork','connect','select1','seed','count_sum','update','verify_update','retire','close']
  r={'cleanup':True,'max_active':1,'mode':'fresh','parallel':1,'count':1,'resolved_max_forks':0,'cleanup_stats':{k:0 for k in ['active_mappings','active_rw_bytes','active_reserved_bytes','release_failures']},'success':True,'suite_ms':11,'batch_end_ms':10,'batch_begin_ms':0,'samples':[{'index':0,'begin_ms':0,'end_ms':10,'cleanup':True,'oracle':True,'spans':[{'name':n,'begin_ms':i,'end_ms':i+1} for i,n in enumerate(names)]}]}
  return r,{'mode':'fresh','parallel':1,'count':1,'negative':False,'exit_code':0}
 def test_positive(self):validate(*self.fixture())
 def test_rejects_mutations(self):
  for change in ['cleanup','cap','index','span','oracle','mapping']:
   r,rec=self.fixture()
   if change=='cleanup':r['cleanup']=False
   if change=='cap':r['resolved_max_forks']=1
   if change=='index':r['samples'][0]['index']=2
   if change=='span':r['samples'][0]['spans'].pop()
   if change=='oracle':r['samples'][0]['oracle']=False
   if change=='mapping':r['cleanup_stats']['active_mappings']=1
   with self.subTest(change=change),self.assertRaises(AssertionError):validate(r,rec)
 def test_wrong_seed_requires_expected_failure(self):
  r,rec=self.fixture();rec.update(negative=True,exit_code=1);r.update(success=False,error='pristine oracle: count=1000 sum=500498');validate(r,rec)
  r['error']='unrelated failure'
  with self.assertRaises(AssertionError):validate(r,rec)
if __name__=='__main__':unittest.main()
