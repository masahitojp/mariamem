"""Bounded Python API workflow; observe hypothetical file-CoW costs, not a backend."""
import argparse
import contextlib
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'python'))
import mariamem
import pymysql

def phase(path, value):
    tmp=path.with_suffix('.new')
    tmp.write_text(value)
    tmp.replace(path)

def campaign(args, mode, rows, repeat, warmup=False):
    label=f'n{rows}-r{repeat}-{mode}'
    out=args.output/label
    out.mkdir()
    phase_file=out/'phase'
    phase(phase_file,'setup/start')
    if mode=='control':
        os.environ.pop('MARIAMEM_COW_MODE',None)
        host=args.control
    else:
        os.environ['MARIAMEM_COW_MODE']=mode
        host=args.observed
    os.environ['MARIAMEM_COW_PHASE_FILE']=str(phase_file)
    os.environ['MARIAMEM_COW_OUT']=str(out)
    result={'mode':mode,'rows':rows,'repeat':repeat,'warmup':warmup,'times_ms':{},'children':[], 'checks':[]}
    def timed(name, fun):
        phase(phase_file,name)
        start=time.perf_counter_ns()
        value=fun()
        result['times_ms'][name]=(time.perf_counter_ns()-start)/1e6
        return value
    def connect(db):
        return pymysql.connect(**db.connection_info(),autocommit=False,charset='utf8mb4')
    def query(c,sql,args=None):
        with c.cursor() as cur:
            cur.execute(sql,args)
            return cur.fetchall()
    begin=time.perf_counter_ns()
    with timed('setup/start',lambda:mariamem.start(host_binary=str(host),log_path=out/'setup.log')) as db:
        result['setup_pid']=db.diagnostics['host_pid']
        def prepare():
            with contextlib.closing(connect(db)) as c:
                version=query(c,'SELECT VERSION()')[0][0]
                assert version.startswith('12.3.3'),version
                result['guest_version']=version
                query(c,'CREATE TABLE users (id INT PRIMARY KEY, email VARCHAR(128) NOT NULL UNIQUE, status INT NOT NULL, payload TEXT) ENGINE=InnoDB')
                query(c,'CREATE TABLE orders (id INT PRIMARY KEY, user_id INT NOT NULL, amount INT NOT NULL, KEY(user_id), FOREIGN KEY(user_id) REFERENCES users(id)) ENGINE=InnoDB')
                payload='x'*(256 if rows==100 else 1024)
                with c.cursor() as cur:
                    for start in range(1,rows+1,500):
                        ids=range(start,min(start+500,rows+1))
                        cur.executemany('INSERT INTO users VALUES (%s,%s,%s,%s)',[(i,f'u{i}@example.test',0,payload) for i in ids])
                    for start in range(1,rows+1,500):
                        ids=range(start,min(start+500,rows+1))
                        cur.executemany('INSERT INTO orders VALUES (%s,%s,%s)',[(i,i,10) for i in ids])
                c.commit()
                assert query(c,'SELECT COUNT(*) FROM users')[0][0]==rows
            db.wait_disconnected()
        timed('setup/migrate-seed',prepare)
        with timed('setup/snapshot',db.snapshot) as baseline:
            result['baseline_manifest']=baseline._manifest
            for child_name in ('first','second'):
                with timed(child_name+'/startup',lambda:baseline.fork(log_path=out/(child_name+'.log'))) as child:
                    result['children'].append({'name':child_name,'pid':child.diagnostics['host_pid']})
                    c=timed(child_name+'/connect',lambda:connect(child))
                    try:
                        def crud():
                            assert query(c,'SELECT COUNT(*) FROM users')[0][0]==rows
                            assert query(c,'SELECT status FROM users WHERE id=1')[0][0]==0
                            if child_name=='first':
                                query(c,'INSERT INTO users VALUES (%s,%s,0,%s)',(rows+1,'created@example.test','new'))
                                query(c,'INSERT INTO orders VALUES (%s,%s,10)',(rows+1,rows+1))
                                c.commit()
                                assert query(c,'SELECT COUNT(*) FROM users')[0][0]==rows+1
                            else:
                                assert query(c,'SELECT COUNT(*) FROM users WHERE email=%s',('created@example.test',))[0][0]==0
                                query(c,'UPDATE users SET status=2 WHERE id=1')
                                c.commit()
                                assert query(c,'SELECT status FROM users WHERE id=1')[0][0]==2
                                query(c,'DELETE FROM orders WHERE id=1')
                                c.rollback()
                                assert query(c,'SELECT COUNT(*) FROM orders')[0][0]==rows
                                query(c,'DELETE FROM orders WHERE id=1')
                                c.commit()
                                assert query(c,'SELECT COUNT(*) FROM orders')[0][0]==rows-1
                            c.commit()
                        timed(child_name+'/crud',crud)
                    finally:
                        timed(child_name+'/disconnect',c.close)
                    timed(child_name+'/close',child.close)
                result['checks'].append(child_name+'-sql-and-isolation-pass')
            result['workflow_ms_before_validation']=(time.perf_counter_ns()-begin)/1e6
            # Verify exact baseline content after both children, outside timed workflow.
            for name,fd,size in baseline._files:
                h=hashlib.sha256();off=0
                while off<size:
                    b=os.pread(fd,min(1024*1024,size-off),off)
                    assert b,(name,off,size)
                    h.update(b);off+=len(b)
                assert h.hexdigest()==baseline._manifest['entries'][name]['sha256'],name
            result['checks'].append('baseline-unchanged-pass')
            timed('baseline/close',baseline.close)
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(label, 'PASS', round(result['workflow_ms_before_validation'],1), flush=True)

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--control',type=Path,required=True)
    p.add_argument('--observed',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--repeats',type=int,default=3)
    p.add_argument('--pilot',action='store_true')
    args=p.parse_args()
    args.control=args.control.resolve();args.observed=args.observed.resolve();args.output=args.output.resolve()
    args.output.mkdir(parents=True,exist_ok=True)
    tools={'python':sys.version,'platform':platform.platform(),'machine':platform.machine(),
           'pymysql':importlib.metadata.version('pymysql'),
           'source_identity':json.loads(subprocess.check_output([sys.executable,str(ROOT/'scripts/git_identity.py'),'--root',str(ROOT),'inspect','HEAD'])),
           'host_sha256':{k:hashlib.sha256(v.read_bytes()).hexdigest() for k,v in [('control',args.control),('observed',args.observed)]}}
    (args.output/'inputs.json').write_text(json.dumps(tools,indent=2)+'\n')
    if args.pilot:
        for mode in ['control','observe','copy-probe']:campaign(args,mode,100,-1,True)
        return
    for n in [100,10000]:
        for rep in range(args.repeats):
            modes=['control','observe','copy-probe']
            for mode in modes[rep%3:]+modes[:rep%3]:campaign(args,mode,n,rep)

if __name__=='__main__':main()
