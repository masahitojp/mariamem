from pathlib import Path
import tempfile,shutil,json,unittest
import analyze as a
E=Path(__file__).resolve().parent
class EvidenceTests(unittest.TestCase):
 def test_bad_cap_worker_and_lifetime_evidence_rejected(self):
  mutations=[('records.json',lambda d:d.pop()),('poll-cap1-r0.json',lambda d:d.update(resolved_max_forks=4)),('poll-cap1-r0.json',lambda d:d.update(parallel=1)),('poll-cap1-r0.json',lambda d:d['samples'][0].update(child_ready_offset_ms=0)),('poll-cap1-r0.json',lambda d:d['samples'][0].update(index=d['samples'][1]['index'])),('poll-cap1-r0.json',lambda d:d.update(cleanup_complete=False)),('poll-cap1-r0.json',lambda d:d['samples'][0].update(oracle=False))]
  for filename,mutate in mutations:
   with self.subTest(filename=filename),tempfile.TemporaryDirectory() as scratch:
    dest=Path(scratch)
    for n in ['records.json','plan.json']+[r['report'] for r in a.read('records.json')]:
     (dest/n).write_text(json.dumps(a.read(n)))
    value=json.loads((dest/filename).read_text());mutate(value);(dest/filename).write_text(json.dumps(value));old=a.E;a.E=dest
    try:
     with self.assertRaises(AssertionError):a.analyze()
    finally:a.E=old
if __name__=='__main__':unittest.main()
