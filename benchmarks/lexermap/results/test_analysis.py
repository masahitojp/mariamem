from pathlib import Path
import copy,json,unittest
from analyze import analyze
from compact import pack,unpack
class EvidenceTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.raw=unpack(json.loads((Path(__file__).parent/'observations.json').read_text()))
 def test_roundtrip(self):self.assertEqual(unpack(pack(self.raw)),self.raw)
 def test_negative_oracles(self):
  def cases(d,which):
   x=d['timed-0'];row=x['Samples'][1]['Rows'][0]
   if which==0:row['result']=1
   if which==1:row['exception']=1
   if which==2:row['elapsed_ns']=0
   if which==3:x['Cleanup']['active_mappings']=1
   if which==4:x['Samples'][1]['Rows'].pop()
   if which==5:d['inventory-0']['Samples'][1]['Rows'][0]['pair_hex']='00'*512
   if which==6:x['Samples'].pop()
   if which==7:x['Success']=False
  for i in range(8):
   data=copy.deepcopy(self.raw);cases(data,i)
   with self.subTest(mutation=i),self.assertRaises(AssertionError):analyze(data)
if __name__=='__main__':unittest.main()
