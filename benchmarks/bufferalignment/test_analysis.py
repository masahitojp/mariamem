import copy,json,unittest
from pathlib import Path
from analyze import summarize

class EvidenceTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.data=json.loads((Path(__file__).parent/'results/observations.json').read_text())
 def test_missing_pair_rejected(self):
  d=copy.deepcopy(self.data);d['trials'].pop()
  with self.assertRaises(AssertionError):summarize(d)
 def test_retry_not_eliminated_rejected(self):
  d=copy.deepcopy(self.data);d['traces']['aligned']['buffer_pool_zero'].append(d['traces']['aligned']['buffer_pool_zero'][0])
  with self.assertRaises(AssertionError):summarize(d)
 def test_unaligned_address_rejected(self):
  d=copy.deepcopy(self.data);d['traces']['aligned']['buffer_pool_zero'][0]['dst']+=4096
  with self.assertRaises(AssertionError):summarize(d)
 def test_mapping_leak_rejected(self):
  d=copy.deepcopy(self.data);d['trials'][0]['final']['active_mappings']=1
  with self.assertRaises(AssertionError):summarize(d)
if __name__=='__main__':unittest.main()
