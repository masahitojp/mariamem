from pathlib import Path
import urllib.request,hashlib,json
E=Path(__file__).resolve().parent;T=E.parent/'temp/source';T.mkdir(exist_ok=True)
files=['storage/innobase/log/log0log.cc','storage/innobase/buf/buf0buf.cc','storage/innobase/handler/ha_innodb.cc','mysys/my_malloc.c','mysys/mf_keycache.c','mysys/ma_dyncol.c','storage/maria/ma_pagecache.c']
records=[]
for f in files:
 u='https://raw.githubusercontent.com/MariaDB/server/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/'+f
 try:b=urllib.request.urlopen(u).read()
 except Exception as e:print(f,e);continue
 (T/Path(f).name).write_bytes(b);records.append({'file':f,'url':u,'sha256':hashlib.sha256(b).hexdigest()})
(E/'source-files.json').write_text(json.dumps(records,indent=2))
