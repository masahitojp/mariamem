#!/usr/bin/env python3
"""Resume correctness after a bounded stop; no benchmark or broader lifecycle."""
import json,os,shutil
from pathlib import Path
import run as r
source=Path(os.environ['GENERIC_INPUT_TEMP'])
prior=json.loads((source.parent/'evidence/campaign.json').read_text())
for name,sha in prior['generated_inventory'].items(): assert r.digest(source/'guest-generated'/name)==sha,name
r.record.update(resumes_from=str(source.parent),fixture_pass=prior['fixture_pass'],prior_parallel_lifecycle='STOPPED by memory budget; not an acceptance pass')
r.run('build-counter',['cc','-O2',r.ROOT/'benchmarks/tools/process_cost.c','-o',r.T/'process-cost'])
product=source/'product';shutil.copyfile(r.HERE/'product_smoke_test.go.txt',product/'tests/godefault/generic_memory_smoke_test.go')
# Separate fresh test processes keep this a small correctness smoke.
for name in ['TestGenericActualGeneratedScalarTraps','TestGenericFocusedCRUDSessionsAndFork']:
 r.run(name,[r.GO,'test','-p','1','-tags=integration','-v','-count=1','-run=^'+name+'$','-timeout=90s','./tests/godefault'],cwd=product,timeout=180)
r.run('compiler-inline-assessment',[r.GO,'build','-p','1','-gcflags=genericfixture/fixture=-m=2','-o',r.T/'inline-fixture','.'],cwd=source/'fixture-checked')
r.record.update(product_smoke=True,finished=True);r.save()
