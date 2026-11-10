"""Fixed scheduling comparison, no retries; diagnostic timings are separate."""
from pathlib import Path
import hashlib
import json
import os
import platform
import subprocess
import time

SOURCE=Path(__file__).resolve().parents[2]
WORK=SOURCE.parent
TEMP,EVIDENCE=WORK/'temp',WORK/'evidence'
inputs=json.loads((EVIDENCE/'inputs.json').read_text())
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=SOURCE,text=True).strip()==inputs['harness_source_commit']
assert not subprocess.check_output(['git','status','--porcelain'],cwd=SOURCE)
assert hashlib.sha256((TEMP/'bin').read_bytes()).hexdigest()==inputs['binary_sha256']
env={k:v for k,v in os.environ.items() if not k.startswith(('GO','MARIAMEM_','MYSQLMEM_','CLOSE_DIAG_','ISSUE','FORKSTAGES_','LEXER_'))}
env.update(GOMAXPROCS='8',GOGC='100')
(EVIDENCE/'host.json').write_text(json.dumps({'platform':platform.platform(),'cpu':subprocess.check_output(['sysctl','-n','machdep.cpu.brand_string'],text=True).strip()},indent=2)+'\n')
rows=[]


def run(arm,p,rep,kind):
    name=f'{arm}-p{p}-{kind}-{rep}'
    dest=EVIDENCE/name;dest.mkdir()
    scratch=TEMP/name;scratch.mkdir()
    report=dest/'result.json'
    local=dict(env,TMPDIR=str(scratch))
    if kind=='diagnostic':
        traces=dest/'traces';traces.mkdir();local['MARIAMEM_TIMING_DIR']=str(traces)
    count=2 if kind=='positive' else (4 if kind=='negative' else 48)
    args=[str(TEMP/'bin'),'-mode','fork','-schedule',arm,'-parallel',str(p),'-count',str(count),'-out',str(report)]
    if kind=='negative':args+=['-corrupt-seed']
    started=time.monotonic()
    with (dest/'console.txt').open('w') as log:
        proc=subprocess.run(args,env=local,stdout=log,stderr=subprocess.STDOUT,timeout=190)
    data=json.loads(report.read_text())
    expected=kind=='negative'
    good=(proc.returncode==1 and not data['success'] and 'pristine oracle' in data.get('error','')) if expected else proc.returncode==0 and data['success']
    good=good and data['cleanup'] and not list(scratch.iterdir()) and data['max_active']<=p
    if not expected:good=good and len(data['samples'])==count and all(s['oracle'] for s in data['samples'])
    for key in ['active_mappings','active_rw_bytes','active_reserved_bytes','release_failures']:good=good and data['cleanup_stats'][key]==0
    if kind=='diagnostic':good=good and len(list(traces.glob('child-*.json')))==count
    row=dict(arm=arm,parallel=p,rep=rep,kind=kind,name=name,exit_code=proc.returncode,expected_failure=expected,accepted=bool(good),duration_ms=(time.monotonic()-started)*1000,scratch_empty=not list(scratch.iterdir()))
    rows.append(row)
    (EVIDENCE/'runs.json').write_text(json.dumps(rows,indent=2)+'\n')
    print(name,'PASS' if good else 'FAIL',f"suite={data['suite_ms']:.1f}ms",flush=True)
    if not good:raise RuntimeError('STOP on unexpected failure: '+name)


try:
    for arm in ('mixed','wave'):
        run(arm,1,-1,'positive');run(arm,4,-1,'negative')
    for p in (4,8):
        for arm in ('mixed','wave'):run(arm,p,-1,'warmup')
    for rep in range(3):
        for p in ((4,8) if rep%2==0 else (8,4)):
            for arm in (('mixed','wave') if rep%2==0 else ('wave','mixed')):run(arm,p,rep,'primary')
    for p in (4,8):
        for arm in (('wave','mixed') if p==4 else ('mixed','wave')):run(arm,p,0,'diagnostic')
finally:
    (EVIDENCE/'completion.json').write_text(json.dumps({'result':'COLLECTED' if len(rows)==24 and all(r['accepted'] for r in rows) else 'STOPPED_INCOMPLETE','harness_source_commit':inputs['harness_source_commit'],'processes':len(rows),'primary_processes':sum(r['kind']=='primary' for r in rows),'retries':0,'product_changes':False},indent=2)+'\n')
