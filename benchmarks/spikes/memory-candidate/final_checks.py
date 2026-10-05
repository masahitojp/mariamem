#!/usr/bin/env python3
"""Review the final constant-address cases, then run the unchanged canonical checks."""
import json
import os
from pathlib import Path
import subprocess
import run as r
from fixtures import build

r.run('build-counter',['cc','-O2',r.ROOT/'benchmarks/tools/process_cost.c','-o',r.TEMP/'process-cost'])
fixture=r.TEMP/'reference-inputs'
count=build(fixture)
r.run('reference-constant-paths',['node',r.HERE/'reference.js',fixture/'contract.wasm',fixture/'matrix.json'])
keys=['op','addr','grow','trap','value','before','after']
rows=[json.loads(line) for line in (r.EVIDENCE/'reference-constant-paths.log').read_text().splitlines() if line.startswith('{')]
assert len(rows)==count
(r.HERE/'reference-results.json').write_text(json.dumps({'fixture_sha256':r.digest(fixture/'contract.wasm'),'keys':keys,'reference':'Node WebAssembly engine; independently executed binary fixture; representative Wasmer control preserved in 49817bb','rows':[[row[key] for key in keys] for row in rows]},separators=(',',':'))+'\n')
converter=Path(os.environ['MARIAMEM_CHECK_CONVERTER'])
r.run('final-regression',[r.sys.executable,r.HERE/'check_fixture.py','--converter',converter,'--output',r.TEMP/'regression'])
r.run('canonical-check',[r.SHARED/'.venv/bin/python',r.ROOT/'scripts/verify.py','check'],timeout=900)
r.record.update(finished=True,fixture_case_count=count,trap_cases=sum(row['trap'] for row in rows),max_boundary_extra_traps=7)
r.save()
