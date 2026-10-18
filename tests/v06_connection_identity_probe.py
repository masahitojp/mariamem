"""Observe greeting identity versus engine identity after capability negotiation."""
import argparse,json
from pathlib import Path
import mysql.connector
p=argparse.ArgumentParser();p.add_argument('--port',type=int);p.add_argument('--host');p.add_argument('--output',required=True);a=p.parse_args()
def run(port):
 out=[]
 for pure in (True,False):
  with mysql.connector.connect(host='127.0.0.1',port=port,user='root',database='test',use_pure=pure,connection_timeout=10,read_timeout=15) as c:
   greeting=c.connection_id;q=c.cursor();q.execute('SELECT CONNECTION_ID()');engine=q.fetchone()[0];q.close();out.append(dict(pure=pure,greeting_connection_id=greeting,sql_connection_id=engine,result='PASS' if greeting==engine else 'FAIL'))
 return out
if a.host:
 import mariamem
 with mariamem.start(host_binary=a.host) as db:results=run(db.connection_info()['port'])
else:results=run(a.port)
Path(a.output).write_text(json.dumps(results,indent=2)+'\n');print(json.dumps(results,indent=2))
