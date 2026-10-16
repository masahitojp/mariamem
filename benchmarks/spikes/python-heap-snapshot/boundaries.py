"""Bounded lifecycle/failure evidence, separate from performance cases."""
import argparse
import concurrent.futures
import json
import os
from pathlib import Path
import threading
import time
from workflow import mariamem,adapter,connect,query,value,disconnect,scratch

p=argparse.ArgumentParser();p.add_argument('--broker',required=True);p.add_argument('--output',required=True);args=p.parse_args();adapter.install('heap');checks=[];details={}
def start():return mariamem.start(host_binary=args.broker)
def seed():
 d=start();c=connect(d);query(c,'CREATE TABLE items(id INT PRIMARY KEY,v INT) ENGINE=InnoDB');query(c,'INSERT INTO items VALUES(1,10)');c.commit();disconnect(d,c);return d
def scalar(db):
 c=connect(db)
 try:return value(c,'SELECT v FROM items')
 finally:disconnect(db,c)
def clean():
 assert scratch()['files']==0 and scratch()['dirs']==0,scratch()
 assert all(s.done and s.proc.poll() is not None for s in adapter.SESSIONS)

# Transaction rejection; successful Snapshot consumes the source only.
d=seed();c=connect(d);query(c,'UPDATE items SET v=11')
try:d.snapshot();raise AssertionError('transaction accepted')
except mariamem.TransactionActive:pass
assert not d.closed and value(c,'SELECT v FROM items')==11;c.rollback();disconnect(d,c);base=d.snapshot();assert d.closed
try:base._session.rpc('fork',999999);raise AssertionError('invalid handle accepted')
except mariamem.HostError as e:assert e.code=='closed'
a,b=base.fork(),base.fork();assert len({a.diagnostics['host_pid'],b.diagnostics['host_pid']})==1
assert a.connection_info()['port']!=b.connection_info()['port']
base.close()
try:base.fork();raise AssertionError('closed snapshot forked')
except ValueError:pass
checks+=['transaction-rejection-source-usable','source-consumed','closed-and-invalid-handles-rejected','one-host-distinct-db-endpoints']
# Two SQL connections in one DB; an ordinary SQL error must not kill its peers.
c1,c2=connect(a),connect(a);assert value(c1,'SELECT v FROM items')==value(c2,'SELECT v FROM items')==10
try:query(c1,'INSERT INTO items VALUES(1,99)');raise AssertionError('duplicate accepted')
except Exception as e:
 assert getattr(e,'args',(None,))[0]==1062,e
c1.rollback();assert value(c2,'SELECT v FROM items')==10
c1.close();disconnect(a,c2);assert scalar(b)==10
checks+=['two-connections-one-db','SQL-error-keeps-host-and-other-db-usable']
c=connect(a);query(c,'UPDATE items SET v=20');c.commit();disconnect(a,c);derived=a.snapshot();third=derived.fork();derived.close();assert scalar(third)==20 and scalar(b)==10
third.close();assert scalar(b)==10;b.close();a.close();d.close();clean()
checks+=['parent-close-live-children','derived-baseline-close-live-child','one-db-close-keeps-sibling-alive']
# Concurrent SQL in separate runtimes, then simultaneous Fork requests through the controller.
d=seed();base=d.snapshot()
with concurrent.futures.ThreadPoolExecutor(2) as pool:a,b=list(pool.map(lambda _:base.fork(),range(2)))
base.close()
def mutate(pair):
 i,db=pair;c=connect(db)
 for _ in range(10):query(c,'UPDATE items SET v=v+%s',(i+1,));c.commit()
 assert value(c,'SELECT v FROM items')==10+10*(i+1);disconnect(db,c);db.close()
with concurrent.futures.ThreadPoolExecutor(2) as pool:list(pool.map(mutate,enumerate([a,b])))
clean();checks+=['simultaneous-fork-requests-serialized','concurrent-independent-SQL']
# Pre-existing corruption/freeze oracles reached through the new host ownership.
faults=[]
for fault in ['freeze','target_corrupt','owner_corrupt']:
 d=seed()
 try:d._session.rpc('snapshot',d.id,fault=fault);raise AssertionError('fault accepted')
 except mariamem.HostError as e:
  want='injected heap freeze' if fault=='freeze' else 'heap content mismatch'
  assert e.closed and want in str(e),(fault,str(e));faults.append({'fault':fault,'error':str(e),'closed':e.closed})
 d.close();clean()
details['faults']=faults;checks+=['freeze-failure-and-two-corruption-gates']
# Owner EOF (not a force kill) cooperatively shuts down all active runtimes.
d=seed();base=d.snapshot();a,b=base.fork(),base.fork();s=base._session;s.proc.stdin.close();s.proc.wait(timeout=40);s.dispose();assert s.proc.returncode==0
a.close();b.close();base.close();clean();checks+=['owner-EOF-cooperative-all-resource-cleanup']
# Actual host loss: every handle in that lineage fails, independent start survives.
independent=seed();d=seed();base=d.snapshot();a,b=base.fork(),base.fork();s=base._session
assert independent.diagnostics['host_pid']!=a.diagnostics['host_pid']
c=connect(a);pending=[];started=threading.Event()
def wait_request():
 started.set()
 try:a.wait_disconnected(timeout=5);pending.append('unexpected-success')
 except Exception as e:pending.append({'type':type(e).__name__,'code':getattr(e,'code',None),'message':str(e)})
t=threading.Thread(target=wait_request);t.start();started.wait();time.sleep(.05);s.proc.kill();t.join(timeout=10);assert not t.is_alive() and len(pending)==1 and pending[0]['code']=='unusable',pending
assert a.closed and b.closed
try:base.fork();raise AssertionError('dead host forked')
except mariamem.HostError as e:assert e.code=='unusable'
c.close();a.close();b.close();base.close();assert scalar(independent)==10;independent.close()
# SIGKILL cannot run Go's directory cleanup. Record actual residue, then remove
# only empty directories in this test's isolated TMPDIR; do not call it library cleanup.
details['host_loss']={'pending':pending,'returncode':s.proc.returncode,'residue_before_harness_cleanup':scratch(),'unrelated_start_survived':True}
assert scratch()['files']==0
for path in sorted(Path(os.environ['TMPDIR']).rglob('*'),key=lambda p:len(p.parts),reverse=True):path.rmdir()
clean();checks+=['host-loss-invalidates-lineage-wakes-pending','separate-start-survives-host-loss']
Path(args.output).write_text(json.dumps({'status':'PASS','checks':checks,**details},indent=2)+'\n');print('PASS',len(checks),'boundary checks')
