#!/usr/bin/env python3
"""Finite exact-source macOS cache comparison; no runtime timing probes."""
import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from git_identity import require_commit, verify_go_binary


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def call(argv, *, cwd, env, log):
    with log.open('w') as out:
        p = subprocess.run(list(map(str, argv)), cwd=cwd, env=env,
                           stdout=out, stderr=subprocess.STDOUT, timeout=600)
    if p.returncode:
        raise RuntimeError(f'command failed ({p.returncode}): {argv}; {log}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--control', required=True)
    parser.add_argument('--candidate', required=True)
    parser.add_argument('--python', type=Path, required=True)
    parser.add_argument('--go', type=Path, required=True)
    a = parser.parse_args()
    if (platform.system(), platform.machine()) != ('Darwin', 'arm64'):
        raise ValueError('native macOS arm64 campaign only')
    work = a.workspace.resolve()
    temp, evidence = work / 'temp', work / 'evidence'
    evidence.mkdir(exist_ok=True)
    env = dict(os.environ, GOTOOLCHAIN='go1.26.8', CGO_ENABLED='0',
               GOCACHE=str(temp / 'gocache'), PYTHONDONTWRITEBYTECODE='1')
    for key in ('MARIAMEM_NATIVE_DIR', 'MARIAMEM_TEST_HOST', 'MARIAMEM_RUNTIME'):
        env.pop(key, None)
    builds = {}
    for label, commit in [('control', a.control), ('candidate', a.candidate)]:
        identity = require_commit(ROOT, commit)
        clone = temp / label
        call(['git', 'clone', '--shared', '--no-checkout', ROOT, clone], cwd=ROOT, env=env, log=evidence/f'{label}-clone.txt')
        call(['git', 'checkout', '--detach', commit], cwd=clone, env=env, log=evidence/f'{label}-checkout.txt')
        if subprocess.check_output(['git','status','--porcelain'],cwd=clone,text=True).strip():
            raise ValueError('dirty source')
        binaries = {}
        for name, package in [('go', './benchmarks/platform-cache'), ('host', './cmd/mariamem-host')]:
            binary = temp / f'{label}-{name}'
            call([a.go, 'build', '-p', '1', '-buildvcs=true', '-o', binary, package], cwd=clone, env=env,
                 log=evidence/f'{label}-{name}-build.txt')
            stamp = verify_go_binary(clone, binary, commit, go=a.go)
            binaries[name] = dict(path=str(binary), sha256=sha(binary), build_info=stamp)
        builds[label] = dict(identity=asdict(identity), binaries=binaries)
    (evidence/'builds.json').write_text(json.dumps(builds,indent=2)+'\n')
    # Ensure the sole behavioural input difference is the platform-check owner.
    diff = subprocess.check_output(['git','diff','--name-only',a.control,a.candidate],cwd=ROOT,text=True).splitlines()
    if not diff or any(not path.startswith('internal/artifacts/') for path in diff):
        raise ValueError(f'unexpected measured input differences: {diff}')
    records = []
    for language in ('go','python'):
        for workers, pairs in [(1,5),(4,3)]:
            for trial in range(pairs):
                order = ('control','candidate') if trial%2==0 else ('candidate','control')
                for label in order:
                    name=f'{language}-w{workers}-{trial}-{label}'
                    scratch=temp/name
                    scratch.mkdir()
                    local_env=dict(env, TMPDIR=str(scratch), GOTMPDIR=str(scratch))
                    output=evidence/f'{name}.json'
                    clone=temp/label
                    binaries=builds[label]['binaries']
                    if language=='go':
                        command=[binaries['go']['path'],'--payload-mib','0','--tables','1','--forks','4','--workers',str(workers),'--workload','crud','--out',output,'--label',label]
                    else:
                        command=[a.python,ROOT/'benchmarks/platform-cache/workflow.py','--sdk',clone/'python','--host',binaries['host']['path'],'--scale','small','--workers',str(workers),'--output',output]
                    at=time.monotonic()
                    call(command,cwd=clone,env=local_env,log=evidence/f'{name}.txt')
                    result=json.loads(output.read_text())
                    if language=='go':
                        ops={row['name']:row['seconds'] for row in result['operations']}
                        for prefix in ('fork_ready','point_use','count_use','mutation','disconnect','child_close'):
                            if sum(k.startswith(prefix+'_') for k in ops)!=4: raise ValueError('missing Go operation')
                        if result['forks']!=4 or result['workers']!=workers: raise ValueError('wrong Go dimensions')
                    else:
                        if result['result']!='PASS' or result['forks']!=4 or result['workers']!=workers or result['unique_hosts']!=1:
                            raise ValueError('Python functional/identity oracle failed')
                    if list(scratch.iterdir()): raise ValueError(f'unreclaimed scratch {scratch}')
                    scratch.rmdir()
                    records.append(dict(name=name,language=language,workers=workers,trial=trial,label=label,
                                        elapsed_seconds=time.monotonic()-at,output_sha256=sha(output)))
                    (evidence/'receipt.json').write_text(json.dumps(records,indent=2)+'\n')
    if len(records)!=32: raise ValueError('incomplete campaign')
    for build in builds.values():
        for binary in build['binaries'].values():
            if sha(Path(binary['path']))!=binary['sha256']:raise ValueError('binary changed during campaign')
    aggregates={}
    for language in ('go','python'):
        for workers in (1,4):
            for label in ('control','candidate'):
                rows=[r for r in records if (r['language'],r['workers'],r['label'])==(language,workers,label)]
                metrics={k:[] for k in ('initial_start','fork','children_wall','whole','close')}
                for row in rows:
                    data=json.loads((evidence/(row['name']+'.json')).read_text())
                    if language=='go':
                        ops={op['name']:op['seconds']*1000 for op in data['operations']}
                        metrics['initial_start'].append(ops['prepare_start'])
                        metrics['fork'].extend(v for k,v in ops.items() if k.startswith('fork_ready_'))
                        metrics['close'].extend(v for k,v in ops.items() if k.startswith('child_close_'))
                        metrics['children_wall'].append(data['instance_suite_wall_seconds']*1000)
                        metrics['whole'].append(data['suite_product_seconds']*1000)
                    else:
                        times=data['times_ms']
                        metrics['initial_start'].append(times['prepare/start'])
                        metrics['fork'].extend(v for k,v in times.items() if k.startswith('child') and k.endswith('/start'))
                        metrics['close'].extend(v for k,v in times.items() if k.startswith('child') and k.endswith('/close'))
                        metrics['children_wall'].append(times['children/wall'])
                        metrics['whole'].append(data['whole_ms'])
                aggregates[f'{language}/w{workers}/{label}']={k:dict(n=len(v),median_ms=statistics.median(v),min_ms=min(v),max_ms=max(v)) for k,v in metrics.items()}
    (evidence/'analysis.json').write_text(json.dumps(aggregates,indent=2)+'\n')
    environment=dict(platform=platform.platform(),machine=platform.machine(),
        python=subprocess.check_output([a.python,'--version'],text=True).strip(),
        packages=subprocess.check_output([a.python,'-m','pip','freeze'],text=True).splitlines(),
        cpu=subprocess.check_output(['sysctl','-n','machdep.cpu.brand_string'],text=True).strip(),
        logical_cpus=os.cpu_count(),differences=diff,process_executions=len(records))
    (evidence/'environment.json').write_text(json.dumps(environment,indent=2)+'\n')
    print(json.dumps(aggregates,indent=2))


if __name__=='__main__':
    main()
