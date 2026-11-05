from pathlib import Path
import tarfile,json
w=Path('.');r=w/'worktree';lock=json.loads((r/'release/inputs.lock.json').read_text());pin=next(x for x in lock['inputs'] if x['name']=='mariadb-12.3.3');a=r/'build/downloads'/pin['file']
with tarfile.open(a) as tar:
 for m in tar:
  rel='/'.join(Path(m.name).parts[1:])
  if rel in ['sql/net_serv.cc','sql/transaction.h','sql/transaction.cc','sql/sql_class.cc','libmysqld/lib_sql.cc','wasm/lite4mariadb.c']:
   p=w/'temp/inspect'/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(tar.extractfile(m).read())
