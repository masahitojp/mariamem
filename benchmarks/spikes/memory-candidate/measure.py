#!/usr/bin/env python3
"""Measure already-built identical probes after all focused acceptance passes."""
import json
import os
from pathlib import Path
import shutil
import run as r

inputs = Path(os.environ['MARIAMEM_PROBE_INPUT'])
assert json.loads((inputs.parent/'evidence/campaign.json').read_text())['compatibility_pass']
r.record['probe_sha256'] = {}
r.run('build-counter', ['cc', '-O2', r.ROOT/'benchmarks/tools/process_cost.c', '-o', r.TEMP/'process-cost'])
for mode in ['baseline','candidate']:
    target=r.TEMP/(mode+'-probe')
    project=inputs/('probe-'+mode)
    shutil.copyfile(r.HERE/'probe.go.txt',project/'main.go')
    r.run('build-probe-'+mode,[r.GO,'build','-mod=mod','-p','1','-trimpath','-o',target,'.'],cwd=project)
    r.record['probe_sha256'][mode]=r.digest(target)
r.record['candidate_provenance_sha256'] = r.digest(r.ROOT/'internal/generatedgo/provenance.json')
r.record['probe_source_sha256'] = r.digest(r.HERE/'probe.go.txt')
for trial in range(20):
    for mode in (['baseline', 'candidate'] if trial%2 == 0 else ['candidate', 'baseline']):
        r.run('fresh-%02d-%s' % (trial, mode), [r.TEMP/(mode+'-probe')], timeout=60)
for mode in ['baseline', 'candidate']:
    r.run('repeated-'+mode, [r.TEMP/(mode+'-probe'), '-generations=20'], timeout=180)
# Separately labelled diagnostic profiles; excluded from the primary timing table.
for mode in ['baseline', 'candidate']:
    profile = r.EVIDENCE/(mode+'-crud.cpu.pprof')
    r.run('profile-'+mode, [r.TEMP/(mode+'-probe'), '-crud-iterations=2000', '-cpu-profile='+str(profile)], timeout=90)
    r.run('profile-top-'+mode, [r.GO, 'tool', 'pprof', '-top', '-nodecount=30', r.TEMP/(mode+'-probe'), profile])
fixture = Path(os.environ['MARIAMEM_FIXTURE_INPUT'])
r.run('compiler-inline-assessment', [r.GO, 'build', '-p', '1', '-gcflags=genericfixture/fixture=-m=2', '-o', r.TEMP/'inline-fixture', '.'], cwd=fixture)
r.run('canonical-check', [r.SHARED/'.venv/bin/python', r.ROOT/'scripts/verify.py', 'check'], timeout=900)
r.record['finished'] = True
r.save()
