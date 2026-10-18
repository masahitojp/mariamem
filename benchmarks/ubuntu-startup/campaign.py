#!/usr/bin/env python3
"""Bounded native Ubuntu startup study. Ordinary and diagnostic cohorts stay separate."""
import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
from git_identity import require_commit,verify_go_binary

BASE='3f514ebf14fbbe6aca6ba77d00a1bb6cdb35163d'

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def case_plan():
    cases=[]
    modes=[('serial',1,'pipeline'),('pipeline',4,'pipeline'),('barrier',4,'barrier')]
    for trial in range(5):
        order=modes[trial%3:]+modes[:trial%3]
        for name,workers,mode in order:
            cases.append(dict(name=f'ordinary-{name}-{trial}',cohort='ordinary',workers=workers,mode=mode,procs=0,diagnostic='none'))
    for trial in range(3):
        procs=[1,2,4];procs=procs[trial%3:]+procs[:trial%3]
        for n in procs:
            cases.append(dict(name=f'procs-{n}-{trial}',cohort='procs',workers=4,mode='barrier',procs=n,diagnostic='none'))
    for trial in range(3):
        for mode in (['pipeline','barrier'] if trial%2==0 else ['barrier','pipeline']):
            cases.append(dict(name=f'cpu-{mode}-{trial}',cohort='cpu',workers=4,mode=mode,procs=0,diagnostic='cpu'))
    for mode in ['pipeline','barrier']:
        cases.append(dict(name=f'trace-{mode}',cohort='trace',workers=4,mode=mode,procs=0,diagnostic='trace'))
    assert len(cases)==32
    return cases


def main():
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--source-commit',required=True);a=p.parse_args()
    if (platform.system(),platform.machine())!=('Linux','x86_64'):raise ValueError('native Ubuntu x86_64 only')
    work=a.work.resolve();temp=work/'temp';out=work/'evidence'
    temp.mkdir(parents=True,exist_ok=True);out.mkdir(parents=True,exist_ok=True)
    identity=require_commit(ROOT,a.source_commit);require_commit(ROOT,BASE)
    if subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()!=a.source_commit:raise ValueError('source differs')
    if subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip():raise ValueError('dirty source')
    if not (ROOT/'.git').is_dir():raise ValueError('normal checkout required for Go stamping')
    changes=subprocess.check_output(['git','diff','--name-only',BASE,a.source_commit],cwd=ROOT,text=True).splitlines()
    if any(not (x.startswith('benchmarks/ubuntu-startup/') or x.startswith('docs/') or x=='.github/workflows/ubuntu-parallel-startup.yml') for x in changes):raise ValueError(f'outside study scope: {changes}')
    env=dict(os.environ,GOTOOLCHAIN='go1.26.8',CGO_ENABLED='0',GOCACHE=str(temp/'gocache'),GOTMPDIR=str(temp/'compiler'),TMPDIR=str(temp/'compiler'))
    (temp/'compiler').mkdir(exist_ok=True)
    for key in ['GOMAXPROCS','MARIAMEM_TIMING_DIR','MARIAMEM_NATIVE_DIR','MARIAMEM_RUNTIME']:
        env.pop(key,None)
    def run(argv,log,timeout=180):
        with log.open('w') as f:r=subprocess.run(list(map(str,argv)),cwd=ROOT,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
        if r.returncode:raise RuntimeError(f'{argv}: exit {r.returncode}; {log}')
    binary=temp/'startup-study'
    run(['go','build','-p','1','-buildvcs=true','-o',binary,'./benchmarks/ubuntu-startup'],out/'build.txt',900)
    stamp=verify_go_binary(ROOT,binary,a.source_commit)
    tools={}
    goroot=Path(subprocess.check_output(['go','env','GOROOT'],cwd=ROOT,env=env,text=True).strip())
    for tool in ['pprof','trace']:
        executable=temp/tool
        run(['go','build','-p','1','-o',executable,'cmd/'+tool],out/(tool+'-build.txt'),300)
        tools[tool]=dict(binary_sha256=sha(executable),source_go_sha256={p.name:sha(p) for p in sorted((goroot/'src/cmd'/tool).glob('*.go')) if not p.name.endswith('_test.go')})
    record=dict(analysis_tools=tools,source_identity=asdict(identity),base_source_commit=BASE,binary_sha256=sha(binary),build_info=stamp,
                go_build=['go','build','-p','1','-buildvcs=true','-o',str(binary),'./benchmarks/ubuntu-startup'],cases=[],completed=False)
    (out/'receipt.json').write_text(json.dumps(record,indent=2)+'\n')
    for case in case_plan():
        scratch=temp/case['name'];scratch.mkdir()
        output=out/(case['name']+'.json');diagnostics=out/(case['name']+'-diagnostics')
        argv=[binary,'--payload-mib','10','--tables','8','--forks','4','--workers',str(case['workers']),
              '--phase-mode',case['mode'],'--procs',str(case['procs']),'--workload','app-connections',
              '--diagnostic',case['diagnostic'],'--diagnostic-dir',diagnostics,'--out',output,'--label',case['name']]
        local=env;env=dict(env,TMPDIR=str(scratch))
        at=time.monotonic();run(argv,out/(case['name']+'.txt'));env=local
        if list(scratch.iterdir()):raise ValueError(f'scratch not reclaimed: {scratch}')
        scratch.rmdir()
        record['cases'].append(dict(**case,argv=list(map(str,argv)),exit_code=0,elapsed_seconds=time.monotonic()-at,output_sha256=sha(output)))
        (out/'receipt.json').write_text(json.dumps(record,indent=2)+'\n')
    if sha(binary)!=record['binary_sha256']:raise ValueError('binary changed')
    for mode in ['pipeline','barrier']:
        for kind in ['cpu','block','mutex']:
            profiles=[out/f'cpu-{mode}-{i}-diagnostics/{kind}.pprof' for i in range(3)]
            for ordering,flags in [('flat',['-top']),('cum',['-top','-cum']),('raw',['-raw'])]:
                run([temp/'pprof',*flags,'-nodecount=60',binary,*profiles],out/f'{mode}-{kind}-{ordering}.txt')
        trace=out/f'trace-{mode}-diagnostics/trace.trace'
        run([temp/'trace','-d=parsed',trace],out/f'{mode}-trace-events.txt')
        for kind in ['sched','sync','syscall']:
            profile=out/f'{mode}-trace-{kind}.pprof'
            run([temp/'trace','-pprof='+kind,trace],profile)
            run([temp/'pprof','-top','-nodecount=50',binary,profile],out/f'{mode}-trace-{kind}.txt')
    record['completed']=True;(out/'receipt.json').write_text(json.dumps(record,indent=2)+'\n')
    print('PASS: 15 ordinary + 9 procs + 6 CPU + 2 trace executions; guest unchanged')

if __name__=='__main__':main()
