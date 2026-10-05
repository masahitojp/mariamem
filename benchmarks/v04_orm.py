#!/usr/bin/env python3
"""Same v0.3 SQLAlchemy CRUD dogfood case on fresh isolated databases."""
import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import platform
import runpy
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--json', type=Path, required=True)
    p.add_argument('--runs', type=int, default=3)
    p.add_argument('--native-dir', type=Path, help='selected exact bundle; public API still uses its ordinary resolver')
    a = p.parse_args()
    if a.runs < 3: p.error('three or more suite trials required')
    if a.native_dir:
        os.environ['MARIAMEM_NATIVE_DIR'] = str(a.native_dir.resolve())
    import mariamem
    expected = runpy.run_path(str(ROOT/'python/mariamem/_version.py'))['PYTHON_VERSION']
    assert mariamem.__version__ == expected, 'installed wheel version differs from measured source'
    source = ROOT/'tests/consumer/test_sqlalchemy_dogfood.py'
    spec = importlib.util.spec_from_file_location('dogfood', source)
    dog = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(dog)
    report = dict(schema_version=1, completed=False, workload='test_03_update_commit_and_delete',
                  source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                  workload_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                  harness_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  platform=platform.platform(), python=platform.python_version(),
                  wheel_origin=json.loads(importlib.metadata.distribution('mariamem').read_text('direct_url.json')),
                  packages={k:importlib.metadata.version(k) for k in ('mariamem','SQLAlchemy','PyMySQL','pytest')},
                  native_manifest=json.loads((Path(os.environ.get('MARIAMEM_NATIVE_DIR', Path(mariamem.__file__).parent/'_native'))/'manifest.json').read_text()),
                  suites=[])
    output = a.json.resolve()
    if output.is_relative_to(ROOT) and not output.is_relative_to(ROOT/'benchmarks/results'):
        p.error('checkout output must be under benchmarks/results')
    output.parent.mkdir(parents=True,exist_ok=True)
    def save(): output.write_text(json.dumps(report,indent=2)+'\n')
    def prepared():
        db = mariamem.start(); engine = dog.engine_for(db,{})
        try: dog.prepare(engine)
        finally: engine.dispose()
        db.wait_disconnected()
        try: return db.snapshot()
        finally: db.close()
    try:
        for phase, counts, rounds in [('warmup',[1],1),('measurement',[10,50,100],a.runs)]:
            for n in counts:
                for r in range(rounds):
                    modes = ('start','fork') if r%2==0 else ('fork','start')
                    for mode in modes:
                        begun=time.monotonic(); snapshot=None; samples=[]
                        try:
                            if mode=='fork': snapshot=prepared()
                            prep=time.monotonic()-begun
                            for i in range(n):
                                t=time.monotonic(); db=snapshot.fork() if snapshot else mariamem.start()
                                pids,directory=db.diagnostics,db.log_path.parent
                                engine=dog.engine_for(db,{})
                                try:
                                    if mode=='start': dog.prepare(engine)
                                    with engine.connect() as c:
                                        assert c.scalar(dog.select(dog.func.count()).select_from(dog.User))==1
                                        assert c.scalar(dog.select(dog.func.count()).select_from(dog.Address))==1
                                        version=c.scalar(dog.text('SELECT VERSION()'))
                                    ready=time.monotonic()-t
                                    work=time.monotonic()
                                    dog.test_03_update_commit_and_delete((engine,db,{}))
                                    workload=time.monotonic()-work
                                finally:
                                    cleanup=time.monotonic(); engine.dispose()
                                    try: db.wait_disconnected()
                                    finally: db.close()
                                    dog.reaped(db,pids,directory)
                                samples.append(dict(ready_seconds=ready,workload_seconds=workload,
                                                    cleanup_seconds=time.monotonic()-cleanup,total_seconds=time.monotonic()-t))
                        finally:
                            if snapshot:
                                saved=snapshot.path; snapshot.close(); assert not saved.exists()
                        report['suites'].append(dict(phase=phase,mode=mode,tests=n,round=r,setup_seconds=prep,
                                                    suite_seconds=time.monotonic()-begun,server_version=version,samples=samples))
                        save(); print(phase,n,r,mode,report['suites'][-1]['suite_seconds'],flush=True)
        report['completed']=True
    finally: save()

if __name__=='__main__':main()
