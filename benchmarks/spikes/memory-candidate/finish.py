#!/usr/bin/env python3
"""Finish a pinned, already-regenerated candidate after an acceptance stop."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import run as r

source = Path(os.environ['MARIAMEM_INPUT_TEMP'])
prior = json.loads((source.parent/'evidence/campaign.json').read_text())
assert prior['fixture_pass'] and prior['released_base'] == r.RELEASE
r.record.update(fixture_pass=True, fixture_case_count=prior['fixture_case_count'], trap_cases=prior['trap_cases'], resumed_generated_manifest_sha256=r.digest(r.ROOT/'release/generated-go-translation.json'))
r.run('build-counter', ['cc', '-O2', r.ROOT/'benchmarks/tools/process_cost.c', '-o', r.TEMP/'process-cost'])
r.run('verify-provenance', [r.sys.executable, r.ROOT/'scripts/verify_generated_runtime.py'])
shutil.copyfile(r.HERE/'matrix.go.txt', source/'fixture/main.go')
r.run('fixture-matrix-grow-state', [r.GO, 'run', '.', source/'fixtures/matrix.json'], cwd=source/'fixture')
shutil.copyfile(r.HERE/'product_smoke_test.go.txt', r.ROOT/'tests/godefault/pure_memory32_test.go')
for test in ['GeneratedTraps', 'CRUDSessionsAndFork', 'Auth', 'RepeatedClose']:
    r.run('product-'+test, [r.GO, 'test', '-p', '1', '-tags=integration', '-v', '-count=1', '-run=^TestPureMemory32'+test+'$', '-timeout=90s', './tests/godefault'], timeout=150)
r.run('focused-adapter-race', [r.GO, 'test', '-race', '-p', '1', '-count=1', './internal/generatedgo', './internal/guest', './internal/host', './internal/mysqlwire', './internal/snapshot'], extras={'CGO_ENABLED': '1'})
r.record['compatibility_pass'] = True
r.save()
baseline = r.TEMP/'baseline'
baseline.mkdir()
archive = r.TEMP/'baseline.tar'
with archive.open('wb') as dest:
    subprocess.run(['git', 'archive', r.RELEASE], cwd=r.ROOT, stdout=dest, check=True)
with tarfile.open(archive) as tar:
    tar.extractall(baseline, filter='data')
archive.unlink()
for mode, runtime_source in [('baseline', baseline), ('candidate', r.ROOT)]:
    probe = r.TEMP/('probe-'+mode)
    probe.mkdir()
    (probe/'go.mod').write_text('module memorycost\n\ngo 1.26.0\nrequire github.com/masahitojp/mariamem v0.0.0\nreplace github.com/masahitojp/mariamem => '+str(runtime_source)+'\n')
    shutil.copyfile(r.HERE/'probe.go.txt', probe/'main.go')
    r.run('build-probe-'+mode, [r.GO, 'build', '-mod=mod', '-p', '1', '-trimpath', '-o', r.TEMP/(mode+'-probe'), '.'], cwd=probe)
for trial in range(20):
    for mode in (['baseline', 'candidate'] if trial%2 == 0 else ['candidate', 'baseline']):
        r.run('fresh-%02d-%s' % (trial, mode), [r.TEMP/(mode+'-probe')], timeout=60)
for mode in ['baseline', 'candidate']:
    r.run('repeated-'+mode, [r.TEMP/(mode+'-probe'), '-generations=20'], timeout=180)
r.run('compiler-inline-assessment', [r.GO, 'build', '-p', '1', '-gcflags=genericfixture/fixture=-m=2', '-o', r.TEMP/'inline-fixture', '.'], cwd=source/'fixture')
r.run('canonical-check', [r.SHARED/'.venv/bin/python', r.ROOT/'scripts/verify.py', 'check'], timeout=900)
r.record['finished'] = True
r.save()
