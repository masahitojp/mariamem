#!/usr/bin/env python3
"""Control: independent databases launched from one existing owned executable."""
import argparse,hashlib,json,os
from pathlib import Path
import mariamem,pymysql
p=argparse.ArgumentParser();p.add_argument('--host',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
for k in ('MARIAMEM_NATIVE_DIR','MARIAMEM_RUNTIME'):
 if os.environ.get(k):raise RuntimeError('clear '+k)
exe=a.host.resolve();before=hashlib.sha256(exe.read_bytes()).hexdigest()
with mariamem.start(host_binary=exe) as x, mariamem.start(host_binary=exe) as y:
 conns=[]
 for db,value in ((x,11),(y,22)):
  c=pymysql.connect(**db.connection_info(),autocommit=True);conns.append(c)
  with c.cursor() as q:q.execute('CREATE TABLE isolated(id INT PRIMARY KEY) ENGINE=InnoDB');q.execute('INSERT INTO isolated VALUES(%s)',(value,))
 for c,value in zip(conns,(11,22)):
  with c.cursor() as q:q.execute('SELECT id FROM isolated');assert q.fetchone()==(value,)
 for c in conns:c.close()
 x.close()
 with pymysql.connect(**y.connection_info(),autocommit=True) as c:
  with c.cursor() as q:q.execute('SELECT id FROM isolated');assert q.fetchone()==(22,)
after=hashlib.sha256(exe.read_bytes()).hexdigest();assert before==after
row={'executable_sha256':before,'two_independent_databases':True,'write_schema_isolation':True,'one_close_other_live':True,'executable_unchanged':True}
a.output.write_text(json.dumps(row,indent=2)+'\n');print(json.dumps(row))
