"""Bounded Python SDK A/B; libproc observes only the explicit host child PID."""
import argparse,ctypes,json,os,resource,time
from pathlib import Path
import pymysql,mariamem
class Usage(ctypes.Structure):
 _fields_=[('uuid',ctypes.c_ubyte*16)]+[(x,ctypes.c_uint64) for x in ['user','system','idle','interrupt','pageins','wired','rss','footprint','start','exit']]
lib=ctypes.CDLL('/usr/lib/libproc.dylib');lib.proc_pid_rusage.argtypes=[ctypes.c_int,ctypes.c_int,ctypes.c_void_p];lib.proc_pid_rusage.restype=ctypes.c_int

class Timebase(ctypes.Structure):
 _fields_=[('numer',ctypes.c_uint32),('denom',ctypes.c_uint32)]
clocklib=ctypes.CDLL('/usr/lib/libSystem.B.dylib');tb=Timebase();assert clocklib.mach_timebase_info(ctypes.byref(tb))==0 and tb.denom

def usage(pid):
 u=Usage();assert lib.proc_pid_rusage(pid,0,ctypes.byref(u))==0
 return {'cpu_ns':(u.user+u.system)*tb.numer//tb.denom,'rss_bytes':u.rss,'footprint_bytes':u.footprint,'pageins':u.pageins}
def connect(db):return pymysql.connect(**db.connection_info(),autocommit=True,charset='utf8mb4')
def query(c,sql):
 with c.cursor() as q:q.execute(sql);return q.fetchall()
VALUES=['',' ','a','A','a ','a  ','á','a\u0301','ä','Ä','ß','ss','æ','ae','ch','cH','café','cafe','🙂','🍣','東京','大阪','ქართული','ไทย','İ','i','ı','I','K','K','x\x00y','x','é','e\u0301']
def contractions(c):
 pairs=[('h','ch'),('ch','i'),('ch','cH'),('a','a '),('á','a'),('é','e\u0301'),('เก','กเ'),('แก','เก')]
 out={}
 for coll in ['utf8mb4_uca1400_ai_ci','utf8mb4_uca1400_czech_ai_ci']:
  values=[]
  with c.cursor() as q:
   for a,b in pairs:
    q.execute(f'SELECT STRCMP(_utf8mb4%s COLLATE {coll},_utf8mb4%s COLLATE {coll})',(a,b));values.append(q.fetchone()[0])
  out[coll]=values
 return out
def semantic(c):
 out={}
 for encoding in ['utf8mb4','utf8mb3']:
  vals=[v for v in VALUES if encoding=='utf8mb4' or all(ord(x)<=65535 for x in v)]+[None]
  query(c,f'CREATE TABLE sem_{encoding}(id INT PRIMARY KEY,v VARCHAR(100) CHARACTER SET {encoding} COLLATE {encoding}_uca1400_ai_ci) ENGINE=InnoDB')
  with c.cursor() as q:q.executemany(f'INSERT INTO sem_{encoding} VALUES(%s,%s)',list(enumerate(vals)))
  table='sem_'+encoding
  out[encoding]={'ordered':query(c,f'SELECT id,HEX(v) FROM {table} ORDER BY v,id'),'groups':query(c,f'SELECT MIN(id),COUNT(*) FROM {table} GROUP BY v ORDER BY MIN(id)'),'pairs':query(c,f'SELECT a.id,b.id,STRCMP(a.v,b.v),(a.v=b.v),(a.v<b.v) FROM {table} a CROSS JOIN {table} b ORDER BY a.id,b.id'),'weights':query(c,f'SELECT id,HEX(WEIGHT_STRING(v)) FROM {table} ORDER BY id')}
  query(c,f'CREATE TABLE uniq_{encoding}(v VARCHAR(100) CHARACTER SET {encoding} COLLATE {encoding}_uca1400_ai_ci UNIQUE) ENGINE=InnoDB')
  codes=[]
  for v in vals:
   try:
    with c.cursor() as q:q.execute(f'INSERT INTO uniq_{encoding} VALUES(%s)',(v,))
    codes.append(0)
   except pymysql.err.IntegrityError as exc:
    assert exc.args[0]==1062;codes.append(1062)
  out[encoding]['unique_insert_errno']=codes
 out['contractions']=contractions(c)
 return out

def seed(c):
 for name in ['ascii','mixed']:
  query(c,f'CREATE TABLE perf_{name}(id INT PRIMARY KEY,v VARCHAR(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_uca1400_ai_ci) ENGINE=InnoDB')
  rows=[(i,('common-prefix-abcdefghijklmnop-' if name=='ascii' else VALUES[8+(i%20)]+'-共同-prefix-')+f'{i:04d}') for i in range(1000)]
  with c.cursor() as q:q.executemany(f'INSERT INTO perf_{name} VALUES(%s,%s)',rows)
 query(c,'CREATE TABLE isolation_probe(id INT PRIMARY KEY) ENGINE=InnoDB');query(c,'INSERT INTO isolation_probe VALUES(1)')
def perf_sql(name):
 return f"SELECT SUM(STRCMP(v,_utf8mb4'common-prefix-abcdefghijklmnop-0500' COLLATE utf8mb4_uca1400_ai_ci)) FROM perf_{name}"
def main(a):
 out={'result':'FAIL','mode':a.mode,'children':[],'held':[],'cleanup':{},'query_repetitions':20}
 if a.mode=='native':
  c=pymysql.connect(host='127.0.0.1',port=a.port,user='root',database='test',autocommit=True,charset='utf8mb4')
  try:
   version=query(c,'SELECT VERSION()')[0][0];assert version.startswith('12.3.3-');out['version']=version;out['semantic']=semantic(c);seed(c);out['perf_expected']={n:str(query(c,perf_sql(n))[0][0]) for n in ['ascii','mixed']};out['result']='PASS'
  finally:c.close()
  return out
 db=None;snapshot=None;children=[];session=None;error=None
 try:
  begin=time.perf_counter_ns();db=mariamem.start(host_binary=a.host);session=db._session;pid=session._process.pid
  with connect(db) as c:
   out['version']=query(c,'SELECT VERSION()')[0][0]
   if a.mode=='semantic':out['semantic']=semantic(c)
   else:seed(c)
  db.wait_disconnected();snapshot=db.snapshot(max_forks=4);out['prepare_wall_ns']=time.perf_counter_ns()-begin;assert snapshot.max_forks==4
  out['host_pid']=pid;out['held'].append({'children':0,**usage(pid)})
  for i in range(1 if a.mode=='semantic' else 4):
   before=usage(pid);start=time.perf_counter_ns();child=snapshot.fork(host_binary=a.host);wall=time.perf_counter_ns()-start;after=usage(pid);children.append(child)
   assert child._session is session
   row={'ordinal':i,'fork_wall_ns':wall,'fork_cpu_ns':after['cpu_ns']-before['cpu_ns'],'rss_after_fork_bytes':after['rss_bytes']}
   if a.mode=='semantic':
    with connect(child) as c:
     for enc in ['utf8mb4','utf8mb3']:
      table='sem_'+enc;want=out['semantic'][enc]
      assert query(c,f'SELECT id,HEX(v) FROM {table} ORDER BY v,id')==want['ordered']
      assert query(c,f'SELECT MIN(id),COUNT(*) FROM {table} GROUP BY v ORDER BY MIN(id)')==want['groups']
      assert query(c,f'SELECT a.id,b.id,STRCMP(a.v,b.v),(a.v=b.v),(a.v<b.v) FROM {table} a CROSS JOIN {table} b ORDER BY a.id,b.id')==want['pairs']
      assert query(c,f'SELECT id,HEX(WEIGHT_STRING(v)) FROM {table} ORDER BY id')==want['weights']
      try:
       with c.cursor() as q:q.execute(f"INSERT INTO uniq_{enc} VALUES('a')")
      except pymysql.err.IntegrityError as exc:assert exc.args[0]==1062
      else:raise AssertionError('child UNIQUE failed')
     assert contractions(c)==out['semantic']['contractions']
    child.wait_disconnected();row['oracle']=True
   if a.mode!='semantic':
    sql_begin=time.perf_counter_ns()
    with connect(child) as c:
     first_read_begin=time.perf_counter_ns()
     expected=2 if a.negative else 1;assert query(c,'SELECT COUNT(*) FROM isolation_probe')[0][0]==expected,'seed oracle'
     row['first_read_wall_ns']=time.perf_counter_ns()-first_read_begin
     query(c,f'INSERT INTO isolation_probe VALUES({i+10})');assert query(c,'SELECT COUNT(*) FROM isolation_probe')[0][0]==2
     row['sql']={}
     for name in ['ascii','mixed']:
      value=query(c,perf_sql(name))[0][0];u=usage(pid);t=time.perf_counter_ns()
      for k in range(20):assert query(c,perf_sql(name))[0][0]==value
      elapsed=time.perf_counter_ns()-t;v=usage(pid);row['sql'][name]={'result':str(value),'wall_ns':elapsed,'host_cpu_ns':v['cpu_ns']-u['cpu_ns']}
    child.wait_disconnected();row['sql_total_wall_ns']=time.perf_counter_ns()-sql_begin;row['oracle']=True
   out['children'].append(row)
   if len(children) in [1,2,4]:out['held'].append({'children':len(children),**usage(pid)})
  out['result']='PASS'
 except Exception as exc:error=exc;out['error']=type(exc).__name__+': '+str(exc)
 finally:
  errors=[]
  for c in reversed(children):
   try:c.close()
   except Exception as ex:errors.append(str(ex))
  if snapshot:
   try:snapshot.close()
   except Exception as ex:errors.append(str(ex))
  if db:
   try:db.close()
   except Exception as ex:errors.append(str(ex))
  if session:out['cleanup']={'refs':session._refs,'process_exit':session._process.poll(),'reaped':session._reaped.is_set(),'root_exists':session.root.exists()}
  out['cleanup_errors']=errors
  if errors or (session and (session._refs!=0 or session._process.poll()!=0 or session.root.exists())):out['result']='FAIL';out['error']=out.get('error','')+' cleanup oracle'
 return out
p=argparse.ArgumentParser();p.add_argument('--mode',choices=['native','semantic','measure'],required=True);p.add_argument('--host');p.add_argument('--port',type=int);p.add_argument('--negative',action='store_true');a=p.parse_args();r=main(a);print(json.dumps(r,ensure_ascii=False));raise SystemExit(0 if r['result']=='PASS' else 1)
