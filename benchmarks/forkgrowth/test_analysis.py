import hashlib,importlib.util,json,shutil,tempfile,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('growth_analysis',HERE/'analyze.py');a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)/'results';shutil.copytree(HERE/'results',self.root)
 def seal(self):
  p=self.root/'SHA256SUMS.json';names=json.loads(p.read_text());p.write_text(json.dumps({n:hashlib.sha256((self.root/n).read_bytes()).hexdigest() for n in names}))
 def test_readonly(self):
  before={p.name:(p.read_bytes(),p.stat().st_mtime_ns) for p in self.root.iterdir()};a.check(self.root);self.assertEqual(before,{p.name:(p.read_bytes(),p.stat().st_mtime_ns) for p in self.root.iterdir()})
 def test_wrong_resealed_model(self):
  p=self.root/'summary.json';d=json.loads(p.read_text());d['rows'][0]['models']['16']['protection_calls_after_initial']-=1;p.write_text(a.rendered(d));self.seal()
  with self.assertRaises(AssertionError):a.check(self.root)
 def test_missing_process(self):
  p=self.root/'observations.json';d=json.loads(p.read_text());d.pop();p.write_text(json.dumps(d));self.seal()
  with self.assertRaises(AssertionError):a.check(self.root)
 def test_broken_chain(self):
  p=self.root/'observations.json';d=json.loads(p.read_text());d[0]['result']['children'][0]['steps'][1]['old']+=65536;p.write_text(json.dumps(d));self.seal()
  with self.assertRaises(AssertionError):a.check(self.root)
 def test_lookahead_explicitly_changes_protection_not_logical(self):
  steps=[dict(old=0,next=256<<20),dict(old=256<<20,next=(256<<20)+65536),dict(old=(256<<20)+65536,next=2<<30)]
  exact=a.replay(steps,0);batch=a.replay(steps,16<<20)
  self.assertEqual([x['logical'] for x in exact['trace']],[x['logical'] for x in batch['trace']])
  self.assertEqual(exact['peak_ahead_rw_bytes'],0);self.assertEqual(batch['peak_ahead_rw_bytes'],(16<<20)-65536);self.assertEqual(batch['trace'][-1]['enabled'],2<<30)
if __name__=='__main__':unittest.main()
