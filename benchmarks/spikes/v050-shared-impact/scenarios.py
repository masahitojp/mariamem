"""Same bounded ordinary scenarios on control, observer-off, observer-on hosts."""
import argparse,concurrent.futures,json,os,time,threading,traceback
from pathlib import Path
import mariamem,pymysql
p=argparse.ArgumentParser();p.add_argument('host',type=Path);p.add_argument('out',type=Path);p.add_argument('--observe',action='store_true');p.add_argument('--enable-ahi',action='store_true');a=p.parse_args();a.out.mkdir(parents=True)
r={'host':str(a.host.resolve()),'observe':a.observe,'result':'FAIL','cases':[]}
def conn(**kw):return pymysql.connect(**info,read_timeout=30,write_timeout=30,**kw)
def sql(c,q,args=None):
 with c.cursor() as cur:cur.execute(q,args);return cur.fetchall()
def case(name,fn):
 t=time.monotonic();value=fn();r['cases'].append({'name':name,'seconds':time.monotonic()-t,'result':'PASS','value':value})
try:
 if a.observe:os.environ['MARIAMEM_IMPACT_OUTPUT']=str((a.out/'events.json').resolve())
 t=time.monotonic();db=mariamem.start(host_binary=a.host.resolve(),log_path=a.out/'host.log',shutdown_timeout=60);info=db.connection_info();r['startup_seconds']=time.monotonic()-t
 with conn(autocommit=True) as c:
  r['version']=sql(c,'SELECT VERSION()')[0][0];r['ahi_initial']=sql(c,"SHOW VARIABLES LIKE 'innodb_adaptive_hash_index'")
  if a.enable_ahi:sql(c,'SET GLOBAL innodb_adaptive_hash_index=ON')
  r['ahi_active']=sql(c,"SHOW VARIABLES LIKE 'innodb_adaptive_hash_index'")
  sql(c,'CREATE TABLE impact_rows(id INT PRIMARY KEY,v INT NOT NULL,k INT NOT NULL, KEY idx_k(k)) ENGINE=InnoDB')
  with c.cursor() as cur:cur.executemany('INSERT INTO impact_rows VALUES(%s,0,%s)',[(i,i%17) for i in range(1,257)])
 def independent():
  gate=threading.Barrier(4)
  def worker(i):
   with conn(autocommit=False) as c:
    gate.wait()
    for step in range(30):
     sql(c,'UPDATE impact_rows SET v=v+1 WHERE id=%s',(i+1,));assert sql(c,'SELECT COUNT(*) FROM impact_rows WHERE k=%s',(step%17,))[0][0]>0;c.commit()
   return 30
  with concurrent.futures.ThreadPoolExecutor(4) as ex:n=sum(ex.map(worker,range(4)))
  with conn(autocommit=True) as c:values=sql(c,'SELECT id,v FROM impact_rows WHERE id<=4 ORDER BY id')
  assert values==((1,30),(2,30),(3,30),(4,30)),values
  return {'workers':4,'commits':n,'values':values}
 case('four_connections_read_write',independent)
 def contention():
  holder=conn(autocommit=False);ready=threading.Event();sql(holder,'UPDATE impact_rows SET v=v+10 WHERE id=10')
  def waiter():
   with conn(autocommit=False) as c:ready.set();sql(c,'UPDATE impact_rows SET v=v+1 WHERE id=10');c.commit()
  with concurrent.futures.ThreadPoolExecutor(1) as ex:
   f=ex.submit(waiter);ready.wait();time.sleep(.05);waiting=not f.done();holder.rollback();f.result(timeout=30)
  holder.close()
  with conn(autocommit=True) as c:value=sql(c,'SELECT v FROM impact_rows WHERE id=10')[0][0]
  assert value==1,value
  return {'blocked_before_rollback':waiting,'final':value}
 case('competing_update_rollback_commit',contention)
 def snapshots():
  with conn(autocommit=False) as reader,conn(autocommit=False) as writer:
   sql(reader,'SET TRANSACTION ISOLATION LEVEL REPEATABLE READ');before=sql(reader,'SELECT v FROM impact_rows WHERE id=20')[0][0]
   sql(writer,'UPDATE impact_rows SET v=v+1 WHERE id=20');writer.commit();during=sql(reader,'SELECT v FROM impact_rows WHERE id=20')[0][0];reader.commit();after=sql(reader,'SELECT v FROM impact_rows WHERE id=20')[0][0];reader.rollback()
   assert before==during==0 and after==1,(before,during,after)
   return [before,during,after]
 case('readview_commit_visibility',snapshots)
 def churn():
  def worker(i):
   for j in range(8):
    with conn(autocommit=False) as c:
     assert sql(c,'SELECT COUNT(*) FROM impact_rows')[0][0]==256;sql(c,'UPDATE impact_rows SET v=v+1 WHERE id=%s',(100+i,));c.rollback()
   return 8
  with concurrent.futures.ThreadPoolExecutor(4) as ex:n=sum(ex.map(worker,range(4)))
  return {'connections':n,'all_rolled_back':True}
 case('parallel_connection_start_end',churn)
 def indexed():
  def worker(i):
   with conn(autocommit=True) as c:
    for j in range(250):
     assert sql(c,'SELECT id FROM impact_rows WHERE id=%s',((j%256)+1,))
     assert sql(c,'SELECT id FROM impact_rows FORCE INDEX(idx_k) WHERE k=%s ORDER BY id',(j%17,))
   return 250
  with concurrent.futures.ThreadPoolExecutor(4) as ex:n=sum(ex.map(worker,range(4)))
  return {'indexed_queries':n}
 case('parallel_repeated_index_reads',indexed)
 db.wait_disconnected(timeout=10);t=time.monotonic();db.close();r['close_seconds']=time.monotonic()-t;r['result']='PASS'
except BaseException as e:r['error']=repr(e);r['traceback']=traceback.format_exc();raise
finally:(a.out/'results.json').write_text(json.dumps(r,indent=2)+'\n')
