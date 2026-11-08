from pathlib import Path
import json,subprocess,base64,hashlib,concurrent.futures
import sys
w=Path(sys.argv[1]).resolve();out=w/'temp/upstream';out.mkdir(parents=True,exist_ok=True)
commit='83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e'
files=['tpool/tpool_generic.cc','tpool/aio_simulated.cc','tpool/tpool.h','storage/innobase/os/os0file.cc','storage/innobase/fil/fil0fil.cc','storage/innobase/buf/buf0rea.cc','storage/innobase/buf/buf0dump.cc','storage/innobase/srv/srv0start.cc']
def fetch(name):
 r=subprocess.run(['gh','api',f'repos/MariaDB/server/contents/{name}?ref={commit}'],capture_output=True,text=True);r.check_returncode();v=json.loads(r.stdout);data=base64.b64decode(v['content']);p=out/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data);return name,{'blob_sha':v['sha'],'sha256':hashlib.sha256(data).hexdigest()}
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:records=dict(pool.map(fetch,files))
(w/'evidence/upstream-files.json').write_text(json.dumps({'source_commit':commit,'files':records},indent=2)+'\n');print('Fetched',len(records),'pinned primary source files')
