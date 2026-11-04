"""Real TCP ordering and cooperative fatal-path controls for the pipeline spike."""
import contextlib,json,os,struct,sys,time
from pathlib import Path
root=Path.cwd();w=root.parent;e=w/'evidence';host=w/'temp/mariamem-host';sys.path[:0]=[str(root/'python'),str(root/'scripts')]
import mariamem,pymysql
from git_identity import verify_go_binary
import subprocess
source=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();verify_go_binary(root,host,source)
r={'scope':'REAL_TCP_COOPERATIVE_ORDERING_AND_FAILURES','source_commit':source,'read_ahead_limit':1048581,'cases':[]}
def connect(db):return pymysql.connect(**db.connection_info(),autocommit=True,read_timeout=5,write_timeout=5)
def sql(c,q):
 with c.cursor() as cur:cur.execute(q);return cur.fetchall()
def frame(q):
 b=b'\3'+q.encode();n=len(b);return bytes([n&255,n>>8&255,n>>16&255,0])+b
def busy(db):
 until=time.monotonic()+3
 while time.monotonic()<until:
  if db.status()['busy']:return
  time.sleep(.005)
 raise AssertionError('active query not observed')
def unusable(db):
 until=time.monotonic()+5
 while time.monotonic()<until:
  try:state=db.status()
  except mariamem.HostError as err:return {'code':err.code,'closed':err.closed}
  if db.closed:return {'closed':True}
  time.sleep(.01)
 raise AssertionError('failed DB stayed usable')
with mariamem.start(host_binary=host) as db:
 with contextlib.closing(connect(db)) as c:
  sql(c,'CREATE TABLE pipeline_order(n INT)');sql(c,'INSERT INTO pipeline_order VALUES(0)')
  c._write_bytes(frame('UPDATE pipeline_order SET n=n+1+SLEEP(0.1)')+frame('SELECT n FROM pipeline_order'))
  c._next_seq_id=1;c._read_query_result();assert c._result.affected_rows==1
  c._next_seq_id=1;c._read_query_result();assert c._result.rows==((1,),),c._result.rows
  assert sql(c,'SELECT 11')==((11,),)
 r['cases'].append({'name':'serial-side-effects-and-response-order','result':'PASS'})
for mode in ('disconnect-after-queued-input','overflow','timeout-with-queued-input','close-with-queued-input'):
 db=None;c=None
 try:
  with mariamem.start(host_binary=host) as independent:
   db=mariamem.start(host_binary=host,query_timeout=.35 if mode=='timeout-with-queued-input' else 3,shutdown_timeout=1)
   c=connect(db);c._execute_command(3,b'SELECT SLEEP(10)');busy(db)
   if mode=='overflow':
    c._write_bytes(b'x'*1048582)
   else:c._write_bytes(frame('SELECT 999'))
   if mode=='disconnect-after-queued-input':c._force_close();state=unusable(db)
   elif mode=='close-with-queued-input':db.close();assert db.closed;state={'closed':True}
   else:
    try:c._read_query_result()
    except pymysql.Error as err:
     text=str(err);assert 'database instance terminated' in text,text
     if mode=='overflow':assert 'bounded receive buffer' in text,text
     state={'driver_error':err.args[0],'message':text,'state':unusable(db)}
    else:raise AssertionError('fatal path returned a normal result')
   with contextlib.closing(connect(independent)) as good:assert sql(good,'SELECT 2')==((2,),)
   r['cases'].append({'name':mode,'result':'PASS','observation':state,'independent_root':'PASS'})
 except Exception as err:r['cases'].append({'name':mode,'result':'FAIL','error':repr(err)})
 finally:
  if c:c._force_close()
  if db:
   try:db.close()
   except Exception as err:r['cases'][-1]['cleanup_error']=repr(err);r['cases'][-1]['result']='FAIL'
 (e/'transport.json').write_text(json.dumps(r,indent=2)+'\n')
r['summary']={k:sum(x['result']==k for x in r['cases']) for k in ('PASS','FAIL')};(e/'transport.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r),flush=True)
