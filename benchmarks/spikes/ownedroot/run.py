#!/usr/bin/env python3
"""Run the bounded component/oracle checks; no guest build or performance claim."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--go', required=True, type=Path)
    args = parser.parse_args()
    evidence = Path(os.environ['MARIAMEM_EXPERIMENT_EVIDENCE'])
    temp = Path(os.environ['MARIAMEM_EXPERIMENT_TEMP'])
    evidence.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, GOTOOLCHAIN='local', GOWORK='off', GOENV='off', GOFLAGS='',
               GOEXPERIMENT='', GOPROXY='off', GOSUMDB='off', GOCACHE=str(temp/'gocache'),
               GOPATH=str(temp/'gopath'), GOMODCACHE=str(temp/'gomodcache'),
               GOTMPDIR=str(temp/'gotmp'), CGO_ENABLED='0')
    for key in ('GOMAXPROCS', 'GOGC', 'GOMEMLIMIT'):
        env.pop(key, None)
    for name in ('gocache','gopath','gomodcache','gotmp'):
        (temp/name).mkdir(exist_ok=True)
    identity = json.loads(subprocess.check_output(
        [sys.executable, 'scripts/git_identity.py', 'inspect', 'HEAD'], cwd=ROOT))
    status = subprocess.check_output(['git','status','--porcelain','--untracked-files=all'], cwd=ROOT, text=True)
    if status.strip():
        raise RuntimeError('Commit the exact recipe before execution: '+status)
    version = subprocess.check_output([str(args.go),'version'], env=env, text=True).strip()
    if 'go1.26.8' not in version:
        raise RuntimeError('Expected pinned Go1.26.8: '+version)
    inputs = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted((ROOT/'benchmarks/spikes/ownedroot').glob('*')) if p.is_file()}
    receipt = {'source_commit':identity['source_commit'], 'source_object_type':identity['object_type'],
               'go':version,'inputs_sha256':inputs,'scope':'guest-disconnected component; no SQL/performance qualification',
               'runs':[],'evidence':[]}
    commands = [
        ('component', ['test','-json','-p','1','-count=1','-timeout=90s','./benchmarks/spikes/ownedroot'], '0'),
        ('existing-strict', ['test','-json','-p','1','-count=1','-timeout=90s',
            './internal/generatedgo/code/base','./internal/snapshot','./internal/prepared',
            '-run','TestHeap|TestClosedOwnerDoesNotRetainHeap|TestCompletedCaptureDoesNotRetainImage'], '0'),
        ('component-race', ['test','-json','-race','-p','1','-count=1','-timeout=90s','./benchmarks/spikes/ownedroot'], '1'),
    ]
    failed = False
    for label, command, cgo in commands:
        t0=time.monotonic()
        result=subprocess.run([str(args.go),*command],cwd=ROOT,env=dict(env,CGO_ENABLED=cgo),
                              stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=480)
        output=result.stdout.replace(str(ROOT),'<source>').replace(str(temp),'<temp>')
        import re
        output=re.sub(r'/Users/[^\s/]+/', '<user>/', output)
        (evidence/(label+'.jsonl')).write_text(output)
        tests=[]
        outputs={}
        for line in output.splitlines():
            try:
                event=json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get('Action') in ('pass','fail','skip') and event.get('Test'):
                tests.append({k:event[k] for k in ('Action','Test')})
            text=event.get('Output','')
            outputs.setdefault(event.get('Test',''),[]).append(text)
        # test2json may split a long testing.Log line across multiple events.
        for chunks in outputs.values():
            for line in ''.join(chunks).splitlines():
                if 'EVIDENCE ' in line:
                    item=json.loads(line.split('EVIDENCE ',1)[1])
                    item['run']=label
                    receipt['evidence'].append(item)
        receipt['runs'].append({'name':label,'arguments':command,'cgo_enabled':cgo,
                               'exit_code':result.returncode,'elapsed_seconds':time.monotonic()-t0,'tests':tests})
        (evidence/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
        print(label, 'PASS' if result.returncode==0 else 'FAIL', flush=True)
        if result.returncode:
            print(output[-5000:],flush=True);failed=True;break
    receipt['result']='FAIL' if failed else 'PASS'
    receipt['interpretation']='Race detector output only; no claim of mmap or general shared-memory safety.'
    (evidence/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return int(failed)

if __name__=='__main__':
    raise SystemExit(main())
