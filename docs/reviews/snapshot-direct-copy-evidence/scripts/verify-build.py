from pathlib import Path
import json, os, subprocess, sys, time

root = Path(__file__).resolve().parents[1]
repo, evidence = root / 'worktree', root / 'evidence'
env = dict(os.environ, GOTOOLCHAIN='go1.26.8', GOCACHE=str(root/'temp/gocache'),
           TMPDIR=str(root/'temp/tmp'), GOTMPDIR=str(root/'temp/go-tmp'),
           MARIAMEM_TEST_DEFAULT='1', MARIAMEM_SNAPSHOT_DIRECT='1', GOMAXPROCS='2')
source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
assert not subprocess.check_output(['git','status','--porcelain'],cwd=repo,text=True).strip()
records = []
steps = [
    ('generated-source', ['python3','scripts/verify_generated_runtime.py']),
    ('snapshot-race', ['go','test','-race','-p','1','./internal/snapshot','-count=1']),
    ('host-runtime-unit', ['go','test','-p','1','./internal/host','./internal/generatedgo','-count=1']),
    ('integration-direct', ['go','test','-p','1','-tags=integration','./tests/gointegration','./tests/godefault','-count=1','-v']),
    ('integration-control', ['go','test','-p','1','-tags=integration','./tests/gointegration','./tests/godefault','-count=1','-v']),
    ('canonical-check', [str(root/'temp/venv/bin/python'),'scripts/verify.py','check']),
    ('build-benchmark', ['go','build','-p','1','-o',str(root/'temp/ownedprepared'),'./benchmarks/ownedprepared']),
    ('build-python-host', ['go','build','-p','1','-o',str(root/'temp/mariamem-host'),'./cmd/mariamem-host']),
]
for name, cmd in steps:
    env['MARIAMEM_SNAPSHOT_DIRECT']='0' if name=='integration-control' else '1'
    print(name, flush=True)
    start=time.monotonic()
    with (evidence/f'{name}.log').open('w') as log:
        result=subprocess.run(cmd,cwd=repo,env=env,stdout=log,stderr=subprocess.STDOUT)
    records.append(dict(source_commit=source,name=name,command=cmd,returncode=result.returncode,seconds=time.monotonic()-start))
    (evidence/'verification.json').write_text(json.dumps(records,indent=2)+'\n')
    if result.returncode:
        print((evidence/f'{name}.log').read_text()[-6000:],flush=True)
        sys.exit(result.returncode)
