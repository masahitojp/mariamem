from pathlib import Path
import urllib.request,json,hashlib
E=Path(__file__).resolve().parent;T=E.parent/'temp/source';records=json.loads((E/'source-files.json').read_text())
for repo,ref,files in [('wasix-org/wasix-libc','v2026-07-03.1',['dlmalloc/src/malloc.c','dlmalloc/src/dlmalloc.c','libc-top-half/musl/src/malloc/posix_memalign.c']),('MariaDB/server','83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e',['storage/innobase/include/univ.i'])]:
 for f in files:
  u=f'https://raw.githubusercontent.com/{repo}/{ref}/{f}';b=urllib.request.urlopen(u,timeout=30).read();p=T/f;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b);records.append({'file':f,'url':u,'sha256':hashlib.sha256(b).hexdigest()});print(f,len(b),flush=True)
(E/'source-files.json').write_text(json.dumps(records,indent=2)+'\n')
