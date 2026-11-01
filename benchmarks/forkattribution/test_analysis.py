import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('attribution',HERE/'analyze.py');a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)/'results';shutil.copytree(HERE/'results',self.root)
    def change(self,fn):
        p=self.root/'observations.json';d=json.loads(p.read_text());fn(d);p.write_text(json.dumps(d));self.seal()
    def seal(self):
        p=self.root/'SHA256SUMS.json';files=json.loads(p.read_text());p.write_text(json.dumps({n:hashlib.sha256((self.root/n).read_bytes()).hexdigest() for n in files}))
    def test_read_only_after_cleanup(self):
        before={p.name:(p.read_bytes(),p.stat().st_mtime_ns) for p in self.root.iterdir()};a.check(self.root)
        self.assertEqual(before,{p.name:(p.read_bytes(),p.stat().st_mtime_ns) for p in self.root.iterdir()})
    def test_resealed_wrong_summary(self):
        p=self.root/'summary.json';d=json.loads(p.read_text());d['growth_calls_after_reserve']['median']+=1;p.write_text(a.rendered(d));self.seal()
        with self.assertRaises(AssertionError):a.check(self.root)
    def test_missing_repetition(self):
        self.change(lambda d:d['stages'].pop())
        with self.assertRaises(AssertionError):a.check(self.root)
    def test_initial_span_only_rejected(self):
        def change(d):
            for e in d['stages'][0]['result']['events']:
                if e['stage']=='child1_checked':e['guest_observed_bytes']=268435456
        self.change(change)
        with self.assertRaises(AssertionError):a.check(self.root)
    def test_page_partition_rejected(self):
        def change(d):d['stages'][0]['result']['comparison']['same_nonzero_pages']+=1
        self.change(change)
        with self.assertRaises(AssertionError):a.check(self.root)
if __name__=='__main__':unittest.main()
