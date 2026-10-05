#!/usr/bin/env python3
"""Only 12 balanced fresh trials and one 20-generation process per state.

Requires a committed candidate and a successful correctness gate. No expansion.
"""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'memory-candidate'))
import run as r

proof = json.loads((r.ROOT/'benchmarks/v042-mmap-controlled-correctness.json').read_text())
assert proof['result'] == 'PASS' and proof['mmap']
assert proof['generated_provenance_sha256'] == r.digest(r.ROOT/'internal/generatedgo/provenance.json')
assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=r.ROOT, text=True).strip()
lock = (r.SHARED/'build/experiment-measurement.lock').open('a+')
fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
for key in ['MARIAMEM_NATIVE_DIR', 'MARIAMEM_RUNTIME', 'MARIAMEM_GENERATED_HOST', 'MARIAMEM_GENERATED_GUEST']:
    r.env.pop(key, None)
r.record.update(correctness_gate_sha256=r.digest(r.ROOT/'benchmarks/v042-mmap-controlled-correctness.json'), backing='three-way comparison', mmap=True, fresh_trials_per_state=12, generations_per_state=20)
r.run('build-counter', ['cc', '-O2', r.ROOT/'benchmarks/tools/process_cost.c', '-o', r.TEMP/'process-cost'])
refs = {'released': '547fb1a6c01e5edb0daa27de273a2e94e66eb098', 'controlled_heap': '2d633531acd7f81f7abb3ed613435b5d4a090342', 'controlled_mmap': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=r.ROOT, text=True).strip()}
r.record.update(sources=refs, binary_sha256={}, source_inventory_sha256={})
for state, ref in refs.items():
    source = r.TEMP/state
    source.mkdir()
    archive = r.TEMP/(state+'.tar')
    with archive.open('wb') as dest:
        subprocess.run(['git', 'archive', ref], cwd=r.ROOT, stdout=dest, check=True)
    with tarfile.open(archive) as tar:
        tar.extractall(source, filter='data')
    archive.unlink()
    project = r.TEMP/(state+'-probe')
    project.mkdir()
    (project/'go.mod').write_text('module github.com/masahitojp/mariamem/memoryprobe\n\ngo 1.26.0\nrequire github.com/masahitojp/mariamem v0.0.0\nreplace github.com/masahitojp/mariamem => '+str(source)+'\n')
    shutil.copyfile(r.ROOT/'benchmarks/spikes/mmap-controlled/fresh.go.txt', project/'main.go')
    if state == 'controlled_mmap':
        (project/'counter.go').write_text('package main\nimport "github.com/masahitojp/mariamem/internal/generatedgo/code/base"\nfunc init(){mappingStats=base.MemoryMappingStats}\n')
    binary = r.TEMP/(state+'-binary')
    r.run('build-'+state, [r.GO, 'build', '-mod=mod', '-p', '1', '-trimpath', '-buildvcs=false', '-o', binary, '.'], cwd=project)
    r.record['binary_sha256'][state] = r.digest(binary)
    manifest = {str(p.relative_to(source)): r.digest(p) for p in (source/'internal/generatedgo').rglob('*') if p.is_file()}
    r.record['source_inventory_sha256'][state] = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
    r.save()
extras = {'MARIAMEM_PROCESS_COUNTER': str(r.TEMP/'process-cost')}
for trial in range(12):
    states = list(refs)
    states = states[trial % 3:]+states[:trial % 3]
    for state in states:
        r.run('fresh-%02d-%s' % (trial, state), [r.TEMP/(state+'-binary')], extras=extras, timeout=60)
for state in refs:
    r.run('one20-'+state, [r.TEMP/(state+'-binary'), '-generations=20'], extras=extras, timeout=180)
r.record.update(finished=True, measurement_pass=True, no_expansion=True)
r.save()
rows = []
for phase in r.record['phases']:
    if phase['name'].startswith(('fresh-', 'one20-')):
        for line in (r.EVIDENCE/(phase['name']+'.log')).read_text().splitlines():
            if line.startswith('{'):
                rows.append(dict(phase=phase['name'], **json.loads(line)))
out = r.ROOT/'benchmarks/v042-mmap-controlled-evidence'
out.mkdir(exist_ok=True)
(out/'measurements.jsonl').write_text(''.join(json.dumps(row, separators=(',', ':'))+'\n' for row in rows))
compact = dict(sources=refs, binary_sha256=r.record['binary_sha256'], source_inventory_sha256=r.record['source_inventory_sha256'], correctness_gate_sha256=r.record['correctness_gate_sha256'], fresh_trials_per_state=12, generations_per_state=20, rows=len(rows), phases=[dict(name=p['name'], exit_code=p['exit_code']) for p in r.record['phases']], backing='released heap / controlled-traps heap / controlled-traps mmap', result='PASS', no_expansion=True)
(out/'campaign.json').write_text(json.dumps(compact, indent=2)+'\n')
