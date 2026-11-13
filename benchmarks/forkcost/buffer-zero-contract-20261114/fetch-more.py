from pathlib import Path
import urllib.request,hashlib,json
E=Path(__file__).resolve().parent;T=E.parent/'temp/source';records=json.loads((E/'source-files.json').read_text())
for f in ['include/my_virtual_mem.h','mysys/my_virtual_mem.c','storage/innobase/buf/buf0lru.cc','storage/innobase/mtr/mtr0log.cc','storage/innobase/include/mtr0mtr.h']:
 u='https://raw.githubusercontent.com/MariaDB/server/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/'+f
 try:b=urllib.request.urlopen(u,timeout=30).read()
 except Exception as e:print(f,str(e),flush=True);continue
 p=T/f;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b);records.append({'file':f,'url':u,'sha256':hashlib.sha256(b).hexdigest()});print(f,len(b),flush=True)
(E/'source-files.json').write_text(json.dumps(records,indent=2)+'\n')
