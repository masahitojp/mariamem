import importlib.util,json,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('analysis',Path(__file__).with_name('analyze.py'));a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
class Checks(unittest.TestCase):
 def setUp(self):self.d=json.loads((Path(__file__).with_name('results')/'observations.json').read_text())
 def test_complete(self):self.assertEqual(len(a.summarize(self.d['records'],self.d['results'])['rows']),12)
 def test_union(self):self.assertEqual(a.union_bytes([(0,10),(4,6),(9,20),(30,32)]),22)
 def test_missing(self):
  with self.assertRaises(AssertionError):a.summarize(self.d['records'][:-1],self.d['results'])
 def test_overflow(self):
  next(iter(self.d['results'].values()))['overflow']=True
  with self.assertRaises(AssertionError):a.summarize(self.d['records'],self.d['results'])
 def test_bad_totals(self):
  d=next(v for v in self.d['results'].values() if v['observed']);d['totals']['1']['zero_bytes']=0
  with self.assertRaises(AssertionError):a.summarize(self.d['records'],self.d['results'])
if __name__=='__main__':unittest.main()
