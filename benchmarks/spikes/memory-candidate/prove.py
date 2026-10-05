#!/usr/bin/env python3
"""Bind regenerated license evidence and independently replay the source pipeline."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import run as r

inputs = Path(os.environ['MARIAMEM_MEASURE_INPUT'])
measured = json.loads((inputs/'evidence/campaign.json').read_text())
probe = inputs/'temp/candidate-probe'
assert r.digest(probe) == measured['probe_sha256']['candidate']
assert r.digest(r.ROOT/'internal/generatedgo/provenance.json') == measured['candidate_provenance_sha256']
r.run('build-counter', ['cc', '-O2', r.ROOT/'benchmarks/tools/process_cost.c', '-o', r.TEMP/'process-cost'])
r.run('candidate-symbols', [r.GO, 'tool', 'nm', probe])
evidence_path = r.ROOT/'release/generated-license-evidence.json'
evidence = json.loads(evidence_path.read_text())
symbols = (r.EVIDENCE/'candidate-symbols.log').read_text()
checked = []
for component, row in evidence['retained_symbols'].items():
    for example in row['examples']:
        path = r.ROOT/example['generated_file']
        name = example['generated_function']
        assert 'func '+name+'(' in path.read_text()
        package = path.parent.name
        assert re.search(r'/code/'+re.escape(package)+r'\.'+re.escape(name)+r'(?:\.abi0)?$', symbols, re.M), name
        checked.append({'component': component, 'function': name, 'generated_file': example['generated_file'], 'candidate_symbol_retained': True})
evidence['generated_provenance_sha256'] = r.digest(r.ROOT/'internal/generatedgo/provenance.json')
evidence['host_check']['note'] = 'Historical released-runtime attribution only; see memory32_candidate_check for regenerated inventory. Not a new release artifact approval.'
evidence['memory32_candidate_check'] = {'base': r.RELEASE, 'prototype_basis': '49817bb8c918be6215f6dfe5a4bdce98ab8d77ab', 'probe_sha256': r.digest(probe), 'generated_provenance_sha256': evidence['generated_provenance_sha256'], 'examples': checked, 'note': 'Same pinned guest and function map; generated definitions and positive native retention rechecked against the measured candidate probe. No release approval.'}
evidence_path.write_text(json.dumps(evidence, indent=2)+'\n')
license_path = r.ROOT/'release/distribution-licenses.json'
license = json.loads(license_path.read_text())
license['evidence_sha256'] = r.digest(evidence_path)
license_path.write_text(json.dumps(license, indent=2)+'\n')
shutil.copyfile(license_path,r.ROOT/'python/license-inventory.json')
r.record['retained_license_examples_rechecked'] = len(checked)
r.save()
# Duplicate cached inputs are owned copies, never modifications to the cache.
tools = json.loads((r.ROOT/'release/generated-go-toolchain.json').read_text())
download = r.ROOT/'build/downloads'/tools['archives']['converter']['file']
download.parent.mkdir(parents=True, exist_ok=True)
shutil.copyfile(r.CACHE/'wasm2go-fork.tar.gz', download)
assert r.digest(download) == tools['archives']['converter']['sha256']
guest = r.TEMP/'guest'
guest.mkdir()
shutil.copyfile(r.GUEST, guest/'mariamem.wasm')
shutil.copyfile(r.GUEST.parent/'guest.json', guest/'guest.json')
r.run('independent-regeneration', [r.sys.executable, r.ROOT/'scripts/regenerate_release_guest.py', '--guest-dir', guest, '--output', r.TEMP/'regeneration'], timeout=600)
r.run('canonical-check', [r.SHARED/'.venv/bin/python', r.ROOT/'scripts/verify.py', 'check'], timeout=900)
r.record['finished'] = True
r.save()
