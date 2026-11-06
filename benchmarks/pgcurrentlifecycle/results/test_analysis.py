import copy,unittest
from analyze import validate
class Oracles(unittest.TestCase):
 def fixture(self):
  names=['start_or_fork','connect','select1','seed','count_sum','update','verify_update','retire','close']
  r={'cleanup':True,'max_active':1,'mode':'fresh','parallel':1,'count':1,'resolved_max_forks':0,'cleanup_stats':{k:0 for k in ['active_mappings','active_rw_bytes','active_reserved_bytes','release_failures']},'success':True,'suite_ms':11,'batch_end_ms':10,'batch_begin_ms':0,'samples':[{'index':0,'begin_ms':0,'end_ms':10,'cleanup':True,'oracle':True,'spans':[{'name':n,'begin_ms':i,'end_ms':i+1} for i,n in enumerate(names)]}]}
  return r,{'variant':'mariamem','mode':'fresh','parallel':1,'count':1,'negative':False,'exit_code':0}
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
 def test_complete_matrix_reduction(self):
  from analyze import reduce
  records=[];data={}
  def add(variant,mode,parallel,rep,kind):
   r,rec=self.fixture();negative=kind=='negative';count=1 if negative else 48
   rec.update(variant=variant,mode=mode,parallel=parallel,rep=rep,kind=kind,count=count,negative=negative,exit_code=1 if negative else 0,report=str(len(records)),external_process_ms=210 if variant=='mariamem' else 110,process_cpu_ms=190 if variant=='mariamem' else 90)
   r.update(mode=mode,parallel=parallel,count=count,resolved_max_forks=parallel if mode=='fork' else 0,suite_ms=200 if variant=='mariamem' else 100,suite_cpu_ms=180 if variant=='mariamem' else 80,batch_ms=90,batch_begin_ms=0,batch_end_ms=90)
   sample=r['samples'][0];sample['lane']=0;r['root_spans']=[]
   if mode=='fork':sample['spans']=[x for x in sample['spans'] if x['name']!='seed']
   r['samples']=[dict(copy.deepcopy(sample),index=i) for i in range(count)]
   if negative:r.update(success=False,error='pristine oracle')
   records.append(rec);data[rec['report']]=r
  for variant in ['pgmem','mariamem']:
   for mode in ['fresh','fork']:
    add(variant,mode,1,-2,'pilot');add(variant,mode,1,-2,'negative')
    for parallel in [1,4]:
     add(variant,mode,parallel,-1,'warmup')
     for rep in range(5):add(variant,mode,parallel,rep,'primary')
  for mode in ['fresh','fork']:add('diagnostic',mode,4,0,'diagnostic')
  out,children=reduce(records,data.__getitem__)
  self.assertEqual(len(children),1920)
  self.assertEqual(out['cells']['mariamem-fork-p4']['median']['external_process_ms'],210)
  self.assertEqual(out['paired_version_effects']['fork-p4']['median_paired_mariamem_wall_pct'],100)
if __name__=='__main__':unittest.main()
