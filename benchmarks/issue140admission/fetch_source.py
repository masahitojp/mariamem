from pathlib import Path
import json,subprocess,base64,hashlib
import sys
w=Path(sys.argv[1]).resolve();records={};commit='83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e'
for name in ['tpool/task.cc','tpool/task_group.cc','tpool/tpool_generic.cc','tpool/tpool_structs.h']:
 v=json.loads(subprocess.check_output(['gh','api',f'repos/MariaDB/server/contents/{name}?ref={commit}'],text=True));data=base64.b64decode(v['content']);p=w/'temp/upstream'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data);records[name]={'blob_sha':v['sha'],'sha256':hashlib.sha256(data).hexdigest()}
(w/'evidence/upstream-files.json').write_text(json.dumps({'source_commit':commit,'files':records},indent=2)+'\n');print('4 source files pinned')
