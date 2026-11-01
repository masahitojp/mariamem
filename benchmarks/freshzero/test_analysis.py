import copy,json,unittest
from pathlib import Path
from analyze import summarize
class EvidenceTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.data=json.loads((Path(__file__).parent/'results/observations.json').read_text())
 def test_missing_pair(self):
  d=copy.deepcopy(self.data);d['trials'].pop()
  with self.assertRaises(AssertionError):summarize(d)
 def test_missing_stage(self):
  d=copy.deepcopy(self.data);d['traces']['fresh']['stages'].pop()
  with self.assertRaises(AssertionError):summarize(d)
 def test_missing_dirty_memory_control(self):
  d=copy.deepcopy(self.data);d['pilot']['constructor_selftests']=0
  with self.assertRaises(AssertionError):summarize(d)
 def test_mapping_leak(self):
  d=copy.deepcopy(self.data);d['trials'][0]['final']['active_mappings']=1
  with self.assertRaises(AssertionError):summarize(d)
if __name__=='__main__':unittest.main()
