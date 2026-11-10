"""Fetch selected files at an exact upstream commit; no full source checkout."""
from pathlib import Path
import base64,concurrent.futures,hashlib,json,subprocess,sys
S=Path(__file__).resolve().parents[2];H=Path(__file__).resolve().parent;W=S.parent;T=W/'temp';E=W/'evidence'
sys.path.insert(0,str(S/'scripts'))
from git_identity import require_commit
p=json.loads((H/'plan.json').read_text());require_commit(S,p['source_commit'])
sha=p['mariadb_source_commit'];base='repos/MariaDB/server'
def api(path):return json.loads(subprocess.check_output(['gh','api',path],text=True))
commit=api(base+'/git/commits/'+sha);assert commit['sha']==sha
(E/'upstream-commit.json').write_text(json.dumps(commit,indent=2)+'\n')
files=['libmysqld/lib_sql.cc','sql/mysqld.cc','mysys/charset.c','mysys/charset-def.c','strings/ctype.c','mysys/hash.c','sql/set_var.cc','mysys/my_once.c','mysys/my_rdtsc.c','sql/item_create.cc','sql/json_schema.cc','sql/sql_lex.cc','sql/sql_locale.cc','sql/sql_show.cc','sql/sql_type.cc','include/my_rdtsc.h','sql/sql_class.cc','storage/perfschema/pfs_timer.cc','sql/sql_profile.cc']
def fetch(name):
 v=api(base+'/contents/'+name+'?ref='+sha);assert v['type']=='file' and v['encoding']=='base64'
 b=base64.b64decode(v['content']);assert hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()==v['sha']
 dst=T/'upstream'/name;dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(b)
 return name,dict(sha256=hashlib.sha256(b).hexdigest(),git_blob_sha=v['sha'],size=len(b),url=v['html_url'])
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:rows=dict(pool.map(fetch,files))
(E/'source-files.json').write_text(json.dumps(dict(mariadb_source_commit=sha,product_source_commit=p['source_commit'],files=rows),indent=2)+'\n')
print('Acquired',len(rows),'source files at verified GitHub commit',sha)
