import sys
from pathlib import Path
import json,hashlib,urllib.request,tarfile
w=Path(sys.argv[1]).resolve();t=w/'temp';p=json.loads((w/'evidence/upstream-input.json').read_text());archive=t/p['file']
with urllib.request.urlopen(p['url'],timeout=60) as r,archive.open('wb') as f:
 while chunk:=r.read(1024*1024):f.write(chunk)
assert hashlib.sha256(archive.read_bytes()).hexdigest()==p['sha256']
with tarfile.open(archive) as a:
 members=[m for m in a.getmembers() if len(m.name.split('/'))>1 and m.name.split('/')[1] in ['include','strings']]
 a.extractall(t/'upstream',members=members,filter='data')
(w/'evidence/acquisition.json').write_text(json.dumps({'result':'PASS','sha256':p['sha256'],'extracted':['include','strings']},indent=2)+'\n')
print('pinned archive verified; only strings/include extracted')
