#!/usr/bin/env python3
import os,shutil
from pathlib import Path
import run as r
source=Path(os.environ['GENERIC_INPUT_TEMP']);product=source/'product'
shutil.copyfile(r.HERE/'product_smoke_test.go.txt',product/'tests/godefault/generic_memory_smoke_test.go')
r.run('build-counter',['cc','-O2',r.ROOT/'benchmarks/tools/process_cost.c','-o',r.T/'process-cost'])
r.run('generated-traps-and-worker-TLS',[r.GO,'test','-p','1','-tags=integration','-v','-count=1','-run=^TestGenericActualGeneratedScalarTraps$','-timeout=90s','./tests/godefault'],cwd=product,timeout=180)
r.record.update(finished=True,worker_TLS_smoke=True);r.save()
