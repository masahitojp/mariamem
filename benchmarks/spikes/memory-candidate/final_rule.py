#!/usr/bin/env python3
"""Verify the store-order guard without changing the measured guest source bytes."""
import json
import os
from pathlib import Path
import shutil
import run as r
from fixtures import build

converter_source=Path(os.environ['MARIAMEM_CONVERTER_SOURCE'])
r.run('build-counter',['cc','-O2',r.ROOT/'benchmarks/tools/process_cost.c','-o',r.TEMP/'process-cost'])
r.run('converter-unit-tests',[r.GO,'test','-p','1','-run=^(TestMemoryAccessWidths|TestTrappingLoadIsObservable|TestPureMemory32RetainsIndividualStores|TestDCE.*)$','./internal/codegen','./internal/ssa','./internal/ssa/pass'],cwd=converter_source)
r.run('build-converter',[r.GO,'build','-p','1','-trimpath','-o',r.TEMP/'converter','./cmd/wasm2go'],cwd=converter_source)
fixture=r.TEMP/'inputs';count=build(fixture)
r.run('reference-partial-writes',['node',r.HERE/'reference.js',fixture/'contract.wasm',fixture/'matrix.json'])
keys=['op','addr','grow','trap','value','before','after']
rows=[json.loads(line) for line in (r.EVIDENCE/'reference-partial-writes.log').read_text().splitlines() if line.startswith('{')]
assert len(rows)==count
(r.HERE/'reference-results.json').write_text(json.dumps({'fixture_sha256':r.digest(fixture/'contract.wasm'),'keys':keys,'reference':'Node WebAssembly engine; independently executed binary fixture; representative Wasmer control preserved in 49817bb','rows':[[row[key] for key in keys] for row in rows]},separators=(',',':'))+'\n')
r.run('final-regression',[r.sys.executable,r.HERE/'check_fixture.py','--converter',r.TEMP/'converter','--output',r.TEMP/'regression'])
r.run('translate-guest',[r.sys.executable,r.ROOT/'benchmarks/spikes/generated-go-integration/translate_guest.py','--guest',r.GUEST,'--guest-sha256',r.digest(r.GUEST),'--converter-archive',r.CACHE/'wasm2go-fork.tar.gz','--output',r.TEMP/'translation'])
manifest=r.TEMP/'translation/input-manifest.json';old=json.loads((r.ROOT/'release/generated-go-translation.json').read_text());new=json.loads(manifest.read_text())
assert old['files_sha256']==new['files_sha256'],'store-order guard changed the measured full guest output; performance must be rerun'
shutil.copyfile(manifest,r.ROOT/'release/generated-go-translation.json')
r.run('verify-provenance',[r.sys.executable,r.ROOT/'scripts/verify_generated_runtime.py'])
r.run('canonical-check',[r.SHARED/'.venv/bin/python',r.ROOT/'scripts/verify.py','check'],timeout=900)
r.record.update(finished=True,fixture_case_count=count,trap_cases=sum(row['trap'] for row in rows),max_boundary_extra_traps=7,partial_write_cases=sum(row['op']=='partialstores' for row in rows),full_guest_byte_identical_to_measurement=True)
r.save()
