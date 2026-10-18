"""Record native/guest errno and actual connection health without relaxing oracle."""
import argparse,json
from pathlib import Path
import mysql.connector
p=argparse.ArgumentParser();p.add_argument('--port',type=int);p.add_argument('--host');p.add_argument('--output',required=True);a=p.parse_args()
def probe(port):
 out=[]
 for pure in (True,False):
  c=mysql.connector.connect(host='127.0.0.1',port=port,user='root',database='test',use_pure=pure,autocommit=True,connection_timeout=10,read_timeout=15)
  d=dict(pure=pure)
  try:
   q=c.cursor(prepared=True)
   try:q.execute('SELEC broken ?',(1,))
   except mysql.connector.Error as e:d.update(errno=e.errno,sqlstate=e.sqlstate,message=str(e),original_1064_oracle='PASS' if e.errno==1064 else 'FAIL')
   else:d.update(original_1064_oracle='FAIL',error='syntax accepted')
   text=c.cursor();text.execute('SELECT 1');d['next_select']=text.fetchone();text.close()
   q.close()
  except Exception as e:d['post_error_exception']=repr(e)
  finally:c.close()
  out.append(d)
 return out
if a.host:
 import mariamem
 with mariamem.start(host_binary=a.host) as db:results=probe(db.connection_info()['port'])
else:results=probe(a.port)
Path(a.output).write_text(json.dumps(results,indent=2)+'\n');print(json.dumps(results,indent=2))
