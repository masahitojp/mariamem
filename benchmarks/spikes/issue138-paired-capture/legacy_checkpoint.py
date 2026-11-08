"""Matched finite workload through the legacy route; no timing ranking."""
import json,os,time
import mariamem,pymysql
host=os.environ['MARIAMEM_TEST_HOST']
def observe(db,stage):
 state=db.status();print(json.dumps({'event':'ISSUE138_OBSERVE','time_ns':time.time_ns(),'stage':stage,'state':state}),flush=True);return state
with mariamem.start(host_binary=host) as root:
 c=pymysql.connect(**root.connection_info(),autocommit=True)
 with c.cursor() as q:
  q.execute('SET GLOBAL innodb_log_file_size=4194304');q.execute('SET GLOBAL innodb_log_archive=ON')
  q.execute('SELECT @@GLOBAL.innodb_log_archive,@@GLOBAL.innodb_log_file_size');assert q.fetchone()==(1,4194304)
  def status(name):q.execute("SHOW GLOBAL STATUS LIKE %s",(name,));return int(q.fetchone()[1])
  start=status('Innodb_lsn_current');q.execute('CREATE TABLE issue128_checkpoint(id INT PRIMARY KEY,v LONGBLOB) ENGINE=InnoDB')
  for i in range(256):q.execute("INSERT INTO issue128_checkpoint VALUES(%s,REPEAT('x',65536))",(i,))
  end=status('Innodb_lsn_current');assert end>start+2*4194304
  q.execute('SET GLOBAL innodb_log_archive=OFF');checkpoint=status('Innodb_lsn_last_checkpoint');assert checkpoint>start
  q.execute('SELECT COUNT(*),SUM(OCTET_LENGTH(v)) FROM issue128_checkpoint');assert tuple(map(int,q.fetchone()))==(256,16777216)
  print(json.dumps({'event':'ISSUE138_ARCHIVE','start':start,'end':end,'checkpoint':checkpoint,'rows':256,'bytes':16777216}),flush=True)
 c.close();observe(root,'close')
 try:root.wait_disconnected(timeout=5)
 except BaseException:observe(root,'drain-timeout');raise
 assert observe(root,'drain-complete')['active_connections']==0
 try:baseline=root.snapshot()
 except BaseException:observe(root,'capture-rejection');raise
 with baseline:
  with baseline.fork(host_binary=host) as child,baseline.fork(host_binary=host) as sibling:
   with pymysql.connect(**child.connection_info(),autocommit=True) as a,pymysql.connect(**sibling.connection_info(),autocommit=True) as b:
    with a.cursor() as q:
     q.execute("SELECT COUNT(*),SUM(OCTET_LENGTH(v)),SUM(id),SUM(v != REPEAT('x',65536)) FROM issue128_checkpoint");assert tuple(map(int,q.fetchone()))==(256,16777216,32640,0)
     q.execute("INSERT INTO issue128_checkpoint VALUES(999,'private')")
    with b.cursor() as q:q.execute('SELECT COUNT(*) FROM issue128_checkpoint');assert q.fetchone()==(256,)
 print('ISSUE138_PAIRED legacy archive/drain/capture/restore/isolation PASS',flush=True)
