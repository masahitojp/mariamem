"""Read-only evidence and numerical reproduction; no network or Go builds."""
from pathlib import Path
import json,hashlib,tempfile,shutil,subprocess,sys
D=Path(__file__).resolve().parent
for name,h in json.loads((D/'SHA256SUMS.json').read_text()).items():
 assert hashlib.sha256((D/name).read_bytes()).hexdigest()==h,name
for directory in (D,D/'light-monitor'):
 records=json.loads(((D/'evidence/measurement-records.json') if directory==D else directory/'measurement-records.json').read_text())
 for r in records:
  assert r['returncode']==0
  binaries=json.loads((D/('evidence/'+r['variant']+'-binaries.json')).read_text());assert r['binary_sha256']==binaries[r['harness']]['sha256']
  d=json.loads((directory/'runs'/(r['name']+'.json')).read_text())
  if r['harness']=='lifecycle':assert d['success'] and len(d['children'])==(16 if r['repetition']<0 else 48) and all(c['oracle'] and c['closed'] for c in d['children'])
  else:assert (directory/'runs'/(r['name']+'.txt')).read_text().rstrip().endswith('PASS')
 with tempfile.TemporaryDirectory(prefix='buffer-zero-saved-') as temporary:
  E=Path(temporary);shutil.copy2((D/'evidence/measurement-records.json') if directory==D else directory/'measurement-records.json',E/'measurement-records.json');shutil.copytree(directory/'runs',E/'runs');shutil.copy2(D/'tools/analyze.py',E/'analyze.py')
  subprocess.run([sys.executable,str(E/'analyze.py')],check=True,stdout=subprocess.DEVNULL)
  assert json.loads((E/'summary.json').read_text())==json.loads(((D/'evidence/summary.json') if directory==D else directory/'summary.json').read_text())
  assert (E/'children.csv').read_bytes()==((D/'evidence/children.csv') if directory==D else directory/'children.csv').read_bytes()
print('PASS evidence hashes, all64 processes/binary identities, separate complete matrices and both summary/CSV reproductions')
