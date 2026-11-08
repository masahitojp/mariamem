import unittest,json,copy
from pathlib import Path
from codec import pack,unpack,read
from analyze import reduce
E=Path(__file__).resolve().parent
class Checks(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.rows=read(E/'observations.json')
 def test_complete_matrix(self):
  result,rows=reduce(self.rows);self.assertEqual(len(rows),1152);self.assertEqual(result['diagnostic_children'],576)
 def test_negative_oracles(self):
  primary=next(i for i,r in enumerate(self.rows) if r['kind']=='primary' and r['observer']=='on')
  cases=['missing_cell','missing_trace','dropped_init','missing_phase','failed_child','wrong_count','wrong_census']
  for mutation in cases:
   with self.subTest(mutation=mutation):
    # Copy only a changed record; never mutate the immutable source observations.
    rows=list(self.rows);r=copy.deepcopy(rows[primary]);rows[primary]=r
    if mutation=='missing_cell':rows.pop(primary)
    elif mutation=='missing_trace':r['traces'].pop('0')
    elif mutation=='dropped_init':r['traces']['0']['startup']['guest']['initialization']['dropped_records']=1
    elif mutation=='missing_phase':r['traces']['0']['startup']['guest']['events']=[e for e in r['traces']['0']['startup']['guest']['events'] if e['name']!='server_init_complete']
    elif mutation=='failed_child':r['report']['samples'][0]['oracle']=False
    elif mutation=='wrong_count':r['count']-=1
    elif mutation=='wrong_census':r['report']['cleanup_stats']['lp_hits']=1
    with self.assertRaises((AssertionError,KeyError)):reduce(rows)
 def test_codec(self):
  value={'one':[1,2,{'a':'日本語','b':None}],'x':False};self.assertEqual(unpack(pack(value)),value)
  for mutation in ['hash','length','trailing','oversize']:
   z=pack(value)
   if mutation=='hash':z['raw_sha256']='0'*64
   if mutation=='length':z['raw_bytes']-=1
   if mutation=='trailing':
    import base64
    z['data']=base64.b64encode(base64.b64decode(z['data'])+b'extra').decode()
   if mutation=='oversize':z['raw_bytes']=151*1024*1024
   with self.subTest(mutation=mutation),self.assertRaises(AssertionError):unpack(z)
if __name__=='__main__':unittest.main()
