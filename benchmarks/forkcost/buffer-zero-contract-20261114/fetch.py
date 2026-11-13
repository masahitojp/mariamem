from pathlib import Path
import urllib.request,hashlib,json
E=Path(__file__).resolve().parent;T=E.parent/'temp/source';T.mkdir(parents=True,exist_ok=True)
files=['storage/innobase/buf/buf0buf.cc','storage/innobase/include/buf0buf.h','storage/innobase/include/buf0buf.inl','storage/innobase/buf/buf0buddy.cc','storage/innobase/buf/buf0flu.cc','storage/innobase/buf/buf0rea.cc','storage/innobase/include/buf0types.h','storage/innobase/include/buf0buddy.ic','storage/innobase/include/buf0buddy.h','storage/innobase/include/buf0flu.h','storage/innobase/include/buf0rea.h','mysys/my_largepage.c','mysys/my_malloc.c','storage/innobase/handler/ha_innodb.cc','storage/innobase/srv/srv0start.cc','storage/innobase/include/my_virtual_mem.h']
records=[]
for f in files:
 u='https://raw.githubusercontent.com/MariaDB/server/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/'+f
 try:b=urllib.request.urlopen(u,timeout=30).read()
 except Exception as e:print(f,str(e),flush=True);continue
 p=T/f;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b);records.append({'file':f,'url':u,'sha256':hashlib.sha256(b).hexdigest()});print(f,len(b),flush=True)
(E/'source-files.json').write_text(json.dumps(records,indent=2)+'\n')
