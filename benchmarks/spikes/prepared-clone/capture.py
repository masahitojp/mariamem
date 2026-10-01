#!/usr/bin/env python3
"""Observe ready state; capture files only via existing orderly snapshot protocol."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import time

sys.path.insert(0,str(Path(__file__).parents[1]/'cow'))
from characterize import Guest,get,delta

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--binary',type=Path,required=True)
p.add_argument('--output-dir',type=Path,required=True)
a=p.parse_args();out=a.output_dir.resolve();out.mkdir(parents=True,exist_ok=True)
env=dict(os.environ,COW_CONTROL_DIR=str(out),PREPARED_EXPORT=str(out/'base'))
report={'source_sha':'8658310fce7745c7a8df04bc0aed7d7a6ce5ce14','ready_live_observation_not_snapshot':True,'completed':False}
with (out/'parent.log').open('wb') as log:
 g=Guest([str(a.binary.resolve()),'measure'],log,env=env)
 try:
  assert g.frame()['result']['ready'];assert g.call(1)['ok']
  def q(sql):
   r=g.call(2,sql);assert r['ok'],(sql,r);return r
  q('CREATE TABLE benchmark_rows(id INT PRIMARY KEY,payload VARCHAR(64)) ENGINE=InnoDB')
  q('START TRANSACTION');q('INSERT INTO benchmark_rows VALUES '+','.join(f"({i},'{32*'x'}')" for i in range(1000)));q('COMMIT')
  assert q('SELECT COUNT(*) FROM benchmark_rows')['rows'][0][0]['$h']=='31303030'
  report['transaction_state']=q('SELECT @@in_transaction')
  report['innodb_status']=g.call(2,'SHOW ENGINE INNODB STATUS')
  assert g.call(3)['closed']
  control=json.loads((out/'control.json').read_text());port=control['port']
  samples=[];runtimes=[]
  for i in range(4):
   time.sleep(2);s=get(port,'sample');r=json.loads(get(port,'runtime'));samples.append(s);runtimes.append(r)
   (out/f'live-{i}.json').write_text(json.dumps({'sample':s,'runtime':r},indent=2)+'\n')
  report['idle_deltas']=[delta(samples[i],samples[i+1]) for i in range(3)]
  report['live_runtime']=[{k:v for k,v in r.items() if k!='goroutine_stacks'} for r in runtimes]
  report['live_linear_bytes']=samples[-1]['linear_resident']
  g.proc.stdin.write(struct.pack('<I',0xfffffffe));g.proc.stdin.flush()
  report['snapshot_reply']=g.frame()['result'];assert report['snapshot_reply']=={'snapshot':True,'snapshot_version':1}
  assert g.proc.wait(timeout=30)==0
  files={}
  for f in sorted((out/'base').rglob('*')):
   if f.is_file():
    data=f.read_bytes();files[f.relative_to(out/'base').as_posix()]={'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()};f.chmod(0o444)
  assert any(k.endswith('benchmark_rows.ibd') for k in files)
  report['base_files']=files;report['base_logical_bytes']=sum(v['bytes'] for v in files.values());report['exit_code']=g.proc.returncode;report['completed']=True
  (out/'manifest.json').write_text(json.dumps(files,indent=2)+'\n')
 finally:
  if g.proc.poll() is None:g.proc.kill();g.proc.wait()
  (out/'capture.json').write_text(json.dumps(report,indent=2)+'\n')
print('captured',report['base_logical_bytes'],'bytes; idle deltas',report['idle_deltas'],flush=True)
