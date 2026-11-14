"""Read-only reproduction of the saved numerical summary; no builds/network."""
from pathlib import Path
import hashlib,json,shutil,tempfile,subprocess,sys
D=Path(__file__).resolve().parent
checks=json.loads((D/'SHA256SUMS.json').read_text())
for name,sha in checks.items():assert hashlib.sha256((D/name).read_bytes()).hexdigest()==sha,name
with tempfile.TemporaryDirectory(prefix='bp-zero-saved-') as path:
 E=Path(path)
 for n in ['measurement-records.json','lifecycle-records.json']:shutil.copy2(D/'evidence'/n,E/n)
 for n in ['runs','lifecycle-runs']:shutil.copytree(D/n,E/n)
 shutil.copy2(D/'tools/analyze.py',E/'analyze.py');subprocess.run([sys.executable,str(E/'analyze.py')],stdout=subprocess.DEVNULL,check=True)
 assert json.loads((E/'summary.json').read_text())==json.loads((D/'evidence/summary.json').read_text())
 assert (E/'children.csv').read_bytes()==(D/'evidence/children.csv').read_bytes()
print('PASS saved evidence hashes, complete matrices, summary and CSV reproduction')
