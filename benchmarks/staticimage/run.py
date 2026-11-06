#!/usr/bin/env python3
"""One constructor-only proof; run under experiment_workspace's disk/time guard."""
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from git_identity import require_commit


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    evidence = Path(os.environ['MARIAMEM_EXPERIMENT_EVIDENCE'])
    temp = Path(os.environ['MARIAMEM_EXPERIMENT_TEMP'])
    sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    require_commit(ROOT, sha)
    if subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT):
        raise RuntimeError('exact clean source required')
    plan = json.loads((Path(__file__).with_name('plan.json')).read_text())
    require_commit(ROOT, plan['baseline_source_commit'])
    changes = subprocess.check_output(['git', 'diff', '--name-only', plan['baseline_source_commit'], sha], cwd=ROOT, text=True).splitlines()
    if any(not (p.startswith('benchmarks/staticimage/') or p.startswith('internal/generatedgo/code/base/static_image_experiment')) for p in changes):
        raise RuntimeError('unexpected changed boundary')
    inputs = json.loads((ROOT / 'release/generated-go-inputs.json').read_text())
    if inputs['guest_sha256'] != plan['guest_sha256']:
        raise RuntimeError('guest identity mismatch')
    env = dict(os.environ, GOCACHE=str(temp/'gocache'), GOMODCACHE=str(temp/'gomodcache'),
               GOTOOLCHAIN='local', CGO_ENABLED='0', GOMAXPROCS='4')
    info = {'source_commit':sha, 'baseline_source_commit':plan['baseline_source_commit'],
            'guest_sha256':inputs['guest_sha256'], 'host':platform.platform(),
            'go':subprocess.check_output(['go','version'],text=True).strip(),
            'files_sha256':{p:digest(ROOT/p) for p in changes}, 'results':[]}
    (evidence/'inputs.json').write_text(json.dumps(info,indent=2)+'\n')
    cases = [('mapping','./internal/generatedgo/code/base','^Test(StaticImage|Mapping)'),
             ('constructor','./benchmarks/staticimage','^Test')]
    for name, package, pattern in cases:
        binary = temp/(name+'.test')
        build = ['go','test','-c','-p','2','-o',str(binary),package]
        with (evidence/(name+'-build.log')).open('w') as log:
            subprocess.run(build,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
        run = [str(binary),'-test.v','-test.count=1','-test.timeout=90s','-test.run='+pattern]
        with (evidence/(name+'.log')).open('w') as log:
            result = subprocess.run(run,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
        record = {'name':name,'build':build[:6]+['<owned-temp>/'+binary.name,package],
                  'run':['<owned-temp>/'+binary.name]+run[1:],
                  'binary_sha256':digest(binary),'exit_code':result.returncode}
        info['results'].append(record)
        (evidence/'result.json').write_text(json.dumps(info,indent=2)+'\n')
        print(name, 'PASS' if result.returncode == 0 else 'FAIL', flush=True)
        if result.returncode:
            raise SystemExit(result.returncode)


if __name__ == '__main__':
    main()
