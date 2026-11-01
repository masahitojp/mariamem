"""Focused tests: no engines/build needed, only compact resource evidence."""
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
import hashlib

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('resource_analysis', HERE / 'analyze.py')
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)

class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'results'
        shutil.copytree(HERE / 'results', self.root)

    def reseal(self):
        p = self.root / 'SHA256SUMS.json'
        files = json.loads(p.read_text())
        p.write_text(json.dumps({n: hashlib.sha256((self.root/n).read_bytes()).hexdigest() for n in files}))

    def test_check_is_readonly_and_self_contained(self):
        def state():
            return {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in self.root.iterdir()}
        before = state()
        a.check(self.root)
        self.assertEqual(before, state())

    def test_resealed_wrong_summary_rejected(self):
        p = self.root / 'summary.json'; d = json.loads(p.read_text())
        d['backends']['mariamem']['phases']['fork']['cpu_ms']['median'] += 1
        p.write_text(a.json_text(d)); self.reseal()
        with self.assertRaises(AssertionError): a.check(self.root)

    def test_missing_repeat_rejected(self):
        p = self.root / 'observations.json'; d = json.loads(p.read_text()); d.pop()
        p.write_text(json.dumps(d)); self.reseal()
        with self.assertRaises(AssertionError): a.check(self.root)

    def test_resealed_inconsistent_cpu_rejected(self):
        p = self.root / 'observations.json'; d = json.loads(p.read_text())
        item = next(o for o in d if not o['record']['warmup'])
        phase = next(p for e in item['result']['events'] for p in e['phases'] if p['name'] == 'fork')
        phase['cpu_ms'] += 1
        p.write_text(json.dumps(d)); self.reseal()
        with self.assertRaises(AssertionError): a.check(self.root)

if __name__ == '__main__': unittest.main()
