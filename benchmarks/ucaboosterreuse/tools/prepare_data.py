import sys
from pathlib import Path
import tarfile,json,hashlib,subprocess,time
w=Path(sys.argv[1]).resolve();t=w/'temp';u=next((t/'upstream').iterdir());archive=t/'mariadb-12.3.3-source.tar.gz'
with tarfile.open(archive) as a:
 members=[m for m in a.getmembers() if m.name.endswith('/mysql-test/std_data/unicode/allkeys1400.txt')];assert len(members)==1
 data=a.extractfile(members[0]).read();(t/'allkeys1400.txt').write_bytes(data)
start=time.monotonic()
with (t/'config/ctype-uca1400data.h').open('wb') as f:subprocess.run([str(t/'uca-dump'),'--name-prefix=uca1400','--levels=3',str(t/'allkeys1400.txt')],stdout=f,check=True)
(w/'evidence/uca-data.json').write_text(json.dumps({'generator':'unmodified pinned strings/uca-dump.c','input_sha256':hashlib.sha256(data).hexdigest(),'generated_sha256':hashlib.sha256((t/'config/ctype-uca1400data.h').read_bytes()).hexdigest(),'wall_seconds':time.monotonic()-start},indent=2)+'\n')
c=(u/'strings/ctype-uca.c').read_text();print(c[c.index('my_uca_2bytes_item_is_applicable')-60:c.index('my_uca_2bytes_item_is_applicable')+80]);print('weightcpy',c[c.index('my_uca_weight_cpy')-65:c.index('my_uca_weight_cpy')+400]);print('block helpers',c[ c.index('my_uca_2bytes_item_is_applicable')-60:c.index('my_uca_level_booster_alloc')-40].count('\n'))
