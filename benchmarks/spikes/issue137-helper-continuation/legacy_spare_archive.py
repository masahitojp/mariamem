"""Finite additional branch stimulus; source-prepared, NOT runtime acceptance.

Keep archive ON across checkpoint/idle transition; observe the existing hook.
No engine/hook changes, no capture retry, no checkpoint-as-branch inference.
"""
import hashlib,json,os,threading,time
MARKER='ISSUE138_BRANCH spare_archive'
def wait_branch(db,timeout=5):
 deadline=time.monotonic()+timeout
 while True:
  if db.closed:raise RuntimeError('root died before spare-archive observation')
  logs=db.logs
  if MARKER in logs:return logs
  remaining=deadline-time.monotonic()
  if remaining<=0:raise TimeoutError('positive spare-archive hook absent; checkpoint progress is insufficient')
  # Bounded observation wait, not an idle/capture sleep or capture retry.
  threading.Event().wait(min(0.01,remaining))
def main():
 import mariamem,pymysql
 host=os.environ['MARIAMEM_TEST_HOST']
 def connect(db):return pymysql.connect(**db.connection_info(),autocommit=True)
 def observe(db,stage):
  state=db.status();print(json.dumps({'event':'SPARE_OBSERVE','time_ns':time.time_ns(),'stage':stage,'state':state,'logs':db.logs}),flush=True);return state
 def exact(db):
  h=hashlib.sha256();n=0
  with connect(db) as c:
   with c.cursor(pymysql.cursors.SSCursor) as q:
    q.execute('SELECT id,v FROM issue138_spare ORDER BY id')
    for ident,value in q:
     assert ident==n and value==b'x'*65536,(ident,n,len(value));h.update(ident.to_bytes(4,'little'));h.update(value);n+=1
  db.wait_disconnected(timeout=5);assert n==256,n
  return h.hexdigest()
 with mariamem.start(host_binary=host) as root:
  with connect(root) as c:
   with c.cursor() as q:
    q.execute('SELECT @@GLOBAL.innodb_max_dirty_pages_pct,@@GLOBAL.innodb_max_dirty_pages_pct_lwm,@@GLOBAL.innodb_flush_sync');settings=q.fetchone()
    q.execute('SET GLOBAL innodb_log_file_size=4194304');q.execute('SET GLOBAL innodb_log_archive=ON')
    q.execute('SET GLOBAL innodb_max_dirty_pages_pct_lwm=0');q.execute('SET GLOBAL innodb_max_dirty_pages_pct=0');q.execute('SET GLOBAL innodb_flush_sync=ON')
    q.execute('CREATE TABLE issue138_spare(id INT PRIMARY KEY,v LONGBLOB) ENGINE=InnoDB')
    q.execute("SHOW GLOBAL STATUS LIKE 'Innodb_lsn_current'");start=int(q.fetchone()[1])
    for i in range(256):q.execute("INSERT INTO issue138_spare VALUES(%s,REPEAT('x',65536))",(i,))
    q.execute("SHOW GLOBAL STATUS LIKE 'Innodb_lsn_current'");end=int(q.fetchone()[1]);assert end>start+2*4194304
  # Let the real page cleaner reach idle while archive is still ON.
  root.wait_disconnected(timeout=5);assert observe(root,'archive-on-drained')['active_connections']==0
  try:wait_branch(root,5)
  except BaseException:observe(root,'branch-missing-or-root-failed');raise
  observe(root,'positive-spare-archive')
  with connect(root) as c:
   with c.cursor() as q:
    q.execute('SET GLOBAL innodb_log_archive=OFF')
    q.execute('SET GLOBAL innodb_max_dirty_pages_pct=%s',(settings[0],));q.execute('SET GLOBAL innodb_max_dirty_pages_pct_lwm=%s',(settings[1],));q.execute('SET GLOBAL innodb_flush_sync=%s',(settings[2],))
    q.execute("SHOW GLOBAL STATUS LIKE 'Innodb_lsn_last_checkpoint'");checkpoint=int(q.fetchone()[1]);assert checkpoint>start
  root.wait_disconnected(timeout=5);before=exact(root);observe(root,'pre-capture-drained')
  with root.snapshot() as baseline: # Exactly one capture, no rejected-capture retry.
   with baseline.fork(host_binary=host) as child,baseline.fork(host_binary=host) as sibling:
    assert exact(child)==before and exact(sibling)==before
    with connect(child) as c:
     with c.cursor() as q:q.execute("INSERT INTO issue138_spare VALUES(999,'private')")
    child.wait_disconnected(timeout=5);assert exact(sibling)==before
  print(json.dumps({'event':'SPARE_ARCHIVE_PASS','start':start,'end':end,'checkpoint':checkpoint,'rows':256,'bytes':16777216,'ordered_data_sha256':before,'branch_marker':MARKER}),flush=True)
if __name__=='__main__':main()
