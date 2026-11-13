from pathlib import Path
import subprocess,sys,json,time
import argparse
parser=argparse.ArgumentParser();parser.add_argument('--workspace',type=Path,required=True);w=parser.parse_args().workspace.resolve();sys.path.insert(0,str(w/'candidate/python'))
import mariamem,mysql.connector
for variant in ['baseline','candidate']:
 with mariamem.start(host_binary=str(w/'artifacts'/(variant+'-host'))) as db:
  with mysql.connector.connect(**db.connection_info(),use_pure=True,autocommit=True) as c:
   with c.cursor(prepared=True) as q:
    for _ in range(10):q.execute("SELECT REPEAT(CAST('x' AS BINARY), ?) AS payload",(65536,));assert q.fetchall()==[(b'x'*65536,)]
    profile=w/'evidence'/(variant+'-sample.txt')
    with (w/'evidence'/(variant+'-sample-command.txt')).open('w') as log:
     sampler=subprocess.Popen(['sample',str(db._session._process.pid),'5','1','-file',str(profile)],stdout=log,stderr=subprocess.STDOUT)
     calls=0
     while sampler.poll() is None:q.execute("SELECT REPEAT(CAST('x' AS BINARY), ?) AS payload",(65536,));assert q.fetchall()==[(b'x'*65536,)];calls+=1
     assert sampler.returncode==0
     print(variant,calls,flush=True)
