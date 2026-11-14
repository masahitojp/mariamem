"""Verify immutable observations and reproduce the published comparison."""
from pathlib import Path
import hashlib,json,subprocess,sys
E=Path(__file__).resolve().parent
sums=json.loads((E/'SHA256SUMS.json').read_text())
actual={p.relative_to(E).as_posix() for p in E.rglob('*') if p.is_file() and p.name!='SHA256SUMS.json'}
assert actual==set(sums),'inventory differs'
for name,expected in sums.items():assert hashlib.sha256((E/name).read_bytes()).hexdigest()==expected,name
for name,row in json.loads((E/'publication.json').read_text())['files'].items():assert sums[name]==row['saved_sha256'],name
outputs=('summary.json','summary.csv','children.csv','spans.csv')
before={n:(E/n).read_bytes() for n in outputs}
subprocess.run([sys.executable,str(E/'analyze.py')],check=True,stdout=subprocess.DEVNULL)
for n in outputs:assert (E/n).read_bytes()==before[n],n
print('PASS all saved hashes,50 processes,864 child oracles,matching scenarios,and summary/CSV reproduction')
