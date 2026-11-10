"""Bounded stage attribution; stop on first slow Close, never retry or tune."""
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
for arm,item in inputs['binaries'].items():
    assert hashlib.sha256((TEMP/('bin-'+arm)).read_bytes()).hexdigest()==item['sha256']
env={k:v for k,v in os.environ.items() if not k.startswith(('GO','MARIAMEM_','MYSQLMEM_','CLOSE_DIAG_','ISSUE','FORKSTAGES_','LEXER_'))}
env.update(GOMAXPROCS='8',GOGC='100')
(EVIDENCE/'host.json').write_text(json.dumps({'platform':platform.platform(),'cpu':subprocess.check_output(['sysctl','-n','machdep.cpu.brand_string'],text=True).strip()},indent=2)+'\n')
rows=[]


def run(arm, rep, kind):
    name=f'{arm}-{kind}-{rep}'
    trace=EVIDENCE/name;trace.mkdir()
    scratch=TEMP/name;scratch.mkdir()
    report=trace/'result.json'
    local=dict(env,TMPDIR=str(scratch),CLOSE_DIAG_DIR=str(trace))
    if kind=='observer-control':local['CLOSE_DIAG_CONTROL']='1'
    count,p=(48,4) if kind=='primary' else (2,1)
    started=time.monotonic()
    with (trace/'console.txt').open('w') as log:
        result=subprocess.run([str(TEMP/('bin-'+arm)),'-mode','fork','-parallel',str(p),'-count',str(count),'-out',str(report)],env=local,stdout=log,stderr=subprocess.STDOUT,timeout=190)
    data=json.loads(report.read_text())
    traces=sorted(trace.glob('close-*.json'))
    row=dict(arm=arm,rep=rep,kind=kind,exit_code=result.returncode,success=data['success'],cleanup=data['cleanup'],
             error=data.get('error'),children=len(data['samples']),oracles=sum(s['oracle'] for s in data['samples']),
             duration_ms=(time.monotonic()-started)*1000,trace_files=[p.relative_to(EVIDENCE).as_posix() for p in traces],
             scratch_empty=not list(scratch.iterdir()),cleanup_stats=data['cleanup_stats'])
    rows.append(row)
    (EVIDENCE/'runs.json').write_text(json.dumps(rows,indent=2)+'\n')
    print(name,'PASS' if data['success'] and data['cleanup'] else 'FAIL','slow snapshots',len(traces),flush=True)
    if kind=='observer-control':
        assert traces and result.returncode==0 and data['success'] and data['cleanup']
        for path in traces:
            sample=json.loads(path.read_text());assert sample['control'] and not sample['stack_truncated']
            assert 'observeClose' in path.with_suffix('.txt').read_text()
        return False
    return bool(traces) or result.returncode!=0 or not data['success'] or not data['cleanup'] or not row['scratch_empty']


stopped=False
for arm in ('before','after'):
    if run(arm,-1,'positive'):
        stopped=True;break
    run(arm,-1,'observer-control')
if not stopped:
    for rep in range(10):
        for arm in (('before','after') if rep%2==0 else ('after','before')):
            if run(arm,rep,'primary'):
                stopped=True;break
        if stopped:break
(EVIDENCE/'completion.json').write_text(json.dumps({'result':'OBSERVATION_CAPTURED' if stopped else 'INCONCLUSIVE_NO_REPRODUCTION',
    'harness_source_commit':inputs['harness_source_commit'],'processes':len(rows),'primary_processes':sum(r['kind']=='primary' for r in rows),
    'max_primary_processes':20,'retries':0,'product_changes':False},indent=2)+'\n')
