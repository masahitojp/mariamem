#!/usr/bin/env python3
"""One initialized-image MAP_PRIVATE proof; independent guest processes, not Fork."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).parents[1]/'wasm2go'))
from sql_execution import Guest, workload
from measure_execution import distribution


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--binary', type=Path, required=True)
    p.add_argument('--image', type=Path, required=True)
    p.add_argument('--helper', type=Path, required=True)
    p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--single-runs', type=int, default=10)
    p.add_argument('--group-runs', type=int, default=3)
    a = p.parse_args()
    out = a.output_dir.resolve(); out.mkdir(parents=True, exist_ok=True)
    image = json.loads((a.image/'image.json').read_text())
    def checksum():
        h = hashlib.sha256((a.image/'image.json').read_bytes())
        with (a.image/'memory.bin').open('rb') as f:
            # All captured extents plus representative holes, without faulting 2 GiB.
            for offset in sorted(set(image['offsets']+[536870912,1073741824,2147467264])):
                f.seek(offset); h.update(offset.to_bytes(8,'little')); h.update(f.read(image['page_size']))
        return h.hexdigest()
    report = {'source_sha':'965da8c9d2702e6ecdd830d684e8463d31e94311',
              'boundary':'initialized thread-free image -> fresh runtime, threads, MemFS and MariaDB; no prepared DB clone or wire/trust',
              'image_resident_bytes':len(image['offsets'])*image['page_size'],
              'image_virtual_bytes':image['length'], 'base_before':checksum(), 'trials':[], 'isolation':{}}
    def save(): (out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    def env(mode): return dict(os.environ,COW_LINEAR_IMAGE=str(a.image.resolve()),COW_LINEAR_MODE=mode)
    def new(mode,name):
        log=(out/(name+'.log')).open('wb')
        return Guest([str(a.binary.resolve()),'measure'],log,env=env(mode)),log
    def q(g,sql):
        r=g.call(2,sql); assert r['ok'],(sql,r); return r
    def rows(g,sql):
        return [[bytes.fromhex(c['$h']).decode() if c else None for c in r] for r in q(g,sql)['rows']]
    def fixture(g):
        q(g,'CREATE TABLE benchmark_rows(id INT PRIMARY KEY,payload VARCHAR(64)) ENGINE=InnoDB')
        q(g,'START TRANSACTION')
        q(g,'INSERT INTO benchmark_rows VALUES '+','.join(f"({i},'{32*'x'}')" for i in range(1000)))
        q(g,'COMMIT'); assert rows(g,'SELECT COUNT(*) FROM benchmark_rows')==[['1000']]
    # Unchanged functional assertions, including two sessions and constraint errors.
    for mode in ['fresh','anon','cow']:
        g,log=new(mode,mode+'-functional'); records=[]
        try: workload(g,records)
        finally:
            if g.proc.poll() is None: g.proc.kill(); g.proc.wait()
            log.close()
        report['isolation'][mode+'_functional_records']=records
        r=subprocess.run([str(a.binary.resolve()),'auth-check'],env=env(mode),capture_output=True,timeout=30)
        assert r.returncode==0,(mode,r.stderr.decode())
        report['isolation'][mode+'_auth_exit']=r.returncode
    gs=[]; logs=[]
    try:
        for name in ['A','B']:
            g,l=new('cow','isolation-'+name); gs.append(g); logs.append(l)
            assert g.frame()['result']['ready']; assert g.call(1)['ok']; fixture(g)
        A,B=gs
        q(A,"UPDATE benchmark_rows SET payload='child-A' WHERE id=1")
        assert rows(B,'SELECT payload FROM benchmark_rows WHERE id=1')==[['x'*32]]
        q(A,'CREATE TABLE only_A(id INT PRIMARY KEY) ENGINE=InnoDB')
        r=B.call(2,'SELECT * FROM only_A'); assert not r['ok'] and r['errno']==1146
        q(A,'START TRANSACTION'); q(A,"INSERT INTO benchmark_rows VALUES(1001,'pending')")
        assert rows(B,'SELECT COUNT(*) FROM benchmark_rows')==[['1000']]
        q(A,'ROLLBACK'); assert rows(A,'SELECT COUNT(*) FROM benchmark_rows')==[['1000']]
        q(A,'START TRANSACTION'); q(A,"INSERT INTO benchmark_rows VALUES(1001,'commit')"); q(A,'COMMIT')
        assert rows(B,'SELECT COUNT(*) FROM benchmark_rows')==[['1000']]
        assert A.call(3)['closed']; assert A.stop()==0
        assert rows(B,'SELECT COUNT(*) FROM benchmark_rows')==[['1000']]
        assert B.call(3)['closed']; assert B.stop()==0
        report['isolation']['A_B_schema_transaction_close']=True
    finally:
        for g in gs:
            if g.proc.poll() is None:g.proc.kill();g.proc.wait()
        for l in logs:l.close()
    for i in range(20):
        g,l=new('cow',f'cycle-{i}')
        try:
            assert g.frame()['result']['ready']; assert g.call(1)['ok']; assert rows(g,'SELECT 1')==[['1']]
            assert g.call(3)['closed']; assert g.stop()==0
        finally:
            if g.proc.poll() is None:g.proc.kill();g.proc.wait()
            l.close()
    report['isolation']['repeated_create_destroy']=20
    report['isolation']['retained_guest_processes']=0
    save()
    for n in [1,4,8,16]:
        for trial in range(a.single_runs if n==1 else a.group_runs):
            # Matched no-sharing mmap control separates GC/ownership from sharing.
            for mode in ['fresh','anon','cow']:
                gs=[]; logs=[]; row={'mode':mode,'workers':n,'trial':trial,'completed':False};report['trials'].append(row)
                started=time.perf_counter()
                try:
                    for i in range(n):
                        g,l=new(mode,f'{mode}-{n}-{trial}-{i}');gs.append(g);logs.append(l)
                    def ready(g):
                        assert g.frame()['result']['ready']; return time.perf_counter()-started
                    with ThreadPoolExecutor(max_workers=n) as pool: row['ready_seconds']=max(pool.map(ready,gs))
                    def first(g):
                        assert g.call(1)['ok']; assert rows(g,'SELECT 1')==[['1']]; return time.perf_counter()-started
                    with ThreadPoolExecutor(max_workers=n) as pool: row['first_sql_seconds']=max(pool.map(first,gs))
                    def counters():
                        return json.loads(subprocess.check_output([str(a.helper.resolve()),*[str(g.proc.pid) for g in gs]],text=True))
                    row['ready_counters']=counters()
                    for key in ['rss_bytes','primary_bytes','cpu_seconds']:
                        row['ready_'+key]=sum(v[key] for v in row['ready_counters'].values())
                    with ThreadPoolExecutor(max_workers=n) as pool: list(pool.map(fixture,gs))
                    row['fixture_seconds']=time.perf_counter()-started;row['fixture_counters']=counters()
                    for key in ['rss_bytes','primary_bytes','cpu_seconds']:
                        row['fixture_'+key]=sum(v[key] for v in row['fixture_counters'].values())
                    if trial==0:
                        vm=subprocess.run(['vmmap','-summary','-wide',str(gs[0].proc.pid)],capture_output=True,text=True)
                        (out/f'{mode}-{n}-fixture.vmmap').write_text(vm.stdout+vm.stderr)
                        row['vmmap_exit']=vm.returncode
                    for g in gs: assert g.call(3)['closed']
                    with ThreadPoolExecutor(max_workers=n) as pool: row['exit_codes']=list(pool.map(lambda g:g.stop(),gs))
                    assert row['exit_codes']==[0]*n
                    row['after_close_active_processes']=sum(g.proc.poll() is None for g in gs)
                    row['after_close_guest_physical_bytes']=0 # reaped processes; not in-process cleanup proof
                    row['completed']=True
                finally:
                    for g in gs:
                        if g.proc.poll() is None:g.proc.kill();g.proc.wait()
                        g.proc.stdin.close();g.proc.stdout.close()
                    for l in logs:l.close()
                    save()
                print(mode,n,trial,round(row['first_sql_seconds']*1000,1),round(row['ready_primary_bytes']/n/2**20,2),flush=True)
    report['base_after']=checksum();assert report['base_before']==report['base_after']
    report['completed']=True
    report['summary']={}
    for mode in ['fresh','anon','cow']:
        report['summary'][mode]={}
        for n in [1,4,8,16]:
            rs=[r for r in report['trials'] if r['mode']==mode and r['workers']==n]
            report['summary'][mode][str(n)]={k:distribution([r[k] for r in rs]) for k in ['ready_seconds','first_sql_seconds','fixture_seconds','ready_rss_bytes','ready_primary_bytes','ready_cpu_seconds','fixture_primary_bytes','fixture_cpu_seconds']}
    save()


if __name__=='__main__':main()
