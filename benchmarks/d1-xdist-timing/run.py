"""One local campaign: fresh pytest process per sample; cold host, warm OS caches."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'scripts'))
from git_identity import require_commit

p=argparse.ArgumentParser()
p.add_argument('--output', type=Path, required=True)
p.add_argument('--host', type=Path, required=True)
a=p.parse_args(); out=a.output.resolve();out.mkdir(parents=True)
sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
require_commit(ROOT,sha)
assert not subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True)
meta={'source_commit':sha,'candidate_source_commit':'d99f07cd16a8a11c1644225206a3d1fcc0a39edd',
      'platform':platform.platform(),'python':sys.version,'cpu_count':os.cpu_count(),
      'host_sha256':hashlib.sha256(a.host.read_bytes()).hexdigest(),
      'versions':{x:importlib.metadata.version(x) for x in ['mariamem','Django','pytest','pytest-django','pytest-xdist','execnet','mysqlclient']}}
(out/'inputs.json').write_text(json.dumps(meta,indent=2)+'\n')
rows=[]
for size in (3,30):
 for repetition in range(4):
  # Rotate order to reduce systematic cache/temperature bias. First round warmup.
  modes=[0,2,4];modes=modes[repetition%3:]+modes[:repetition%3]
  for workers in modes:
   dest=out/('%d-%d-%d'%(size,repetition,workers));dest.mkdir()
   scratch=dest/'tmp';scratch.mkdir()
   env=dict(os.environ,PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',DJANGO_SETTINGS_MODULE='timing_settings',
       D1_TIMING_OUT=str(dest),D1_TIMING_SIZE=str(size),MARIAMEM_PREPARED_HOST=str(a.host.resolve()),
       MARIAMEM_PREPARED_EVENTS=str(dest/'declaration.jsonl'),TMPDIR=str(scratch),
       PYTHONPATH=os.pathsep.join(map(str,[ROOT/'benchmarks/d1-xdist-timing',ROOT/'tests/django_prepared',ROOT/'tests/e2e_native_control/pythonapp'])))
   cmd=[sys.executable,'-m','pytest','-p','xdist.plugin','-p','pytest_django.plugin','-p','mariamem.django.pytest_plugin',
        str(ROOT/'benchmarks/d1-xdist-timing/test_workload.py'),'-q','--junitxml='+str(dest/'junit.xml')]
   if workers:cmd+=['-n',str(workers),'--dist=loadscope','--max-worker-restart=0']
   start=time.perf_counter()
   result=subprocess.run(cmd,env=env,cwd=ROOT,capture_output=True,text=True,timeout=240)
   wall=time.perf_counter()-start
   (dest/'stdout.txt').write_text(result.stdout+result.stderr)
   assert result.returncode==0,(dest,result.stdout[-2000:],result.stderr)
   tree=ET.parse(dest/'junit.xml');tests=tree.findall('.//testcase')
   assert len(tests)==size*8 and not tree.findall('.//failure') and not tree.findall('.//error')
   reports=[json.loads(x.read_text()) for x in dest.glob('*.json')]
   hosts=[pid for r in reports for pid in r['host_pids']]
   assert len(hosts)==(workers or 1),(dest,hosts)
   for pid in hosts:
    try:os.kill(pid,0)
    except ProcessLookupError:pass
    else:raise AssertionError('Host still alive: '+str(pid))
   row=dict(tests=size*8,repetition=repetition,warmup=repetition==0,workers=workers,wall_seconds=wall,
       hosts=len(hosts),forks=sum(r['counts'].get('fork',0) for r in reports),
       host_start_seconds_sum=sum(r['seconds'].get('start',0) for r in reports),
       snapshot_seconds_sum=sum(r['seconds'].get('snapshot',0) for r in reports),
       fork_seconds_sum=sum(r['seconds'].get('fork',0) for r in reports))
   rows.append(row);(out/'samples.json').write_text(json.dumps(rows,indent=2)+'\n')
   print(json.dumps(row),flush=True)
summary=[]
for tests in (24,240):
 for workers in (0,2,4):
  selected=[r['wall_seconds'] for r in rows if r['tests']==tests and r['workers']==workers and not r['warmup']]
  summary.append(dict(tests=tests,workers=workers,median_seconds=statistics.median(selected),min_seconds=min(selected),max_seconds=max(selected)))
(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
