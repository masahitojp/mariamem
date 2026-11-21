"""Run correctness controls first, then serial P1 processes in the frozen order."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import time

p = argparse.ArgumentParser()
p.add_argument('binary', type=Path)
p.add_argument('results', type=Path)
p.add_argument('--counters', action='store_true')
a = p.parse_args()
a.results.mkdir(exist_ok=False, parents=True)
binary = a.binary.resolve()
env = dict(os.environ, GOMAXPROCS='8', GOGC='100', GODEBUG='profstackdepth=256')
metadata = dict(binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
                environment={k:env[k] for k in ('GOMAXPROCS','GOGC','GODEBUG')},
                os=platform.platform(), cpu=subprocess.check_output(['sysctl','-n','machdep.cpu.brand_string'],text=True).strip(),
                go_build=subprocess.check_output(['go','version','-m',binary],text=True), load_parallel=1)
(a.results/'environment.json').write_text(json.dumps(metadata,indent=2)+'\n')
start = time.monotonic()
deadline = start + 900
for index,(name,arm) in enumerate(
        [('validate-'+s,s) for s in 'ABC'] + [(f'{j+1}-{s}',s) for j,order in enumerate(('ABC','BCA','CAB')) for s in order]):
    args = [binary,'-arm',arm]
    if not name.startswith('validate-') and not a.counters:
        # Divide the remaining envelope across unstarted processes, including this one.
        secs = min(98, int((deadline-time.monotonic())/(12-index))-2)
        if secs <= 0: raise SystemExit('Phase 2 measurement budget reached')
        args += ['-duration',f'{secs}s','-profile',a.results/(name+'.pprof')]
    e = env.copy()
    if a.counters: e['COUNTER_OUTPUT'] = str((a.results/(name+'-events.json')).resolve())
    with (a.results/(name+'.jsonl')).open('w') as out,(a.results/(name+'.stderr')).open('w') as err:
        before = time.monotonic()
        result = subprocess.run(args,env=e,stdout=out,stderr=err,timeout=max(0,deadline-before))
    with (a.results/'runs.jsonl').open('a') as records:
        records.write(json.dumps(dict(name=name,arm=arm,rc=result.returncode,elapsed_s=time.monotonic()-before))+'\n')
    print(name,result.returncode,flush=True)
    if result.returncode:
        raise SystemExit('comparison stopped at '+name)
