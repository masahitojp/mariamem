from pathlib import Path
import unittest,tempfile,shutil,json
from analyze import analyze
E=Path(__file__).resolve().parent
class EvidenceTests(unittest.TestCase):
 def test_complete_and_negative_controls(self):
  summary,rows=analyze(E)
  self.assertEqual(len(rows),384)
  self.assertEqual(summary['groups']['ordinary']['children'],144)
  self.assertEqual(summary['groups']['diagnostic']['children'],144)
 def test_invalid_evidence_rejected(self):
  mutations=[('records.json',lambda d:d.pop()),('diagnostic-r0.json',lambda d:d['samples'][0].update(oracle=False)),('diagnostic-r0.json',lambda d:d['samples'][0]['wait_trace'].update(idle_observed=False)),('diagnostic-r0.json',lambda d:d['samples'][0]['wait_trace']['checks'][-1].update(active=1)),('diagnostic-r0.json',lambda d:d['samples'][0]['wait_trace'].update(sleep_requests=99)),('diagnostic-r0.json',lambda d:d['samples'][0].update(cleanup_complete=False)),('diagnostic-r0.json',lambda d:d['samples'][0].update(index=d['samples'][1]['index']))]
  for filename,mutate in mutations:
   with self.subTest(filename=filename),tempfile.TemporaryDirectory() as scratch:
    dest=Path(scratch)
    for name in ['records.json']+[x['report'] for x in json.loads((E/'records.json').read_text())]:shutil.copyfile(E/name,dest/name)
    data=json.loads((dest/filename).read_text());mutate(data);(dest/filename).write_text(json.dumps(data))
    with self.assertRaises(AssertionError):analyze(dest)
if __name__=='__main__':unittest.main()
