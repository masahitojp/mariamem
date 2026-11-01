import copy,json,unittest,gzip
from pack import normalize_profile,enc
from pathlib import Path
from analyze import summarize,top
class EvidenceTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.data=json.loads((Path(__file__).parent/'results/observations.json').read_text())
 def test_missing_phase(self):
  d=copy.deepcopy(self.data);d['runs'].pop()
  with self.assertRaises(AssertionError):summarize(d)
 def test_phase_count(self):
  d=copy.deepcopy(self.data);d['runs'][0]['result']['phase_totals']['fork']['count']-=1
  with self.assertRaises(AssertionError):summarize(d)
 def test_worker_leak(self):
  d=copy.deepcopy(self.data);r=next(r for r in d['runs'] if r['mode']=='diagnostic');r['result']['diagnostic']['fork']['spawn']+=1
  with self.assertRaises(AssertionError):summarize(d)
 def test_profile_units(self):
  d=top('Duration: 2s, Total samples = 0.5s\n 20ms 4% 4% 120ms 24% runtime.pthread_cond_signal\n')
  self.assertEqual(d['total_cpu_sample_ms'],500);self.assertEqual(d['top'][0]['flat_ms'],20)
 def test_profile_path_normalization(self):
  root=b'/private/tmp/test';text=root+b'/probe';sample=enc(2<<3|2)+enc(3)+b'abc'
  original=sample+enc(6<<3|2)+enc(len(text))+text
  normalized=gzip.decompress(normalize_profile(gzip.compress(original),root))
  replacement=b'<WORKSPACE>/probe'
  self.assertEqual(normalized,sample+enc(6<<3|2)+enc(len(replacement))+replacement)
if __name__=='__main__':unittest.main()
