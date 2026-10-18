"""Actual default connector mode and ordinary %s parameter markers."""
import argparse,json
from pathlib import Path
import mysql.connector
p=argparse.ArgumentParser();p.add_argument('--port',type=int);p.add_argument('--host');p.add_argument('--output',required=True);a=p.parse_args()
def run(port):
 with mysql.connector.connect(host='127.0.0.1',port=port,user='root',database='test',connection_timeout=10,read_timeout=15) as c:
  q=c.cursor(prepared=True);q.execute('SELECT %s, %s, %s',(17,'日本語',None));row=q.fetchone();assert row==(17,'日本語',None),row;kind=type(q).__name__;assert 'Prepared' in kind;q.close();return dict(result='PASS',connection_type=type(c).__name__,cursor_type=kind,row=row,explicit_use_pure=False,explicit_client_flags=False)
if a.host:
 import mariamem
 with mariamem.start(host_binary=a.host) as db:result=run(db.connection_info()['port'])
else:result=run(a.port)
Path(a.output).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
