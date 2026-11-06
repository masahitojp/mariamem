from pathlib import Path
import tempfile,shutil,json,unittest
import analyze as a
E=Path(__file__).resolve().parent
class MutationTests(unittest.TestCase):
 def test_incomplete_or_invalid_primary_evidence_rejected(self):
  mutations=[('records.json',lambda d:d.pop()),('poll-r0.json',lambda d:d['samples'][0].update(oracle=False)),('poll-r0.json',lambda d:d['samples'][0].update(cleanup_complete=False)),('poll-r0.json',lambda d:d['samples'][0].update(index=d['samples'][1]['index'])),('poll-r0.json',lambda d:d['samples'][0].update(wait_ms=-1))]
  for filename,fn in mutations:
   with self.subTest(filename=filename),tempfile.TemporaryDirectory() as scratch:
    dest=Path(scratch)
    for name in ['records.json']+[r['report'] for r in json.loads((E/'records.json').read_text())]:shutil.copyfile(E/name,dest/name)
    value=json.loads((dest/filename).read_text());fn(value);(dest/filename).write_text(json.dumps(value))
    saved=a.E;a.E=dest
    try:
     with self.assertRaises(AssertionError):a.analyze()
    finally:a.E=saved
if __name__=='__main__':unittest.main()
