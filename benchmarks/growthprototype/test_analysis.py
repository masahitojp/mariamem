import copy,importlib.util,json,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('analysis',Path(__file__).with_name('analyze.py'));a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
class AnalysisTests(unittest.TestCase):
 def setUp(self):self.obs=json.loads((Path(__file__).with_name('results')/'observations.json').read_text())
 def test_complete(self):self.assertEqual(len(a.summarize(self.obs['records'],self.obs['results'])['pairs']),5)
 def test_missing_pair(self):
  with self.assertRaises(AssertionError):a.summarize(self.obs['records'][:-1],self.obs['results'])
 def test_order(self):
  self.obs['records'][0],self.obs['records'][1]=self.obs['records'][1],self.obs['records'][0]
  with self.assertRaises(AssertionError):a.summarize(self.obs['records'],self.obs['results'])
 def test_leak(self):
  next(iter(self.obs['results'].values()))['final']['active_rw_bytes']=65536
  with self.assertRaises(AssertionError):a.summarize(self.obs['records'],self.obs['results'])
 def test_failed_oracle(self):
  next(iter(self.obs['results'].values()))['success']=False
  with self.assertRaises(AssertionError):a.summarize(self.obs['records'],self.obs['results'])
if __name__=='__main__':unittest.main()
