"""Real Python API-shaped CRUD, same SQL in all three fresh-process modes."""
import argparse
import contextlib
import json
import os
from pathlib import Path
import resource
import sys
import tempfile
import time
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'python'))
import mariamem
import pymysql
import adapter


def connect(db):return pymysql.connect(**db.connection_info(),autocommit=False,charset='utf8mb4')
def query(c,sql,args=None):
    with c.cursor() as cur:
        cur.execute(sql,args)
        return cur.fetchall()
def value(c,q):return query(c,q)[0][0]
def disconnect(db,c):c.close();db.wait_disconnected()
def scratch():
    paths=list(Path(tempfile.gettempdir()).rglob('*'))
    return {'files':sum(p.is_file() for p in paths),'dirs':sum(p.is_dir() for p in paths),'bytes':sum(p.stat().st_size for p in paths if p.is_file())}

def workflow(args):
    out=Path(args.output);times={};res={};excluded=0
    result={'mode':args.mode,'rows':args.rows,'resources_enabled':args.resources,'times_ms':times,'resources':res}
    if args.mode!='control':adapter.install(args.mode)
    binary=args.host if args.mode=='control' else args.broker
    def timed(name,fn):
        at=time.perf_counter_ns();x=fn();times[name]=(time.perf_counter_ns()-at)/1e6;return x
    def observe(name,obj):
        nonlocal excluded
        if args.resources:
            at=time.perf_counter_ns()
            if args.mode!='control':res[name]=obj._session.rpc('stats')
            excluded+=time.perf_counter_ns()-at
    assert scratch()['files']==0 and scratch()['dirs']==0
    begin=time.perf_counter_ns()
    with timed('setup/start',lambda:mariamem.start(host_binary=binary)) as db:
        result['pids']=[db.diagnostics['host_pid']]
        def prepare():
            c=connect(db)
            try:
                result['guest_version']=value(c,'SELECT VERSION()');assert result['guest_version'].startswith('12.3.3')
                query(c,'CREATE TABLE users (id INT PRIMARY KEY, email VARCHAR(128) NOT NULL UNIQUE, status INT NOT NULL, payload TEXT) ENGINE=InnoDB')
                query(c,'CREATE TABLE orders (id INT PRIMARY KEY, user_id INT NOT NULL, amount INT NOT NULL, KEY(user_id), FOREIGN KEY(user_id) REFERENCES users(id)) ENGINE=InnoDB')
                payload='x'*(256 if args.rows==100 else 1024)
                with c.cursor() as cur:
                    for lo in range(1,args.rows+1,500):cur.executemany('INSERT INTO users VALUES (%s,%s,%s,%s)',[(i,f'u{i}@example.test',0,payload) for i in range(lo,min(lo+500,args.rows+1))])
                    for lo in range(1,args.rows+1,500):cur.executemany('INSERT INTO orders VALUES (%s,%s,%s)',[(i,i,10) for i in range(lo,min(lo+500,args.rows+1))])
                c.commit();assert value(c,'SELECT COUNT(*) FROM users')==args.rows
            finally:disconnect(db,c)
        timed('setup/migrate-seed',prepare);observe('after-seed',db)
        with timed('setup/snapshot',db.snapshot) as baseline:
            assert db.closed
            observe('after-snapshot',baseline)
            at=time.perf_counter_ns();result['tmp_after_snapshot']=scratch()
            if args.mode=='heap':
                assert result['tmp_after_snapshot']['files']==0
                result['heap_stats']=baseline.heap_stats
            excluded+=time.perf_counter_ns()-at
            for name in ['first','second']:
                with timed(name+'/startup',baseline.fork) as child:
                    result['pids'].append(child.diagnostics['host_pid'])
                    observe(name+'-started',child)
                    c=timed(name+'/connect',lambda:connect(child))
                    def crud():
                        assert value(c,'SELECT COUNT(*) FROM users')==args.rows
                        assert value(c,'SELECT status FROM users WHERE id=1')==0
                        if name=='first':
                            query(c,'INSERT INTO users VALUES (%s,%s,0,%s)',(args.rows+1,'created@example.test','new'))
                            query(c,'INSERT INTO orders VALUES (%s,%s,10)',(args.rows+1,args.rows+1));c.commit()
                            assert value(c,'SELECT COUNT(*) FROM users')==args.rows+1
                        else:
                            assert value(c,"SELECT COUNT(*) FROM users WHERE email='created@example.test'")==0
                            query(c,'UPDATE users SET status=2 WHERE id=1');c.commit();assert value(c,'SELECT status FROM users WHERE id=1')==2
                            query(c,'DELETE FROM orders WHERE id=1');c.rollback();assert value(c,'SELECT COUNT(*) FROM orders')==args.rows
                            query(c,'DELETE FROM orders WHERE id=1');c.commit();assert value(c,'SELECT COUNT(*) FROM orders')==args.rows-1
                    timed(name+'/crud',crud);timed(name+'/disconnect',lambda:disconnect(child,c));timed(name+'/close',child.close)
                    observe(name+'-closed',baseline)
            if args.mode=='heap':
                at=time.perf_counter_ns();baseline._session.rpc('verify',baseline.id);excluded+=time.perf_counter_ns()-at
            timed('baseline/close',baseline.close)
    result['whole_ms']=(time.perf_counter_ns()-begin-excluded)/1e6
    result['tmp_after_close']=scratch();assert result['tmp_after_close']['files']==0 and result['tmp_after_close']['dirs']==0
    if args.mode=='control':assert len(set(result['pids']))==3
    else:assert len(set(result['pids']))==1 and all(s.done and s.proc.poll()==0 for s in adapter.SESSIONS)
    if args.resources:
        result['host_metrics']=[json.loads(p.read_text()) for p in sorted(Path(os.environ['MARIAMEM_SPIKE_METRICS']).glob('*.json'))]
        assert result['host_metrics']
        result['python_maxrss_raw']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    result['status']='PASS';result['checks']=['version','CRUD-commit-rollback','sibling-isolation','source-consumed','host-pid-ownership','cleanup']
    out.write_text(json.dumps(result,indent=2)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--mode',choices=['control','file','heap'],required=True);p.add_argument('--host',required=True);p.add_argument('--broker',required=True);p.add_argument('--rows',type=int,default=100);p.add_argument('--resources',action='store_true');p.add_argument('--output',required=True);workflow(p.parse_args())
