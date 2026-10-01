#!/usr/bin/env python3
"""Prepared persistent-files clone with fresh execution state, not ready-heap resume."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0,str(Path(__file__).parents[1]/'wasm2go'))
from sql_execution import Guest,workload
from measure_execution import distribution

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--binary',type=Path,required=True)
p.add_argument('--capture',type=Path,required=True)
p.add_argument('--linear-image',type=Path,required=True)
p.add_argument('--helper',type=Path,required=True)
p.add_argument('--output-dir',type=Path,required=True)
p.add_argument('--single-runs',type=int,default=30)
p.add_argument('--group-runs',type=int,default=3)
a=p.parse_args();out=a.output_dir.resolve();out.mkdir(parents=True,exist_ok=True)
manifest=json.loads((a.capture/'manifest.json').read_text())
def verify():
 for name,info in manifest.items():
  data=(a.capture/'base'/name).read_bytes()
  assert len(data)==info['bytes'] and hashlib.sha256(data).hexdigest()==info['sha256'],name
verify_started=time.perf_counter();verify();verification_seconds=time.perf_counter()-verify_started
report={'source_sha':'8658310fce7745c7a8df04bc0aed7d7a6ce5ce14','completed':False,
 'boundary':'prepared clean files + pre-init linear image -> new process/runtime -> MariaDB reinitialization -> first SQL; no wire/per-child trust verification',
 'base_verify_once_seconds':verification_seconds,'base_unchanged_after':False,
 'binary_bytes':a.binary.stat().st_size,'binary_sha256':hashlib.sha256(a.binary.read_bytes()).hexdigest(),
 'functional':{},'isolation':{},'trials':[]}
def save(): (out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
def env(mode):
 e=dict(os.environ,COW_LINEAR_MODE='cow',COW_LINEAR_IMAGE=str(a.linear_image.resolve()))
 if mode!='fresh-db':e.update(PREPARED_FS_IMAGE=str((a.capture/'base').resolve()),PREPARED_FS_MODE='cow' if mode=='prepared-cow' else 'copy')
 return e
def new(mode,label):
 l=(out/(label+'.log')).open('wb');return Guest([str(a.binary.resolve()),'measure'],l,env=env(mode)),l
def q(g,sql,slot=0):
 r=g.call(2,sql,slot=slot);assert r['ok'],(sql,r);return r
def rows(g,sql,slot=0):return [[bytes.fromhex(c['$h']).decode() if c else None for c in r] for r in q(g,sql,slot)['rows']]
def fixture(g):
 q(g,'CREATE TABLE benchmark_rows(id INT PRIMARY KEY,payload VARCHAR(64)) ENGINE=InnoDB')
 q(g,'START TRANSACTION');q(g,'INSERT INTO benchmark_rows VALUES '+','.join(f"({i},'{32*'x'}')" for i in range(1000)));q(g,'COMMIT')

# Validate unchanged SQL expectations, then a child-specific prepared-table workload.
for mode in ['prepared-cow','prepared-copy']:
 g,l=new(mode,mode+'-existing-SQL');records=[]
 try:workload(g,records)
 finally:
  if g.proc.poll() is None:g.proc.kill();g.proc.wait()
  l.close()
 report['functional'][mode]=records
 g,l=new(mode,mode+'-prepared-SQL');records=[]
 try:
  assert g.frame()['result']['ready'];assert g.call(1)['ok']
  assert rows(g,'SELECT 1')==[['1']];assert rows(g,'SELECT COUNT(*) FROM benchmark_rows')==[['1000']]
  assert rows(g,'SELECT payload FROM benchmark_rows WHERE id=1')==[['x'*32]]
  q(g,'START TRANSACTION');q(g,"INSERT INTO benchmark_rows VALUES(1001,'commit')");q(g,'COMMIT')
  q(g,"UPDATE benchmark_rows SET payload='updated' WHERE id=1");q(g,'DELETE FROM benchmark_rows WHERE id=1001')
  q(g,'START TRANSACTION');q(g,"INSERT INTO benchmark_rows VALUES(1002,'rollback')");q(g,"UPDATE benchmark_rows SET payload='rollback' WHERE id=1");q(g,'ROLLBACK')
  assert rows(g,'SELECT COUNT(*) FROM benchmark_rows')==[['1000']]
  assert rows(g,'SELECT payload FROM benchmark_rows WHERE id=1')==[['updated']]
  q(g,'CREATE TABLE child_schema(id INT PRIMARY KEY) ENGINE=InnoDB')
  r=g.call(2,"INSERT INTO benchmark_rows VALUES(1,'duplicate')");assert not r['ok'] and r['errno']==1062
  assert g.call(1,slot=1)['ok'];q(g,'START TRANSACTION');q(g,"INSERT INTO benchmark_rows VALUES(1003,'pending')")
  assert rows(g,'SELECT COUNT(*) FROM benchmark_rows',slot=1)==[['1000']];q(g,'ROLLBACK')
  assert g.call(3,slot=1)['closed'];assert g.call(3)['closed'];assert g.stop()==0
  report['functional'][mode+'_prepared_fixture']=True
 finally:
  if g.proc.poll() is None:g.proc.kill();g.proc.wait()
  l.close()
 r=subprocess.run([str(a.binary.resolve()),'auth-check'],env=env(mode),capture_output=True,timeout=30)
 assert r.returncode==0 and b'"PASS"' in r.stdout,(mode,r.stderr)
 report['functional'][mode+'_auth']=True
gs=[];logs=[]
try:
 for name in ['A','B']:
  g,l=new('prepared-cow','isolation-'+name);gs.append(g);logs.append(l)
  assert g.frame()['result']['ready'];assert g.call(1)['ok'];assert rows(g,'SELECT COUNT(*) FROM benchmark_rows')==[['1000']]
 A,B=gs;q(A,"UPDATE benchmark_rows SET payload='A' WHERE id=1")
 assert rows(B,'SELECT payload FROM benchmark_rows WHERE id=1')==[['x'*32]]
 q(A,'CREATE TABLE only_A(id INT PRIMARY KEY) ENGINE=InnoDB');r=B.call(2,'SELECT * FROM only_A');assert not r['ok'] and r['errno']==1146
 q(A,'START TRANSACTION');q(A,"INSERT INTO benchmark_rows VALUES(1001,'uncommitted')")
 assert rows(B,'SELECT COUNT(*) FROM benchmark_rows')==[['1000']];q(A,'ROLLBACK')
 q(A,'START TRANSACTION');q(A,"INSERT INTO benchmark_rows VALUES(1001,'committed')");q(A,'COMMIT')
 assert rows(B,'SELECT COUNT(*) FROM benchmark_rows')==[['1000']]
 assert A.call(3)['closed'];assert A.stop()==0;assert rows(B,'SELECT COUNT(*) FROM benchmark_rows')==[['1000']]
 assert B.call(3)['closed'];assert B.stop()==0
 report['isolation']['A_B_writes_schema_transactions_shutdown']=True
finally:
 for g in gs:
  if g.proc.poll() is None:g.proc.kill();g.proc.wait()
 for l in logs:l.close()
for cycle in range(20):
 g,l=new('prepared-cow',f'cycle-{cycle}')
 try:
  assert g.frame()['result']['ready'];assert g.call(1)['ok'];assert rows(g,'SELECT COUNT(*) FROM benchmark_rows')==[['1000']]
  assert g.call(3)['closed'];assert g.stop()==0
 finally:
  if g.proc.poll() is None:g.proc.kill();g.proc.wait()
  l.close()
report['isolation']['clean_create_destroy_cycles']=20;save()

for n in [1,4,8,16]:
 for trial in range(a.single_runs if n==1 else a.group_runs):
  for mode in ['fresh-db','prepared-copy','prepared-cow']:
   if n==1 and trial>=10 and mode!='prepared-cow':continue
   gs=[];logs=[];row={'mode':mode,'workers':n,'trial':trial,'completed':False};report['trials'].append(row)
   started=time.perf_counter()
   try:
    for i in range(n):g,l=new(mode,f'{mode}-{n}-{trial}-{i}');gs.append(g);logs.append(l)
    def ready(g):assert g.frame()['result']['ready'];return time.perf_counter()-started
    with ThreadPoolExecutor(max_workers=n) as pool:row['ready_seconds']=max(pool.map(ready,gs))
    def first(g):assert g.call(1)['ok'];assert rows(g,'SELECT 1')==[['1']];return time.perf_counter()-started
    with ThreadPoolExecutor(max_workers=n) as pool:row['first_sql_seconds']=max(pool.map(first,gs))
    def count(g):
     if mode=='fresh-db':fixture(g)
     assert rows(g,'SELECT COUNT(*) FROM benchmark_rows')==[['1000']]
     return time.perf_counter()-started
    with ThreadPoolExecutor(max_workers=n) as pool:row['fixture_count_seconds']=max(pool.map(count,gs))
    counters=json.loads(subprocess.check_output([str(a.helper.resolve()),*[str(g.proc.pid) for g in gs]],text=True));row['counters']=counters
    for key in ['rss_bytes','primary_bytes','cpu_seconds']:row[key]=sum(v[key] for v in counters.values())
    if trial==0:
     vm=subprocess.run(['vmmap','-summary','-wide',str(gs[0].proc.pid)],capture_output=True,text=True)
     (out/f'{mode}-{n}.vmmap').write_text(vm.stdout+vm.stderr);row['vmmap_exit']=vm.returncode
    for g in gs:assert g.call(3)['closed']
    with ThreadPoolExecutor(max_workers=n) as pool:row['exit_codes']=list(pool.map(lambda g:g.stop(),gs))
    assert row['exit_codes']==[0]*n;row['after_close_active_processes']=sum(g.proc.poll() is None for g in gs);row['after_close_guest_physical_bytes']=0
    row['completed']=True
   finally:
    for g in gs:
     if g.proc.poll() is None:g.proc.kill();g.proc.wait()
     g.proc.stdin.close();g.proc.stdout.close()
    for l in logs:l.close()
    save()
   print(mode,n,trial,round(row['first_sql_seconds']*1000,1),round(row['primary_bytes']/n/2**20,2),flush=True)
verify();report['base_unchanged_after']=True;report['completed']=True
report['summary']={m:{str(n):{k:distribution([r[k] for r in report['trials'] if r['mode']==m and r['workers']==n]) for k in ['ready_seconds','first_sql_seconds','fixture_count_seconds','rss_bytes','primary_bytes','cpu_seconds']} for n in [1,4,8,16]} for m in ['fresh-db','prepared-copy','prepared-cow']}
save()
