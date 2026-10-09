#!/usr/bin/env python3
"""Bounded v0.4.4 qualification, with no tag, merge, release or guest rebuild.

Run correctness before comparison on one platform. The candidate and published
v0.4.3 are built from exact source; measurements never compete on this machine.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import time

ROOT=Path(__file__).resolve().parents[1]
BASELINE='dd84ca4e9e0f2802766dd2f46d1c6ab24a41dc20'


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')


def sha256(path):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate-sha',required=True)
    parser.add_argument('--baseline-sha',default=BASELINE,choices=(BASELINE,))
    parser.add_argument('--workspace',type=Path,required=True,help='disposable parent outside source checkout')
    parser.add_argument('--disposable-checkout',action='store_true',required=True,help='allow cleanup of outputs in an otherwise disposable source checkout')
    parser.add_argument('--phase',choices=('all','correctness','performance'),default='all')
    args=parser.parse_args()
    if not re.fullmatch('[0-9a-f]{40}',args.candidate_sha):
        parser.error('exact 40-character candidate SHA required')
    workspace=args.workspace.resolve()
    if workspace==ROOT or ROOT in workspace.parents:
        parser.error('workspace must be outside candidate source checkout')
    actual=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    if actual!=args.candidate_sha or subprocess.check_output(['git','diff','--name-only','HEAD'],cwd=ROOT,text=True).strip():
        parser.error('source must be the exact clean candidate')
    machine=(platform.system(),platform.machine())
    if machine not in (('Darwin','arm64'),('Linux','x86_64')):
        parser.error('requires native macOS arm64 or Ubuntu x86_64')
    if machine[0]=='Linux' and ('ID=ubuntu' not in Path('/etc/os-release').read_text() or 'VERSION_ID="24.04"' not in Path('/etc/os-release').read_text()):
        parser.error('canonical Linux qualification requires Ubuntu 24.04')
    evidence=workspace/'evidence'
    scratch=workspace/'scratch'
    evidence.mkdir(parents=True,exist_ok=True)
    if scratch.exists():
        parser.error('scratch already exists; use a new disposable workspace')
    scratch.mkdir()
    env=dict(os.environ,GOTOOLCHAIN='go1.26.8',GOMAXPROCS='2',CGO_ENABLED='1',
             GOCACHE=str(scratch/'go-cache'),GOPATH=str(scratch/'go-path'),PIP_NO_CACHE_DIR='1')
    for key in ('MARIAMEM_RUNTIME','MARIAMEM_NATIVE_DIR','MARIAMEM_TEST_HOST','PYTHONPATH',
                'MARIAMEM_TIMING_DIR','MARIAMEM_INIT_DIAGNOSTICS','MARIAMEM_MEMORY_DIAGNOSTICS'):
        env.pop(key,None)
    commands=json.loads((evidence/'commands.json').read_text()) if (evidence/'commands.json').exists() else []
    metadata=dict(candidate_sha=actual,baseline_sha=args.baseline_sha,
                  guest_sha256=json.loads((ROOT/'release/generated-go-inputs.json').read_text())['guest_sha256'],
                  platform=platform.platform(),machine=platform.machine(),python=sys.version,
                  measured_at_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
                  contract='v044-ownedprepared-product-validation',phase=args.phase)
    if (evidence/'inputs.json').exists():
        previous=json.loads((evidence/'inputs.json').read_text())
        if previous.get('candidate_sha')!=actual or previous.get('baseline_sha')!=args.baseline_sha:
            parser.error('evidence workspace belongs to another source pair')
        metadata.update({key:value for key,value in previous.items() if key not in ('phase','result','error')})
    write(evidence/'inputs.json',metadata)
    def run(name,argv,*,cwd=ROOT,extra_env=None):
        command=[str(arg) for arg in argv]
        record=dict(name=name,argv=command,cwd=str(cwd))
        commands.append(record);write(evidence/'commands.json',commands)
        print('+',name,' '.join(command),flush=True)
        begun=time.monotonic()
        with (evidence/(name+'.log')).open('w') as output:
            result=subprocess.run(command,cwd=cwd,env=dict(env,**(extra_env or {})),stdout=output,stderr=subprocess.STDOUT)
        record.update(seconds=time.monotonic()-begun,exit_code=result.returncode)
        write(evidence/'commands.json',commands)
        if result.returncode:
            raise RuntimeError(f'{name} failed: exit {result.returncode}; see {name}.log')
    try:
        helper=scratch/'process_cost'
        run('build-counter',['cc','-O2','-o',helper,'benchmarks/tools/process_cost.c'])
        host=scratch/'candidate-host'
        run('build-host',['go','build','-p','1','-trimpath','-o',host,'./cmd/mariamem-host'],extra_env={'CGO_ENABLED':'0'})
        gate_path=evidence/'correctness.json'
        if args.phase in ('all','correctness'):
            write(gate_path,dict(result='NOT READY',candidate_sha=actual,baseline_sha=args.baseline_sha))
            # Runtime ownership/host handoff and pytest teardown changed. These
            # are their canonical source, handwritten-race and real-runtime gates.
            run('validation-tools',[sys.executable,'benchmarks/ownedprepared/test_tools.py'])
            run('source-unit-checks',[sys.executable,'scripts/verify.py','check'])
            run('runtime-integration',[sys.executable,'scripts/verify.py','integration'],
                extra_env={'MARIAMEM_PROCESS_COST':str(helper)})
            run('wheel-build',[sys.executable,'scripts/build_alpha.py','--ci-candidate'])
            wheel_record=json.loads((ROOT/'tests/evidence/alpha-wheel.json').read_text())
            wheel=ROOT/wheel_record['wheel']
            metadata['wheel_sha256']=sha256(wheel)
            venv=scratch/'consumer-venv'
            run('consumer-venv',[sys.executable,'-m','venv',venv])
            python=venv/'bin/python'
            run('consumer-install',[python,'-m','pip','install','--no-cache-dir',wheel,
                                    'pytest==8.4.2','pytest-xdist==3.8.0','PyMySQL==1.2.3'])
            run('installed-pytest',[python,'tests/verify_alpha.py'])
            for name in ('alpha.json','alpha-wheel.json','alpha-serial.log','alpha-parallel.log',
                         'alpha-migration.log','alpha-failure-cleanup.log','snapshots.json'):
                source=ROOT/'tests/evidence'/name
                if source.exists():
                    shutil.copy2(source,evidence/name)
            write(gate_path,dict(result='PASS',candidate_sha=actual,baseline_sha=args.baseline_sha,
                                 boundaries=['source/unit','handwritten races','Go real SQL/lifecycle',
                                             'Python import/isolation/lifecycle','installed pytest/xdist']))
        if args.phase in ('all','performance'):
            gate=json.loads(gate_path.read_text())
            if gate.get('result')!='PASS' or gate.get('candidate_sha')!=actual:
                raise RuntimeError('performance requires PASS correctness for this exact candidate')
            baseline=scratch/'baseline'
            baseline.mkdir()
            run('fetch-baseline',['git','fetch','--no-tags','origin',args.baseline_sha])
            peeled=subprocess.check_output(['git','rev-parse',args.baseline_sha+'^{commit}'],cwd=ROOT,text=True).strip()
            if peeled!=args.baseline_sha:
                raise RuntimeError('baseline must be an exact commit SHA')
            archive=scratch/'baseline.tar'
            run('archive-baseline',['git','archive','--format=tar','-o',archive,args.baseline_sha])
            with tarfile.open(archive) as source:
                source.extractall(baseline,filter='data')
            archive.unlink()
            if json.loads((baseline/'release/generated-go-inputs.json').read_text())['guest_sha256']!=metadata['guest_sha256']:
                raise RuntimeError('comparison guest changed; this qualification requires the existing guest')
            shared=baseline/'benchmarks/ownedprepared'
            shared.mkdir(parents=True)
            shutil.copy2(ROOT/'benchmarks/ownedprepared/main.go',shared/'main.go')
            candidate_bench=scratch/'candidate-bench'
            baseline_bench=scratch/'baseline-bench'
            baseline_host=scratch/'baseline-host'
            run('candidate-bench',['go','build','-p','1','-trimpath','-o',candidate_bench,'./benchmarks/ownedprepared'])
            run('baseline-bench',['go','build','-p','1','-trimpath','-o',baseline_bench,'./benchmarks/ownedprepared'],cwd=baseline)
            run('baseline-host',['go','build','-p','1','-trimpath','-o',baseline_host,'./cmd/mariamem-host'],cwd=baseline)
            metadata['binaries_sha256']={name:sha256(path) for name,path in {
                'candidate-bench':candidate_bench,'baseline-bench':baseline_bench,
                'candidate-host':host,'baseline-host':baseline_host,'process_cost':helper}.items()}
            run('comparison',[sys.executable,'benchmarks/ownedprepared/run_compare.py',
                              '--baseline-root',baseline,'--baseline-bench',baseline_bench,
                              '--candidate-bench',candidate_bench,'--baseline-host',baseline_host,
                              '--candidate-host',host,'--helper',helper,'--scratch',scratch/'measure',
                              '--out',evidence/'performance','--trials','3','--forks','16',
                              '--correctness-evidence',gate_path,'--candidate-sha',actual])
        metadata['result']='PASS'
    except Exception as error:
        metadata.update(result='FAIL',error=str(error))
        raise
    finally:
        metadata['harness_sha256']={str(path.relative_to(ROOT)):sha256(path) for path in
            sorted((ROOT/'benchmarks/ownedprepared').glob('*')) if path.is_file()}
        write(evidence/'inputs.json',metadata)
        shutil.rmtree(scratch)
        # build_alpha creates disposable build/package copies in the checkout.
        # This runner requires an exact CI checkout; never deletes user work.
        if (ROOT/'build').exists():
            for path in (ROOT/'build').iterdir():
                if path.name=='go.mod':
                    continue # tracked nested-module boundary
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink()
        for path in (ROOT/'python/mariamem/_native',ROOT/'python/build',ROOT/'python/mariamem.egg-info',ROOT/'tests/runs'):
            if path.exists():
                shutil.rmtree(path)
        for path in list(ROOT.rglob('__pycache__'))+list(ROOT.rglob('.pytest_cache')):
            shutil.rmtree(path)
        write(evidence/'cleanup.json',dict(scratch_removed=not scratch.exists(),
              recreated_build_removed=not (ROOT/'build').exists() or not any(path.name!='go.mod' for path in (ROOT/'build').iterdir()),retained_large_paths=[]))
        write(evidence/'SHA256SUMS.json',{str(path.relative_to(evidence)):sha256(path)
               for path in sorted(evidence.rglob('*')) if path.is_file() and path.name!='SHA256SUMS.json'})


if __name__=='__main__':
    main()
